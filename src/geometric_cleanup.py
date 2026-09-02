"""
Fase 2b: Depuracion geometrica — transforma primitivas CAD en representacion
limpia de elementos estructurales fisicos por planta.

No genera modelos OpenSees. Solo identifica vigas, pilares, muros y ejes
a partir de las capas RLE-*, con agrupacion por proximidad y verificaciones.
"""

import ezdxf
import math
import json
import hashlib
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Rutas ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DXF_DIR = ROOT / "data" / "dxf"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

DXF_FILES = [
    "2017_67-100.dxf",
    "2017_67-101.dxf",
    "2017_67-102.dxf",
    "2017_67-103.dxf",
]

CAD_FACTOR = 100.0
BEAM_WIDTH_CAD = 60.0
WALL_THICK_CAD = 20.0
COL_SIZE_CAD = 70.0
COL_CLUSTER_TOL = 30.0
BEAM_PARALLEL_TOL = 15.0
WALL_PARALLEL_TOL = 10.0
SHORT_ELEM_CAD = 100.0
MAIN_AXIS_V_MIN_LEN = 2000.0
MAIN_AXIS_H_MIN_LEN = 3000.0
AXIS_LABEL_MATCH_TOL = 150.0


def pr(line=""):
    print(line)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def line_length(s, e):
    return math.hypot(e[0] - s[0], e[1] - s[1])


def line_angle(s, e):
    return math.atan2(e[1] - s[1], e[0] - s[0])


def midpoint(s, e):
    return ((s[0] + e[0]) / 2.0, (s[1] + e[1]) / 2.0)


def is_horizontal(s, e, tol=0.1):
    return abs(e[1] - s[1]) < tol * line_length(s, e) + 0.01


def is_vertical(s, e, tol=0.1):
    return abs(e[0] - s[0]) < tol * line_length(s, e) + 0.01


def parallel_distance(s1, e1, s2, e2):
    """Distance between two parallel line segments (perpendicular offset)."""
    dx, dy = e1[0] - s1[0], e1[1] - s1[1]
    ln = math.hypot(dx, dy)
    if ln < 1e-6:
        return float("inf")
    nx, ny = -dy / ln, dx / ln
    d = abs(nx * (s2[0] - s1[0]) + ny * (s2[1] - s1[1]))
    return d


def segment_overlap_1d(a_min, a_max, b_min, b_max):
    """Overlap length of two 1D intervals."""
    return max(0.0, min(a_max, b_max) - max(a_min, b_min))


# ═══════════════════════════════════════════════════════════════════════
# Extraction of raw geometry from one DXF file
# ═══════════════════════════════════════════════════════════════════════

def extract_lines_from_layer(msp, layer):
    """Return list of (start, end, length, midpoint, angle) for LINE entities on layer."""
    results = []
    for e in msp.query(f'LINE[layer=="{layer}"]'):
        s = (e.dxf.start.x, e.dxf.start.y)
        end = (e.dxf.end.x, e.dxf.end.y)
        ln = line_length(s, end)
        if ln < 0.5:
            continue
        results.append({
            "start": s, "end": end, "length": ln,
            "mid": midpoint(s, end), "angle": line_angle(s, end),
        })
    return results


def extract_closed_polylines_from_layer(msp, layer):
    """Return list of vertex lists for closed LWPOLYLINE entities on layer."""
    results = []
    for e in msp.query(f'LWPOLYLINE[layer=="{layer}"]'):
        pts = [(p[0], p[1]) for p in e.get_points(format="xy")]
        if len(pts) < 3:
            continue
        results.append(pts)
    return results


def extract_mtext_from_layer(msp, layer):
    """Return list of (text, position, height) for MTEXT entities on layer."""
    results = []
    for e in msp.query(f'MTEXT[layer=="{layer}"]'):
        txt = e.plain_text().strip()
        pos = (e.dxf.insert.x, e.dxf.insert.y)
        h = e.dxf.char_height
        if txt:
            results.append({"text": txt, "pos": pos, "height": h})
    return results


def extract_circles_from_layer(msp, layer):
    """Return list of (center, radius) for CIRCLE entities on layer."""
    results = []
    for e in msp.query(f'CIRCLE[layer=="{layer}"]'):
        c = (e.dxf.center.x, e.dxf.center.y)
        r = e.dxf.radius
        results.append({"center": c, "radius": r})
    return results


# ═══════════════════════════════════════════════════════════════════════
# Grouping: PILARES (columns)
# ═══════════════════════════════════════════════════════════════════════

