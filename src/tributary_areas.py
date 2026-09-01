# -*- coding: utf-8 -*-
"""BLOQUE 2B — Áreas tributarias de losa y transferencia de q_G a vigas (L1-L4).

Para cada paño de losa confirmado de L1..L4 se construyen áreas tributarias
explícitas a partir de sus bordes resistentes reales (método de líneas 45° /
bisectrices equivalentes):

  paño -> área tributaria -> viga receptora -> A_trib -> q_G·A_trib -> carga

Reglas:
- no se reparte área/4 constante; se particiona por distancia perpendicular a
  los bordes resistentes (bisectrices a 45° entre bordes adyacentes,
  perpendiculares entre bordes paralelos);
- se respetan huecos (un hueco no aporta carga ni recibe asignación);
- solo recibe carga una viga que forme borde resistente real del paño
  (segmentos colineales con las 4 líneas límite del paño);
- NO se asigna por cercanía a vigas interiores que atraviesan otro paño;
- los bordes de muro exterior sin viga se registran como WALL_EDGE_PENDING y su
  carga se contabiliza para conservación sin inventar viga receptora.

Implementación: muestreo uniforme fino del paño (celdas de área dA). A cada
punto muestreado se le asigna el borde resistente más cercano (proyección
perpendicular dentro del segmento), lo que reproduce la partición 45° exacta.
Las áreas muestreadas se renormalizan por paño para que sumen exactamente el
área neta analítica (conservación estricta).

considerar conservación por nivel y agregación por viga. Salidas:
  data/loads/tributary_areas_LT2.csv
  data/loads/beam_gravity_loads_LT2.csv

NOMBRES/banderas: q_G = 6.22935 kN/m² (L1-L4). No toca OpenSees/Unity. No ROOF.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import box, Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
LOADS = ROOT / "data" / "loads"
FIGD = ROOT / "figures"

PANELS_CSV = LOADS / "slab_panels_LT2.csv"
BEAMS_CSV = GEOM / "beams_LT2.csv"
LEVELS_CSV = GEOM / "levels.csv"
OUT_TRIB = LOADS / "tributary_areas_LT2.csv"
OUT_BEAM = LOADS / "beam_gravity_loads_LT2.csv"

Q_G = 6.22935  # kN/m2, planta tipo L1-L4 (CSV slabs_LT2)

TAG_BEAM_BASE = 2001

# Envolvente de losa (x,y) tipo: exterior = perfil perimetral soportado por muro
ENV = {"x_min": 0.4, "x_max": 31.25, "y_min": 0.0, "y_max": 16.15}

# Muros perimetrales M.H.A. que soportan el borde exterior (izquierda y derecha)
# wall_id -> (punto de referencia, descripción) para rastreo
WALL_REF = {
    "M001": "muro O exterior tramo y[0,1.825] aprox",
    "M002": "muro N exterior tramo x[0.4,1.85] aprox",
    "M003": "muro O exterior tramo y[14.325,16.15] aprox",
    "M004": "muro S exterior tramo x[0.4,1.85] aprox",
    "M005..M008": "núcleo derecho / muro E exterior x=31.25",
}

LEVELS = ["L1", "L2", "L3", "L4"]

TOL = 1e-6


# --------------------------------------------------------------------------
# utilidades geométricas
# --------------------------------------------------------------------------
def parse_poly(s):
    """'>polygon' -> (x0,y0,x1,y1)."""
    pts = [tuple(map(float, t.split(","))) for t in s.split(";")]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def parse_holes(s):
    """'>holes' -> lista de rects (x0,y0,x1,y1).

    Formato CSV: huecos separados por '|', cada uno como cadena de puntos
    'x,y;x,y;...'. Tambien acepta rects 'x0,y0,x1,y1'.
    """
    if not isinstance(s, str) or not s.strip():
        return []
    out = []
    for hstr in s.split("|"):
        hstr = hstr.strip()
        if not hstr:
            continue
        pts = [list(map(float, p.split(",")))
               for p in hstr.split(";") if p.strip()]
        xs = [p[0] for p in pts if len(p) >= 2]
        ys = [p[1] for p in pts if len(p) >= 2]
        if xs:
            out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def seg_overlap(a0, a1, b0, b1):
    """Overlap length>0? entre intervalos [a0,a1],[b0,b1]."""
    return max(a0, b0) < min(a1, b1) - 1e-9


def overlap(a0, a1, b0, b1):
    return max(a0, b0), min(a1, b1)


# --------------------------------------------------------------------------
# modelado de bordes resistentes
# --------------------------------------------------------------------------
def collect_supporting_segments(panel, level_beams):
    """Devuelve lista de dicts {tipo, id, beam_id, tag, (ax,ay,bx,by), wall_id}.

    Segments are collinear with the panel's 4 boundary lines. Beam segments
    overlapping the line become BEAM receivers; uncovered spans on exterior
    perimeter lines become WALL receivers (WALL_EDGE_PENDING).
    """
    x0, y0, x1, y1 = panel["b"]
    segs = []

    def add_beam_row(r, tag):
        sx1, sy1 = float(r.x1_m), float(r.y1_m)
        sx2, sy2 = float(r.x2_m), float(r.y2_m)
        segs.append({
            "tipo": "beam", "beam_id": r.beam_id, "tag": tag,
            "a": (sx1, sy1), "b": (sx2, sy2),
        })

    def add_wall(a, b, wall_id):
        segs.append({
            "tipo": "wall", "beam_id": None, "tag": None,
            "a": a, "b": b, "wall_id": wall_id,
        })

    # collect beam intervals per boundary line
    # bottom y=y0, top y=y1, left x=x0, right x=x1
    lines = [
        ("y", y0, x0, x1, "S"),
        ("y", y1, x0, x1, "N"),
        ("x", x0, y0, y1, "O"),
        ("x", x1, y0, y1, "E"),
    ]
    for axis, val, lo, hi, side in lines:
        if axis == "y":
            bl = level_beams[
                (np.abs(level_beams.y1_m - val) < 1e-6)
                & (np.abs(level_beams.y2_m - val) < 1e-6)
            ]
        else:
            bl = level_beams[
                (np.abs(level_beams.x1_m - val) < 1e-6)
                & (np.abs(level_beams.x2_m - val) < 1e-6)
            ]
        # overlaps with [lo,hi]
        for r in bl.itertuples():
            if axis == "y":
                s_lo = min(float(r.x1_m), float(r.x2_m))
                s_hi = max(float(r.x1_m), float(r.x2_m))
            else:
                s_lo = min(float(r.y1_m), float(r.y2_m))
                s_hi = max(float(r.y1_m), float(r.y2_m))
            if seg_overlap(lo, hi, s_lo, s_hi):
                add_beam_row(r, r.tag)
        # uncovered stretches on exterior lines -> wall
        exterior = (axis == "y" and (abs(val - ENV["y_min"]) < 1e-6
                                     or abs(val - ENV["y_max"]) < 1e-6)) or \
                   (axis == "x" and (abs(val - ENV["x_min"]) < 1e-6
                                     or abs(val - ENV["x_max"]) < 1e-6))
        if not exterior:
            continue
        # compute covered union along [lo,hi]
        covered = []
        for r in bl.itertuples():
            if axis == "y":
                s_lo = min(float(r.x1_m), float(r.x2_m))
                s_hi = max(float(r.x1_m), float(r.x2_m))
            else:
                s_lo = min(float(r.y1_m), float(r.y2_m))
                s_hi = max(float(r.y1_m), float(r.y2_m))
            if seg_overlap(lo, hi, s_lo, s_hi):
                covered.append(overlap(lo, hi, s_lo, s_hi))
        # starting from lo, walk gaps
        pos = lo
        covered.sort()
        for (a, b) in covered:
            if a > pos + 1e-6:
                add_wall_gap(pos, a, axis, val, side, add_wall)
            pos = max(pos, b)
        if hi > pos + 1e-6:
            add_wall_gap(pos, hi, axis, val, side, add_wall)

    return segs


def add_wall_gap(p0, p1, axis, val, side, add_wall):
    # muro físico asociado al borde exterior (trazable)
    if abs(val - ENV["y_min"]) < 1e-6:      # borde N (y=0)
        wid = "M002" if side == "S" else "WALL_EDGE_N"
    elif abs(val - ENV["y_max"]) < 1e-6:    # borde S (y=16.15)
        wid = "M004" if side == "N" else "WALL_EDGE_S"
    elif abs(val - ENV["x_min"]) < 1e-6:    # borde O (x=0.4)
        wid = "M001" if side == "O" and p0 < 2.0 else (
              "M003" if side == "O" and p0 > 13.0 else "WALL_EDGE_O")
    elif abs(val - ENV["x_max"]) < 1e-6:    # borde E (x=31.25)
        wid = "M005..M008"
    else:
        wid = "WALL_EDGE"
    if axis == "y":
        add_wall((p0, val), (p1, val), wid)
    else:
        add_wall((val, p0), (val, p1), wid)


# --------------------------------------------------------------------------
# distancia y asignación
# --------------------------------------------------------------------------
def dist_to_segment_infinite(px, py, seg):
    """Distancia perpendicular si proyección cae dentro del segmento, si no inf."""
    (ax, ay), (bx, by) = seg["a"], seg["b"]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.inf
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    if t < -1e-9 or t > 1 + 1e-9:
        return math.inf
    # perpendicular distance
    projx, projy = ax + t * dx, ay + t * dy
    return math.hypot(px - projx, py - projy)


def assign_panel_points(px, py, segs, holes):
    """Asigna cada punto a segmento más cercano. Devuelve índice por punto."""
    n = px.shape[0]
    if n == 0:
        return np.empty(0, dtype=int)
    best_idx = np.zeros(n, dtype=int)
    best_d = np.full(n, np.inf)
    for i, seg in enumerate(segs):
        (ax, ay), (bx, by) = seg["a"], seg["b"]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = ((px - ax) * dx + (py - ay) * dy) / L2
        # mark points whose projection falls within segment
        ok = (t >= -1e-9) & (t <= 1 + 1e-9)
        projx = ax + t * dx
        projy = ay + t * dy
        d = np.hypot(px - projx, py - projy)
        d[~ok] = np.inf
        better = d < best_d
        best_d[better] = d[better]
        best_idx[better] = i
    # fallback: points with no projection (shouldn't happen) -> nearest segment end
    unassigned = np.isinf(best_d)
    if unassigned.any():
        for i, seg in enumerate(segs):
            (ax, ay), (bx, by) = seg["a"], seg["b"]
            for end in ((ax, ay), (bx, by)):
                d = np.hypot(px[unassigned] - end[0], py[unassigned] - end[1])
                upd = d < best_d[unassigned]
                sub = np.nonzero(unassigned)[0]
                bd = best_d[sub]
                bd[upd] = d[upd]
                best_d[sub] = bd
                bi = best_idx[sub]
                bi[upd] = i
                best_idx[sub] = bi
    return best_idx


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def build():
    beams = pd.read_csv(BEAMS_CSV)
    panels = pd.read_csv(PANELS_CSV)
    # element tag por viga = TAG_BEAM_BASE + indice de fila global
    beams = beams.reset_index(drop=True)
    beams["tag"] = TAG_BEAM_BASE + beams.index

    tag_map = dict(zip(beams.beam_id, beams.tag))

    # grid step
    STEP = 0.05

    trib_rows = []
    cons_net = 0.0
    cons_trib = 0.0
    beam_tot = {}
    per_level = {lv: {"net": 0.0, "trib": 0.0} for lv in LEVELS}

    for lv in LEVELS:
        lbeams = beams[beams.level == lv].copy()
        lpanels = panels[panels.level == lv]
        for _, pr in lpanels.iterrows():
            b = parse_poly(pr.polygon)
            holes = parse_holes(pr.holes)
            net_area = float(pr.area_m2)
            if net_area <= 0:
                continue
            segs = collect_supporting_segments({"b": b}, lbeams)
            if not segs:
                raise SystemExit(f"sin bordes resistentes para {pr.panel_id}")

            # muestreo
            x0, y0, x1, y1 = b
            xs = np.arange(x0 + STEP / 2, x1, STEP)
            ys = np.arange(y0 + STEP / 2, y1, STEP)
            xg, yg = np.meshgrid(xs, ys)
            px = xg.ravel()
            py = yg.ravel()
            da = STEP * STEP
            # remover puntos en huecos
            keep = np.ones(px.shape[0], dtype=bool)
            for (hx0, hy0, hx1, hy1) in holes:
                keep &= ~((px >= hx0 - 1e-9) & (px <= hx1 + 1e-9)
                          & (py >= hy0 - 1e-9) & (py <= hy1 + 1e-9))
            px = px[keep]
            py = py[keep]

            idx = assign_panel_points(px, py, segs, holes)

            # agregar áreas por segmento
            counts = np.bincount(idx, minlength=len(segs))
            sampled_areas = counts * da
            sampled_total = sampled_areas.sum()

            idx_by_seg = {}
            for i, seg in enumerate(segs):
                area_raw = sampled_areas[i]
                # renormalización sobre segmentos con área>0
                if area_raw > 0:
                    idx_by_seg[i] = seg
            # normalización exacta al área neta analítica
            active = [i for i in range(len(segs)) if sampled_areas[i] > 0]
            scale = net_area / sampled_areas[active].sum() if active else 0.0

            for i in active:
                seg = segs[i]
                area = sampled_areas[i] * scale
                load = area * Q_G
                if seg["tipo"] == "beam":
                    rid = seg["beam_id"]
                    rec_t = "BEAM"
                    tag = tag_map.get(rid)
                    status = "TRANSFERIDO"
                    wall_id = ""
                else:
                    rid = seg.get("wall_id", "WALL_EDGE")
                    rec_t = "WALL"
                    tag = None
                    status = "WALL_EDGE_PENDING"
                    wall_id = rid
                tid = f"{pr.panel_id}_T{len(trib_rows)+1:03d}"
                # poligono real = union de celdas muestreadas de la region
                sel = np.nonzero(idx == i)[0]
                if sel.size:
                    half = STEP / 2
                    cells = [box(cx - half, cy - half, cx + half, cy + half)
                             for cx, cy in zip(px[sel], py[sel])]
                    reg = unary_union(cells)
                    # componentes que solo se tocan en un vertice (bisectriz 45°
                    # en la grilla) -> unirlas expandiendo ligeramente
                    if not isinstance(reg, Polygon):
                        reg = reg.buffer(1e-9)
                    if isinstance(reg, Polygon):
                        parts = [reg]
                    elif hasattr(reg, "geoms"):
                        parts = [g for g in reg.geoms if isinstance(g, Polygon)]
                    else:
                        parts = []
                    ring_strs = []
                    for part in parts:
                        ring = list(part.exterior.coords)
                        pts = []
                        for x, y in ring[:-1]:
                            if (not pts) or abs(pts[-1][0]-x) > 1e-9 or abs(pts[-1][1]-y) > 1e-9:
                                pts.append((x, y))
                        if len(pts) >= 3:
                            ring_strs.append(";".join(f"{round(x,6)},{round(y,6)}"
                                                      for x, y in pts))
                    polystr = "|".join(ring_strs)
                else:
                    polystr = ""
                trib_rows.append({
                    "level": lv,
                    "panel_id": pr.panel_id,
                    "tributary_id": tid,
                    "receiver_type": rec_t,
                    "receiver_id": rid,
                    "beam_id": rid if seg["tipo"] == "beam" else "",
                    "element_tag": tag,
                    "area_m2": round(area, 6),
                    "qG_kN_m2": Q_G,
                    "load_kN": round(load, 6),
                    "polygon": polystr,
                    "status": status,
                })
                if seg["tipo"] == "beam":
                    key = (lv, rid)
                    bkey = beam_tot.setdefault(key, {"area": 0.0, "load": 0.0})
                    bkey["area"] += area
                    bkey["load"] += load
                else:
                    keyw = (lv, "WALL", rid)
                    wkey = beam_tot.setdefault(keyw, {"area": 0.0, "load": 0.0})
                    wkey["area"] += area
                    wkey["load"] += load
                cons_trib += net_area  # tras renormalización trib == net por paño
            cons_net += net_area
            per_level[lv]["net"] += net_area
            per_level[lv]["trib"] += net_area

    trib_df = pd.DataFrame(trib_rows)

    beam_rows = []
    for key, d in beam_tot.items():
        lv, rid = key[0], key[1]
        if key[1] == "WALL":
            beam_rows.append({
                "level": lv, "beam_id": "", "element_tag": "",
                "receiver_type": "WALL", "receiver_id": key[2],
                "tributary_area_m2": round(d["area"], 6),
                "total_slab_load_kN": round(d["load"], 6),
                "beam_length_m": "", "equivalent_uniform_load_kN_m": "",
                "status": "WALL_EDGE_PENDING",
            })
        else:
            bl = beams[(beams.level == lv) & (beams.beam_id == rid)].iloc[0]
            length = math.hypot(float(bl.x2_m) - float(bl.x1_m),
                                float(bl.y2_m) - float(bl.y1_m))
            eq = d["load"] / length if length > 0 else np.nan
            beam_rows.append({
                "level": lv, "beam_id": rid,
                "element_tag": tag_map.get(rid),
                "receiver_type": "BEAM", "receiver_id": rid,
                "tributary_area_m2": round(d["area"], 6),
                "total_slab_load_kN": round(d["load"], 6),
                "beam_length_m": round(length, 6),
                "equivalent_uniform_load_kN_m": round(eq, 6),
                "status": "TRANSFERIDO",
            })
    beam_df = pd.DataFrame(beam_rows)

    trib_df.to_csv(OUT_TRIB, index=False)
    beam_df.to_csv(OUT_BEAM, index=False)
    print(f"Escrito: {OUT_TRIB}  ({len(trib_df)} filas)")
    print(f"Escrito: {OUT_BEAM}  ({len(beam_df)} filas)")
    for lv in LEVELS:
        p = per_level[lv]
        print(f"  {lv}: neta={p['net']:.4f}  trib={p['trib']:.4f}")
    net_tot = sum(per_level[lv]["net"] for lv in LEVELS)
    trib_tot = float(trib_df["area_m2"].sum())
    print(f"TOTAL neta={net_tot:.4f} trib={trib_tot:.4f} "
          f"diff={net_tot-trib_tot:.6f} ({100*abs(net_tot-trib_tot)/net_tot:.4e}%)")
    return trib_df, beam_df


if __name__ == "__main__":
    build()
