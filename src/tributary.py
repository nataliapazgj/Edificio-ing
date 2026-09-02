"""
Areas tributarias EXPLICITAS de losa -> vigas receptoras (v2).

Reglas:
  - la losa NO se modela FE; su carga q_G[kN/m2] se reparte a las vigas
    mediante AREAS TRIBUTARIAS CON POLIGONO EXPLICITO;
  - dentro del poligono de losa de cada nivel se muestrea una malla fina
    (dx=dy=0.25 m); cada punto se asigna a la VIGA ORIGINAL mas cercana
    (distancia euclidiana al segmento) => subdivido del slab en regiones,
    lo que equivale al criterio de bisectriz / 45 grados para vanos;
  - la region de cada viga se reconstruye como poligono ortogonal explicito
    (contorno de las celdas asignadas);
  - el area tributaria de cada viga original se PROMEA entre sus elementos
    de red v2 (beam_elementTag) proporcional a su longitud;
  - slab_load_kN = area_trib * q_G ;  equivalent_line_load_kN_m =
    slab_load_kN / longitud_viga_receptora (constante a lo largo de la viga).

Metricas por nivel (seccion 'VERIFICACION POR PISO'):
  A_losa, A_trib, error_area, carga_esperada=A_losa*q_G,
  carga_transferida=sum(slab_load), error_carga.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from structure_params import SLAB_QG_KN_M2
from slabs import build_slabs, poly_area, GRID
from ops_model import load_aligned, build_ops_model


# ───────────────────────────────────────────────────────────────────────────
# Geometria util
# ───────────────────────────────────────────────────────────────────────────

def point_in_poly(pt, verts):
    x, y = pt
    inside = False
    n = len(verts)
    j = n - 1
    for i in range(n):
        xi, yi = verts[i]
        xj, yj = verts[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def seg_distance(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / L2
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy)


def region_outline(cells):
    """Contorno ortogonal (lista de vertices) de un conjunto de celdas (ix,iy)."""
    ed = {}          # (a,b) directed edge -> bool (True=boundary, False=cancelled)
    for (ix, iy) in cells:
        es = [((ix, iy), (ix + 1, iy)),
              ((ix + 1, iy), (ix + 1, iy + 1)),
              ((ix + 1, iy + 1), (ix, iy + 1)),
              ((ix, iy + 1), (ix, iy))]
        for (a, b) in es:
            rev = (b, a)
            if ed.get(rev):
                ed[rev] = False
            else:
                ed[(a, b)] = True
    edges = [e for e, v in ed.items() if v]
    if not edges:
        return None
    start = edges[0][0]
    cur = edges[0][1]
    pts = [start, cur]
    remain = list(range(1, len(edges)))
    while cur != start and remain:
        nxt = None
        ni = None
        for i in remain:
            a, b = edges[i]
            if a == cur:
                nxt, ni = b, i
                break
            if b == cur:
                nxt, ni = a, i
                break
        if nxt is None:
            break
        pts.append(nxt)
        cur = nxt
        remain.remove(ni)
    return pts


# ───────────────────────────────────────────────────────────────────────────
# Calculo
# ───────────────────────────────────────────────────────────────────────────

def compute_tributary(data, summary, by_level_slabs=None):
    """
    Devuelve dict:
      receivers  : {level: [ {orig, x1,y1,x2,y2, area_m2, polygon, slab_load_kN,
                             elements:[{tag,len,area_m2,slab_load_kN,
                                        equivalent_line_load_kN_m,polygon}]} ]}
      beam_load  : {tag: slab_load_kN}   (para aplicar en gravedad)
      per_level  : verif. por piso (A_losa, A_trib, errores, cargas)
    """
    if by_level_slabs is None:
        _, by_level_slabs = build_slabs(data)

    frame = ("P1", "P2", "P3", "P4")
    # elementos de viga v2 agrupados por (level, orig)
    elems_by_orig = {}
    for e in summary["beam_elements"]:
        elems_by_orig.setdefault((e["level"], e["orig"]), []).append(e)

    receivers = {}
    beam_load = {}
    per_level = {}

    for lvl in frame:
        slab = by_level_slabs.get(lvl)
        if slab is None:
            per_level[lvl] = {"A_losa": 0.0, "A_trib": 0.0, "error_area": None,
                              "carga_esperada": 0.0, "carga_transferida": 0.0,
                              "error_carga": None, "status": "sin_losa"}
            continue

        poly = [(p[0], p[1]) for p in slab["polygon"]]
        qG = slab["q_G_kN_m2"]
        bems = [b for b in data["beams"]
                if b["level"] == lvl and b["status"] == "high-confidence"]

        # malla de puntos dentro del poligono
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        cells = {}            # (ix,iy) -> segment index
        cell_area = GRID * GRID
        ix = 0
        x = xmin
        while x < xmax:
            iy = 0
            y = ymin
            while y < ymax:
                if point_in_poly((x + GRID / 2.0, y + GRID / 2.0), poly):
                    cells[(ix, iy)] = None
                iy += 1
                y += GRID
            ix += 1
            x += GRID

        # asignacion a la viga original mas cercana
        reg_cells = [[] for _ in bems]
        for (cx, cy) in cells:
            if len(bems) == 0:
                break
            best, bd = 0, float("inf")
            px = xmin + (cx + 0.5) * GRID
            py = ymin + (cy + 0.5) * GRID
            for i, b in enumerate(bems):
                d = seg_distance(px, py, b["x1"], b["y1"], b["x2"], b["y2"])
                if d < bd:
                    bd, best = d, i
            reg_cells[best].append((cx, cy))

        lvl_recs = []
        sum_trib = 0.0
        sum_load = 0.0
        for i, b in enumerate(bems):
            cells_i = reg_cells[i]
            area = len(cells_i) * cell_area
            sum_trib += area
            L_orig = b["length_m"]
            load = area * qG
            sum_load += load
            outline = region_outline(cells_i) if cells_i else None
            if outline:
                poly_m = [[xmin + vx * GRID, ymin + vy * GRID] for (vx, vy) in outline]
            else:
                poly_m = []
            line_load = (load / L_orig) if (L_orig > 0 and area > 0) else 0.0

            els = elems_by_orig.get((lvl, i), [])
            L_el_sum = sum(e["length"] for e in els)
            elements = []
            for e in els:
                frac = (e["length"] / L_el_sum) if L_el_sum > 0 else 0.0
                a_e = area * frac
                p_e = load * frac
                elements.append({
                    "tag": e["tag"],
                    "length_m": e["length"],
                    "tributary_area_m2": round(a_e, 4),
                    "slab_load_kN": round(p_e, 3),
                    "equivalent_line_load_kN_m": round(line_load, 4),
                    "polygon": poly_m,
                })
                if a_e > 0 or p_e > 0:
                    beam_load[e["tag"]] = round(p_e, 3)
            lvl_recs.append({
                "orig": i,
                "x1": b["x1"], "y1": b["y1"], "x2": b["x2"], "y2": b["y2"],
                "area_m2": round(area, 4),
                "polygon": poly_m,
                "slab_load_kN": round(load, 3),
                "elements": elements,
            })
        receivers[lvl] = lvl_recs

        A_losa = slab["area_m2"]
        carga_esperada = A_losa * qG
        # cargas por NODO? no: por viga; consistency de areas con sum over beams
        err_area = abs(sum_trib - A_losa) / A_losa if A_losa > 0 else None
        err_carga = (abs(sum_load - carga_esperada) / carga_esperada
                     if carga_esperada > 0 else None)
        per_level[lvl] = {
            "A_losa": round(A_losa, 2),
            "A_trib": round(sum_trib, 2),
            "error_area": err_area,
            "carga_esperada": round(carga_esperada, 2),
            "carga_transferida": round(sum_load, 2),
            "error_carga": err_carga,
            "q_G_kN_m2": qG,
        }

    return {"receivers": receivers, "beam_load": beam_load, "per_level": per_level,
            "slabs": by_level_slabs}


if __name__ == "__main__":
    data = load_aligned()
    summary = build_ops_model(data)
    out = compute_tributary(data, summary)
    for lvl, v in out["per_level"].items():
        print(lvl, v)