def group_columns(lines):
    """
    Group RLE-PILAR lines into physical columns.

    A physical column is drawn as a 70x70 CAD closed square: 4 LINEs of length
    ~70 (two horizontal, two vertical). Each edge implies the square center:
      - horizontal bottom edge (x0..x1, y): center = (mid_x, y + 35)
      - horizontal top edge    (x0..x1, y): center = (mid_x, y - 35)
      - vertical   left edge  (x, y0..y1): center = (x + 35, mid_y)
      - vertical   right edge (x, y0..y1): center = (x - 35, mid_y)

    All 4 edges of one column project to the same center. We cluster the
    inferred centers and take the bounding box of the clustered lines.
    """
    col_lines = [l for l in lines if 55.0 <= l["length"] <= 85.0]

    if not col_lines:
        return []

    half = 35.0
    cands_per_line = []
    all_cands = []
    for l in col_lines:
        s, e = l["start"], l["end"]
        if is_horizontal(s, e):
            cx = (s[0] + e[0]) / 2.0
            y = s[1]
            cands = [(cx, y + half), (cx, y - half)]
        elif is_vertical(s, e):
            cy = (s[1] + e[1]) / 2.0
            x = s[0]
            cands = [(x + half, cy), (x - half, cy)]
        else:
            cands = [((s[0] + e[0]) / 2.0, (s[1] + e[1]) / 2.0)]
        cands_per_line.append(cands)
        all_cands.extend(cands)

    # Cluster all candidate centers in 2D. Each physical column produces 4
    # votes at its true center (one from each edge), so dense clusters (>=3
    # votes) are the true column centers; spurious candidates sit isolated.
    centers_pts = np.array(all_cands)
    assigned_pt = [False] * len(all_cands)
    cluster_centers = []
    for i in range(len(all_cands)):
        if assigned_pt[i]:
            continue
        cl = [i]
        assigned_pt[i] = True
        for j in range(i + 1, len(all_cands)):
            if assigned_pt[j]:
                continue
            if np.linalg.norm(centers_pts[i] - centers_pts[j]) < COL_CLUSTER_TOL:
                cl.append(j)
                assigned_pt[j] = True
        if len(cl) >= 3:
            cluster_centers.append(tuple(centers_pts[cl].mean(axis=0)))

    # Group lines by which dense column-center their candidate set is closest to.
    line_groups = {}
    for li, cands in enumerate(cands_per_line):
        best_j = None
        best_d = float("inf")
        for j, cc in enumerate(cluster_centers):
            for cx, cy_ in cands:
                d = math.hypot(cx - cc[0], cy_ - cc[1])
                if d < best_d:
                    best_d = d
                    best_j = j
        if best_d <= COL_CLUSTER_TOL:
            line_groups.setdefault(best_j, []).append(li)

    columns = []
    for j, idxs in line_groups.items():
        all_x = []
        all_y = []
        for k in idxs:
            s, e = col_lines[k]["start"], col_lines[k]["end"]
            all_x += [s[0], e[0]]
            all_y += [s[1], e[1]]
        all_x_min, all_x_max = min(all_x), max(all_x)
        all_y_min, all_y_max = min(all_y), max(all_y)
        cx = (all_x_min + all_x_max) / 2.0
        cy = (all_y_min + all_y_max) / 2.0
        w = all_x_max - all_x_min
        h = all_y_max - all_y_min
        columns.append({
            "center_cad": (cx, cy),
            "center_m": (cx / CAD_FACTOR, cy / CAD_FACTOR),
            "bbox_cad": (all_x_min, all_y_min, all_x_max, all_y_max),
            "width_cad": w,
            "height_cad": h,
            "n_primitives": len(idxs),
        })

    return columns


# ═══════════════════════════════════════════════════════════════════════
# Element extractor (shared by vigas & muros)
# ═══════════════════════════════════════════════════════════════════════

def cluster_1d(values, tol):
    """Cluster 1D coordinates; return list of mean values."""
    values = sorted(values)
    groups = []
    for v in values:
        if groups and v - groups[-1][-1] < tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def detect_face_width(clustered_coords):
    """
    Detect the dominant small spacing between consecutive parallel face
    coordinates (the drawing convention for element width in CAD units).
    Returns the modal small spacing, or a default if none found.
    """
    cs = sorted(clustered_coords)
    diffs = []
    for i in range(1, len(cs)):
        d = abs(cs[i] - cs[i - 1])
        if d >= 5.0 and d <= 150.0:
            diffs.append(round(d))
    if not diffs:
        return None
    from collections import Counter
    # Prefer the smallest modal spacing (the element width, not bay spacing)
    cnt = Counter(diffs)
    small = [d for d, c in cnt.items() if d <= 80]
    if small:
        return max(set(small), key=lambda d: cnt[d])
    return max(set(diffs), key=lambda d: cnt[d])


def merge_runs(segments):
    """
    Given intervals (a,b) on a line, merge overlapping/adjacent ones into
    maximal runs. Returns list of (start, end) tuples.
    """
    segs = sorted([(min(a, b), max(a, b)) for a, b in segments])
    if not segs:
        return []
    merged = [list(segs[0])]
    for a, b in segs[1:]:
        if a <= merged[-1][1] + 15.0:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged]


