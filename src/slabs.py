"""
Registro de losas por nivel (P1..P4) con area y carga q_G.

Metodo de contorno (intencionalmente simple):
  - la geometria de losa de planos (capa RLE-LOSA) solo produce paneles
    parciales/escasos (~1.3 m2 por nivel), NO huellas completas de piso;
  - se genera entonces, con la GEOMETRIA ESTRUCTURAL v2, el poligono de cada
    nivel como el CASCO CONVEXO de la reticula de pilares de ese nivel:
      * P1 (16 pilares, faltan los (40,-9.15)/(40,-0.25)) -> contorno distinto,
        660.0 m2 (hay una muesca por falta de soporte, documentada);
      * P2/P3/P4 (18 pilares) -> rectangulo 45 x 16.15 = 726.75 m2.
  - NO se asume que los cuatro niveles tienen igual superficie.
  - status = "PROVISIONAL" (contorno por reticula de pilares hasta disponer de
    la planta arquitectonica de losa completa).

Campos por losa:
  slab_id, level, polygon, area_m2, thickness, self_weight_kN_m2,
  finishes_kN_m2, q_G_kN_m2, status, source
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from structure_params import SLAB_THICKNESS, SLAB_DEAD_LOAD, SLAB_FINISHES_KN_M2, SLAB_QG_KN_M2
from ops_model import load_aligned

FRAME_LEVELS = ("P1", "P2", "P3", "P4")
GRID = 0.25


def poly_area(verts):
    a = 0.0
    n = len(verts)
    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 1:
        return list(pts)
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def build_slabs(data, frame_levels=FRAME_LEVELS):
    """Poligono de losa (casco convexo de pilares) por nivel + q_G."""
    slabs = []
    by_level = {}
    for lvl in frame_levels:
        pts = [(round(n["x"], 3), round(n["y"], 3)) for n in data["nodes"]
               if n["level"] == lvl]
        hull = convex_hull(pts)
        if len(hull) < 3 or poly_area(hull) <= 1e-9:
            by_level[lvl] = None
            continue
        area = poly_area(hull)
        slab = {
            "slab_id": f"SL-{lvl}-01",
            "level": lvl,
            "polygon": [[x, y] for x, y in hull],
            "area_m2": round(area, 3),
            "thickness_m": SLAB_THICKNESS,
            "self_weight_kN_m2": SLAB_DEAD_LOAD,
            "finishes_kN_m2": SLAB_FINISHES_KN_M2,
            "q_G_kN_m2": SLAB_QG_KN_M2,
            "status": "PROVISIONAL",
            "source": "casco convexo reticula pilares v2 (losas DXF parciales)",
        }
        slabs.append(slab)
        by_level[lvl] = slab
    return slabs, by_level


if __name__ == "__main__":
    data = load_aligned()
    slabs, _ = build_slabs(data)
    for s in slabs:
        print(s["slab_id"], s["level"], f"A={s['area_m2']:.2f} m2",
              f"qG={s['q_G_kN_m2']:.2f} kN/m2", s["status"])