def extract_face_runs(lines, orientation, min_len_cad=50.0, coord_tol=8.0):
    """
    Group parallel line segments of a given orientation into 'face runs'.
    Returns list of dicts: {coord, interval:(start,end), length, n_segments}
    """
    if orientation == "H":
        sel = [l for l in lines if is_horizontal(l["start"], l["end"]) and l["length"] >= min_len_cad]
        coords = [l["mid"][1] for l in sel]
    else:
        sel = [l for l in lines if is_vertical(l["start"], l["end"]) and l["length"] >= min_len_cad]
        coords = [l["mid"][0] for l in sel]

    if not sel:
        return []

    centers = cluster_1d(coords, coord_tol)

    runs = []
    for c in centers:
        bucket = [l for l in sel if abs((l["mid"][1] if orientation == "H" else l["mid"][0]) - c) < coord_tol]
        if not bucket:
            continue
        if orientation == "H":
            intervals = [(l["start"][0], l["end"][0]) for l in bucket]
            merged = merge_runs(intervals)
            for a, b in merged:
                runs.append({
                    "coord": c,
                    "interval": (a, b),
                    "length": b - a,
                    "n_segments": 1,
                })
        else:
            intervals = [(l["start"][1], l["end"][1]) for l in bucket]
            merged = merge_runs(intervals)
            for a, b in merged:
                runs.append({
                    "coord": c,
                    "interval": (a, b),
                    "length": b - a,
                    "n_segments": 1,
                })
    return runs


def pair_runs_to_elements(runs, orientation, face_width, width_tol, frag_label):
    """
    Pair parallel face runs separated by ~face_width into linear elements.
    Returns (elements, unpaired_runs).
    """
    elements = []
    used = [False] * len(runs)

    for i in range(len(runs)):
        if used[i]:
            continue
        for j in range(i + 1, len(runs)):
            if used[j]:
                continue
            d = abs(runs[i]["coord"] - runs[j]["coord"])
            if face_width is not None and abs(d - face_width) <= width_tol:
                itv_i, itv_j = runs[i]["interval"], runs[j]["interval"]
                overlap = segment_overlap_1d(itv_i[0], itv_i[1], itv_j[0], itv_j[1])
                if overlap > 0.4 * max(itv_i[1] - itv_i[0], itv_j[1] - itv_j[0]):
                    if orientation == "H":
                        coord = (runs[i]["coord"] + runs[j]["coord"]) / 2.0
                        a = min(itv_i[0], itv_j[0])
                        b = max(itv_i[1], itv_j[1])
                        centerline = ((a, coord), (b, coord))
                    else:
                        coord = (runs[i]["coord"] + runs[j]["coord"]) / 2.0
                        a = min(itv_i[0], itv_j[0])
                        b = max(itv_i[1], itv_j[1])
                        centerline = ((coord, a), (coord, b))
                    elements.append({
                        "type": frag_label,
                        "orientation": orientation,
                        "centerline_cad": centerline,
                        "length_cad": abs(b - a),
                        "width_cad": d,
                        "n_primitives": runs[i]["n_segments"] + runs[j]["n_segments"],
                    })
                    used[i] = True
                    used[j] = True
                    break

    unpaired = [runs[k] for k in range(len(runs)) if not used[k]]
    return elements, unpaired


# ═══════════════════════════════════════════════════════════════════════
# Grouping: VIGAS (beams)
# ═══════════════════════════════════════════════════════════════════════

def group_beams(lines, column_centers):
    """
    Group RLE-VIGA lines into physical beams.

    Strategy (data-driven, tolerant of differing drawing conventions across
    files): 
    1. Keep reasonably long lines (>= 80 CAD) as beam face segments.
    2. Adapt the example: a face line is used only via its collinear runs.
    3. Build parallel face runs per orientation.
    4. Auto-detect the dominant face width from the spacing between face coords.
    5. Pair runs at that width -> centerline.
    6. Unpaired runs become ambiguous 'beam_fragment' entries (reported).
    """
    beam_lines = [l for l in lines if l["length"] >= 80.0]
    if not beam_lines:
        return [], []

    h_runs = extract_face_runs(beam_lines, "H")
    v_runs = extract_face_runs(beam_lines, "V")

    h_coords = cluster_1d([r["coord"] for r in h_runs], 8.0)
    v_coords = cluster_1d([r["coord"] for r in v_runs], 8.0)
    all_coords = h_coords + v_coords
    face_width = detect_face_width(all_coords)

    beams = []
    fragments = []

    for runs, orient in ((h_runs, "H"), (v_runs, "V")):
        els, unpaired = pair_runs_to_elements(runs, orient, face_width, 12.0, "beam")
        beams.extend(els)
        for u in unpaired:
            fragments.append({
                "type": "beam_fragment",
                "orientation": orient,
                "centerline_cad": (
                    ((u["interval"][0], u["coord"]), (u["interval"][1], u["coord"]))
                    if orient == "H"
                    else ((u["coord"], u["interval"][0]), (u["coord"], u["interval"][1]))
                ),
                "length_cad": u["length"],
                "n_primitives": u["n_segments"],
            })

    for b in beams + fragments:
        s, e = b["centerline_cad"]
        b["centerline_m"] = (
            (s[0] / CAD_FACTOR, s[1] / CAD_FACTOR),
            (e[0] / CAD_FACTOR, e[1] / CAD_FACTOR),
        )
        b["length_m"] = b["length_cad"] / CAD_FACTOR
        b["midpoint_m"] = (
            (s[0] + e[0]) / 2.0 / CAD_FACTOR,
            (s[1] + e[1]) / 2.0 / CAD_FACTOR,
        )

    return beams, fragments


# ═══════════════════════════════════════════════════════════════════════
# Grouping: MUROS (walls)
# ═══════════════════════════════════════════════════════════════════════

def group_walls(lines):
    """
    Group RLE-MURO lines into physical walls using the same face-run pairing
    approach, with wall thickness auto-detected (typically ~20 CAD).
    """
    wall_lines = [l for l in lines if l["length"] >= 20.0]
    if not wall_lines:
        return [], []

    h_runs = extract_face_runs(wall_lines, "H", min_len_cad=20.0)
    v_runs = extract_face_runs(wall_lines, "V", min_len_cad=20.0)

    h_coords = cluster_1d([r["coord"] for r in h_runs], 8.0)
    v_coords = cluster_1d([r["coord"] for r in v_runs], 8.0)
    face_width = detect_face_width(h_coords + v_coords)

    walls = []
    fragments = []

    for runs, orient in ((h_runs, "H"), (v_runs, "V")):
        els, unpaired = pair_runs_to_elements(runs, orient, face_width, 8.0, "wall")
        walls.extend(els)
        for u in unpaired:
            fragments.append({
                "type": "wall_fragment",
                "orientation": orient,
                "centerline_cad": (
                    ((u["interval"][0], u["coord"]), (u["interval"][1], u["coord"]))
                    if orient == "H"
                    else ((u["coord"], u["interval"][0]), (u["coord"], u["interval"][1]))
                ),
                "length_cad": u["length"],
                "n_primitives": u["n_segments"],
            })

    for w in walls + fragments:
        s, e = w["centerline_cad"]
        w["centerline_m"] = (
            (s[0] / CAD_FACTOR, s[1] / CAD_FACTOR),
            (e[0] / CAD_FACTOR, e[1] / CAD_FACTOR),
        )
        w["length_m"] = w["length_cad"] / CAD_FACTOR

    return walls, fragments


# ═══════════════════════════════════════════════════════════════════════
# Axes: depurated structural grid
# ═══════════════════════════════════════════════════════════════════════

def depurate_axes(msp):
    """
    Depurate structural axes from RLE-EJES lines and RLE-EJE MTEXT labels.

    Strategy:
    1. Extract all RLE-EJES LINE entities.
    2. Filter: keep only lines longer than threshold (main grid only).
    3. Group same-orientation lines at same coordinate (within tolerance).
    4. Match MTEXT labels from RLE-EJE to axis lines by proximity.
    5. Handle ambiguity: if multiple labels match, report it.
    """
    raw_lines = extract_lines_from_layer(msp, "RLE-EJES")
    mtexts = extract_mtext_from_layer(msp, "RLE-EJE")
    circles = extract_circles_from_layer(msp, "RLE-EJE")

    main_v = [
        l for l in raw_lines
        if is_vertical(l["start"], l["end"]) and l["length"] >= MAIN_AXIS_V_MIN_LEN
    ]
    main_h = [
        l for l in raw_lines
        if is_horizontal(l["start"], l["end"]) and l["length"] >= MAIN_AXIS_H_MIN_LEN
    ]

    def deduplicate_by_coord(line_list, coord_extractor, tol=5.0):
        groups = []
        used = [False] * len(line_list)
        for i in range(len(line_list)):
            if used[i]:
                continue
            ci = coord_extractor(line_list[i])
            group = [i]
            used[i] = True
            for j in range(i + 1, len(line_list)):
                if used[j]:
                    continue
                cj = coord_extractor(line_list[j])
                if abs(ci - cj) < tol:
                    group.append(j)
                    used[j] = True
            groups.append(group)
        return groups

    v_groups = deduplicate_by_coord(main_v, lambda l: (l["start"][0] + l["end"][0]) / 2.0)
    h_groups = deduplicate_by_coord(main_h, lambda l: (l["start"][1] + l["end"][1]) / 2.0)

    LABEL_TOL = 60.0

    def match_label(coord, orientation, extent_min, extent_max):
        """
        Find the single best MTEXT label for an axis.
        A V-axis label sits at the same x, at one extreme of the vertical extent.
        We assign the nearest label in the primary coordinate, with a small
        tolerance, and flag ambiguity only if two labels tie closely.
        Returns (label, ambiguous_info_or_None).
        """
        best = None
        best_d = float("inf")
        for mt in mtexts:
            lx, ly = mt["pos"]
            if orientation == "V":
                d = abs(lx - coord)
                # label must be near the same x and at/near the axis extremes
                if d < LABEL_TOL and (extent_min - 400) <= ly <= (extent_max + 400):
                    pass
                else:
                    continue
            else:
                d = abs(ly - coord)
                if d < LABEL_TOL and (extent_min - 400) <= lx <= (extent_max + 400):
                    pass
                else:
                    continue
            if d < best_d:
                best_d = d
                best = (d, mt["text"])

        if best is None:
            return f"{'V' if orientation == 'V' else 'H'}_{coord:.0f}", {
                "coord_cad": coord,
                "coord_m": coord / CAD_FACTOR,
                "orientation": orientation,
                "labels_found": [],
                "resolved_as": None,
            }, None

        # Look for another label within a tight tie margin of the best.
        tie_labels = set()
        for mt in mtexts:
            lx, ly = mt["pos"]
            if orientation == "V":
                dd = abs(lx - coord)
                in_ext = (extent_min - 400) <= ly <= (extent_max + 400)
            else:
                dd = abs(ly - coord)
                in_ext = (extent_min - 400) <= lx <= (extent_max + 400)
            if dd < LABEL_TOL and in_ext and abs(dd - best_d) < 30.0:
                tie_labels.add(mt["text"])

        resolved = best[1]
        if len(tie_labels) > 1:
            return resolved, {
                "coord_cad": coord,
                "coord_m": coord / CAD_FACTOR,
                "orientation": orientation,
                "labels_found": sorted(tie_labels),
                "resolved_as": resolved,
            }, resolved
        return resolved, None, resolved

    axes = []
    ambiguous = []

    for grp_indices in v_groups:
        grp = [main_v[k] for k in grp_indices]
        avg_x = sum((l["start"][0] + l["end"][0]) / 2.0 for l in grp) / len(grp)
        y_vals = []
        for l in grp:
            y_vals.extend([l["start"][1], l["end"][1]])
        y_min, y_max = min(y_vals), max(y_vals)
        total_len = y_max - y_min

        label, amb, _ = match_label(avg_x, "V", y_min, y_max)
        if amb:
            ambiguous.append(amb)

        axes.append({
            "label": label,
            "orientation": "V",
            "coord_cad": avg_x,
            "coord_m": avg_x / CAD_FACTOR,
            "extent_cad": (y_min, y_max),
            "length_cad": total_len,
            "n_raw_lines": len(grp),
        })

    for grp_indices in h_groups:
        grp = [main_h[k] for k in grp_indices]
        avg_y = sum((l["start"][1] + l["end"][1]) / 2.0 for l in grp) / len(grp)
        x_vals = []
        for l in grp:
            x_vals.extend([l["start"][0], l["end"][0]])
        x_min, x_max = min(x_vals), max(x_vals)
        total_len = x_max - x_min

        label, amb, _ = match_label(avg_y, "H", x_min, x_max)
        if amb:
            ambiguous.append(amb)

        axes.append({
            "label": label,
            "orientation": "H",
            "coord_cad": avg_y,
            "coord_m": avg_y / CAD_FACTOR,
            "extent_cad": (x_min, x_max),
            "length_cad": total_len,
            "n_raw_lines": len(grp),
        })

    return axes, ambiguous


# ═══════════════════════════════════════════════════════════════════════
# Verification checks
# ═══════════════════════════════════════════════════════════════════════

def verify_elements(beams, beam_frags, walls, wall_frags, columns):
    issues = []

    for i, c in enumerate(columns):
        w, h = c["width_cad"], c["height_cad"]
        if w < 10 or h < 10:
            issues.append(f"Pilar {i}: dimension minima degenerada ({w:.1f}x{h:.1f} CAD)")
        if abs(w - COL_SIZE_CAD) > 15 or abs(h - COL_SIZE_CAD) > 15:
            issues.append(
                f"Pilar {i}: dimension inusual ({w:.1f}x{h:.1f} CAD, esperado ~{COL_SIZE_CAD:.0f})"
            )

    for i, b in enumerate(beams):
        if b["length_m"] < 0.4:
            issues.append(f"Viga {i}: longitud muy corta ({b['length_m']:.2f} m)")

    for i, w in enumerate(walls):
        if w["length_m"] < 0.4:
            issues.append(f"Muro {i}: longitud muy corta ({w['length_m']:.2f} m)")

    if len(beam_frags) > 0:
        issues.append(f"Vigas ambiguas/fragmento: {len(beam_frags)} face-runs sin pareja")
    if len(wall_frags) > 0:
        issues.append(f"Muros ambiguos/fragmento: {len(wall_frags)} face-runs sin pareja")

    return issues


# ═══════════════════════════════════════════════════════════════════════
# Figures
# ═══════════════════════════════════════════════════════════════════════

def plot_plant_clean(dxf_name, beams, beam_frags, walls, wall_frags, columns, axes, ambiguous, output_path):
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_aspect("equal")
    ax.set_title(
        f"{dxf_name} — Elementos estructurales fisicos depurados\n"
        f"Vigas={len(beams)}  Pilares={len(columns)}  Muros={len(walls)}  "
        f"Ejes={len(axes)}  [ambiguos: vigas={len(beam_frags)} muros={len(wall_frags)}]",
        fontsize=11,
    )

    for c in columns:
        x0, y0, x1, y1 = c["bbox_cad"]
        rect = mpatches.Rectangle(
            (x0 / CAD_FACTOR, y0 / CAD_FACTOR),
            (x1 - x0) / CAD_FACTOR, (y1 - y0) / CAD_FACTOR,
            linewidth=1.5, edgecolor="black", facecolor="orange", alpha=0.7,
        )
        ax.add_patch(rect)

    for b in beams:
        s, e = b["centerline_cad"]
        color = "blue" if b["orientation"] == "H" else (
            "darkblue" if b["orientation"] == "V" else "purple"
        )
        ax.plot(
            [s[0] / CAD_FACTOR, e[0] / CAD_FACTOR],
            [s[1] / CAD_FACTOR, e[1] / CAD_FACTOR],
            color=color, linewidth=1.2, alpha=0.8,
        )

    for b in beam_frags:
        s, e = b["centerline_cad"]
        ax.plot(
            [s[0] / CAD_FACTOR, e[0] / CAD_FACTOR],
            [s[1] / CAD_FACTOR, e[1] / CAD_FACTOR],
            color="cyan", linewidth=0.8, alpha=0.6, linestyle=":",
        )

    for w in walls:
        s, e = w["centerline_cad"]
        ax.plot(
            [s[0] / CAD_FACTOR, e[0] / CAD_FACTOR],
            [s[1] / CAD_FACTOR, e[1] / CAD_FACTOR],
            color="green", linewidth=2.0, alpha=0.8,
        )

    for w in wall_frags:
        s, e = w["centerline_cad"]
        ax.plot(
            [s[0] / CAD_FACTOR, e[0] / CAD_FACTOR],
            [s[1] / CAD_FACTOR, e[1] / CAD_FACTOR],
            color="lightgreen", linewidth=1.2, alpha=0.7, linestyle=":",
        )

    for a in axes:
        xmin, xmax = a["extent_cad"]
        if a["orientation"] == "V":
            ax.axvline(
                a["coord_m"], color="red", linewidth=0.6, alpha=0.5, linestyle="--",
            )
            ax.text(
                a["coord_m"], a["extent_cad"][1] / CAD_FACTOR + 1.0,
                a["label"], fontsize=7, color="red", ha="center", va="bottom",
                fontweight="bold",
            )
        else:
            ax.axhline(
                a["coord_m"], color="red", linewidth=0.6, alpha=0.5, linestyle="--",
            )
            ax.text(
                a["extent_cad"][1] / CAD_FACTOR + 1.0, a["coord_m"],
                a["label"], fontsize=7, color="red", ha="left", va="center",
                fontweight="bold",
            )

    legend_items = [
        mpatches.Patch(color="orange", alpha=0.7, label=f"Pilares ({len(columns)})"),
        plt.Line2D([0], [0], color="blue", linewidth=1.2, label=f"Vigas ({len(beams)})"),
        plt.Line2D([0], [0], color="green", linewidth=2.0, label=f"Muros ({len(walls)})"),
        plt.Line2D([0], [0], color="red", linewidth=0.6, linestyle="--", label=f"Ejes ({len(axes)})"),
        plt.Line2D([0], [0], color="cyan", linewidth=0.8, linestyle=":", label=f"Ambig: v={len(beam_frags)} m={len(wall_frags)}"),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=8)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_axis_comparison(all_results, output_path):
    fig, ax = plt.subplots(1, 1, figsize=(16, 8))
    ax.set_title("Comparacion de ejes estructurales depurados entre plantas", fontsize=12)
    colors_v = plt.cm.Set1(np.linspace(0, 1, 12))
    colors_h = plt.cm.Set2(np.linspace(0, 1, 12))

    all_v_axes = defaultdict(list)
    all_h_axes = defaultdict(list)

    for dxf_name, data in all_results.items():
        for a in data["axes"]:
            if a["orientation"] == "V":
                all_v_axes[a["label"]].append((dxf_name, a["coord_m"]))
            else:
                all_h_axes[a["label"]].append((dxf_name, a["coord_m"]))

    v_labels = sorted(all_v_axes.keys(), key=lambda k: all_v_axes[k][0][1])
    h_labels = sorted(all_h_axes.keys(), key=lambda k: all_h_axes[k][0][1])

    dxf_names = list(all_results.keys())
    y_positions_v = {name: i * 0.15 for i, name in enumerate(dxf_names)}
    y_positions_h = {name: i * 0.15 for i, name in enumerate(dxf_names)}

    for idx, label in enumerate(v_labels):
        entries = all_v_axes[label]
        color = colors_v[idx % len(colors_v)]
        for dxf_name, coord in entries:
            y = y_positions_v[dxf_name] + idx * 0.8
            ax.plot(coord, y, "|", color=color, markersize=20, markeredgewidth=2)
        if len(entries) >= 2:
            coords = [c for _, c in entries]
            spread = max(coords) - min(coords)
            if spread > 0.5:
                mid_y = sum(y_positions_v[d] + idx * 0.8 for d, _ in entries) / len(entries)
                ax.annotate(
                    f"{label} ({spread:.1f}m)",
                    xy=(np.mean(coords), mid_y),
                    fontsize=6, color="red", ha="center",
                )

    for idx, label in enumerate(h_labels):
        entries = all_h_axes[label]
        color = colors_h[idx % len(colors_h)]
        for dxf_name, coord in entries:
            y = y_positions_h[dxf_name] + idx * 0.5
            ax.axhline(y, xmin=0, xmax=1, color=color, linewidth=0.3, alpha=0.3)

    ax.set_xlabel("Coordenada X para ejes V / Y para ejes H (m)")
    ax.set_ylabel("Planta")
    ax.set_yticks([y_positions_v[n] + 0.4 for n in dxf_names])
    ax.set_yticklabels(dxf_names)
    ax.grid(True, alpha=0.2, axis="x")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    pr("=" * 90)
    pr("  FASE 2b: DEPURACION GEOMETRICA — ELEMENTOS ESTRUCTURALES FISICOS")
    pr("=" * 90)
    pr()

    all_results = {}
    all_stats = {}
    all_issues = {}
    all_ambiguous = {}

    hashes_before = {f: sha256(DXF_DIR / f) for f in DXF_FILES}

    for dxf_name in DXF_FILES:
        pr(f"  Procesando {dxf_name}...")
        doc = ezdxf.readfile(str(DXF_DIR / dxf_name))
        msp = doc.modelspace()

        raw_viga = extract_lines_from_layer(msp, "RLE-VIGA")
        raw_pilar = extract_lines_from_layer(msp, "RLE-PILAR")
        raw_muro = extract_lines_from_layer(msp, "RLE-MURO")

        columns = group_columns(raw_pilar)
        beams, beam_frags = group_beams(raw_viga, [c["center_cad"] for c in columns])
        walls, wall_frags = group_walls(raw_muro)
        axes, ambiguous = depurate_axes(msp)

        issues = verify_elements(beams, beam_frags, walls, wall_frags, columns)

        stats = {
            "raw_viga_lines": len(raw_viga),
            "raw_pilar_lines": len(raw_pilar),
            "raw_muro_lines": len(raw_muro),
            "physical_beams": len(beams),
            "beam_fragments": len(beam_frags),
            "physical_columns": len(columns),
            "physical_walls": len(walls),
            "wall_fragments": len(wall_frags),
            "main_axes": len(axes),
            "ambiguous_axes": len(ambiguous),
        }
        all_stats[dxf_name] = stats
        all_issues[dxf_name] = issues
        all_ambiguous[dxf_name] = ambiguous
        all_results[dxf_name] = {
            "beams": beams,
            "beam_fragments": beam_frags,
            "columns": columns,
            "walls": walls,
            "wall_fragments": wall_frags,
            "axes": axes,
        }

        pr(f"    Primitivas crudas:  vigas={len(raw_viga)}  pilares={len(raw_pilar)}  muros={len(raw_muro)}")
        pr(f"    Elementos fisicos: vigas={len(beams)}  pilares={len(columns)}  muros={len(walls)}")
        pr(f"    Ambiguos: viga_frag={len(beam_frags)}  muro_frag={len(wall_frags)}")
        pr(f"    Ejes principales:  {len(axes)}  (etiquetas ambiguas: {len(ambiguous)})")
        if issues:
            for iss in issues:
                pr(f"      [!] {iss}")
        pr()

        fig_path = FIGURES_DIR / f"{dxf_name.replace('.dxf', '')}_depurado.png"
        plot_plant_clean(dxf_name, beams, beam_frags, walls, wall_frags, columns, axes, ambiguous, fig_path)
        pr(f"    Figura: {fig_path.relative_to(ROOT)}")

    pr()
    pr("  Generando comparacion de ejes depurados...")
    plot_axis_comparison(all_results, FIGURES_DIR / "comparacion_ejes_depurada.png")
    pr(f"    Figura: figures/comparacion_ejes_depurada.png")

    pr()
    pr("=" * 90)
    pr("  RESUMEN DE ELEMENTOS FISICOS POR PLANTA")
    pr("=" * 90)
    pr()
    pr(f"  {'Planta':<20} {'Vigas':>6} {'Vfrag':>6} {'Pilares':>8} {'Muros':>6} {'Mfrag':>6} {'Ejes':>5}")
    pr(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*8} {'-'*6} {'-'*6} {'-'*5}")
    for dxf_name in DXF_FILES:
        s = all_stats[dxf_name]
        pr(
            f"  {dxf_name:<20} {s['physical_beams']:>6} {s['beam_fragments']:>6} {s['physical_columns']:>8} "
            f"{s['physical_walls']:>6} {s['wall_fragments']:>6} {s['main_axes']:>5}"
        )
    pr()

    pr("  CRITERIOS DE AGRUPACION DE PRIMITIVAS CAD:")
    pr(f"    Pilares: LINEs de ~{COL_SIZE_CAD:.0f} CAD, centroides agrupados por cercania (tol={COL_CLUSTER_TOL:.0f} CAD)")
    pr(f"    Vigas: face-runs paralelas a distancia ~ancho de viga (detectado por archivo), con solapamiento > 40%")
    pr(f"    Muros: face-runs paralelas a distancia ~espesor de muro (detectado por archivo), con solapamiento > 40%")
    pr(f"    Ancho/espesor: detectado automaticamente (espaciado modal entre coordenadas de cara por archivo)")
    pr(f"    Ejes: LINEs de RLE-EJES > {MAIN_AXIS_V_MIN_LEN:.0f} CAD (V) / > {MAIN_AXIS_H_MIN_LEN:.0f} CAD (H)")
    pr(f"    Etiquetas: MTEXT de RLE-EJE, matching por proximidad (< {AXIS_LABEL_MATCH_TOL:.0f} CAD); si es ambiguo se reporta")
    pr()

    pr("  AMBIGUEDADES REPORTADAS:")
    any_ambig = False
    for dxf_name in DXF_FILES:
        for amb in all_ambiguous[dxf_name]:
            pr(f"    {dxf_name}: eje {amb['orientation']} en {amb['coord_m']:.1f} m")
            pr(f"      Labels encontrados: {amb['labels_found']}")
            pr(f"      Resuelto como: '{amb['resolved_as']}'")
            any_ambig = True
    if not any_ambig:
        pr("    Ninguna")
    pr()

    pr("  VERIFICACIONES:")
    pr("    V1 — Pilares con dimension degenerada:")
    any_col_issue = False
    for dxf_name in DXF_FILES:
        for iss in all_issues[dxf_name]:
            if "Pilar" in iss:
                pr(f"      {dxf_name}: {iss}")
                any_col_issue = True
    if not any_col_issue:
        pr("      Ninguno")
    pr()

    pr("    V2 — Vigas demasiado cortas (< 0.5 m):")
    any_beam_issue = False
    for dxf_name in DXF_FILES:
        for iss in all_issues[dxf_name]:
            if "Viga" in iss:
                pr(f"      {dxf_name}: {iss}")
                any_beam_issue = True
    if not any_beam_issue:
        pr("      Ninguna")
    pr()

    pr("    V3 — Elementos ambiguos / primitivas sin agrupar:")
    any_v3 = False
    for dxf_name in DXF_FILES:
        for iss in all_issues[dxf_name]:
            if "ambigu" in iss or "frag" in iss:
                pr(f"      {dxf_name}: {iss}")
                any_v3 = True
    if not any_v3:
        pr("      Ninguno")
    pr()

    pr("    V4 — Geometria degenerada / demasiado corta:")
    any_v4 = False
    for dxf_name in DXF_FILES:
        for iss in all_issues[dxf_name]:
            if "degenerada" in iss or "muy corta" in iss:
                pr(f"      {dxf_name}: {iss}")
                any_v4 = True
    if not any_v4:
        pr("      Ninguna")
    pr()

    pr("    V4b — Integridad DXF originales:")
    for f in DXF_FILES:
        h = sha256(DXF_DIR / f)
        if h == hashes_before[f]:
            pr(f"      {f}: OK")
        else:
            pr(f"      {f}: MODIFICADO")
    pr()

    save_data = {}
    for dxf_name in DXF_FILES:
        r = all_results[dxf_name]
        save_data[dxf_name] = {
            "beams": [
                {
                    "centerline_m": b["centerline_m"],
                    "length_m": round(b["length_m"], 3),
                    "orientation": b["orientation"],
                }
                for b in r["beams"]
            ],
            "beam_fragments": [
                {
                    "centerline_m": b["centerline_m"],
                    "length_m": round(b["length_m"], 3),
                    "orientation": b["orientation"],
                }
                for b in r["beam_fragments"]
            ],
            "columns": [
                {
                    "center_m": c["center_m"],
                    "width_m": round(c["width_cad"] / CAD_FACTOR, 3),
                    "height_m": round(c["height_cad"] / CAD_FACTOR, 3),
                }
                for c in r["columns"]
            ],
            "walls": [
                {
                    "centerline_m": w["centerline_m"],
                    "length_m": round(w["length_m"], 3),
                    "orientation": w["orientation"],
                    "width_m": round(w.get("width_cad", WALL_THICK_CAD) / CAD_FACTOR, 3),
                }
                for w in r["walls"]
            ],
            "wall_fragments": [
                {
                    "centerline_m": w["centerline_m"],
                    "length_m": round(w["length_m"], 3),
                    "orientation": w["orientation"],
                }
                for w in r["wall_fragments"]
            ],
            "axes": [
                {
                    "label": a["label"],
                    "orientation": a["orientation"],
                    "coord_m": round(a["coord_m"], 3),
                }
                for a in r["axes"]
            ],
            "stats": all_stats[dxf_name],
            "ambiguous_axes": all_ambiguous[dxf_name],
        }

    out_path = PROCESSED_DIR / "structural_geometry_clean.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    pr(f"  Geometria limpia guardada: {out_path.relative_to(ROOT)}")

    pr()
    pr("  Archivos creados/modificados:")
    for dxf_name in DXF_FILES:
        fig_name = f"{dxf_name.replace('.dxf', '')}_depurado.png"
        pr(f"    figures/{fig_name}")
    pr("    figures/comparacion_ejes_depurada.png")
    pr(f"    {out_path.relative_to(ROOT)}")
    pr()
    pr("  DEPURACION GEOMETRICA COMPLETADA.")
    pr("  NO se generaron modelos OpenSees.")


if __name__ == "__main__":
    main()
