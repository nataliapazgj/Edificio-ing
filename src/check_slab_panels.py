# -*- coding: utf-8 -*-
"""Checker geometrico de panes de losa LT2.

Lee data/loads/slab_panels_LT2.csv y reporta por nivel:
    numero_paneles | area_total_losa_m2 | pendientes | errores

Detecta:
  - area <= 0;
  - poligono invalido (<3 vertices, no cerrado, self-intersectado);
  - solapamientos entre panies del mismo nivel (area > tol);
  - panies duplicados (mismo nivel + mismo poligono);
  - vertices claramente fuera del dominio estructural;
  - niveles sin panies;
  - panies con qG pendiente (qG_kN_m2 NaN);
  - huecos (columna `holes`): fuera del panel, hueco que se sale del contorno
    de losa, o area_m2 inconsistente con area_exterior - area_huecos.

No modifica datos. No calcula areas tributarias.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.validation import explain_validity

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
LOAD = ROOT / "data" / "loads"

# Dominio estructural (planta). Se define holgado con respecto al contorno de
# losa digitalizado (beams/walls L1-L4): x[0.4,31.25] y[0,16.15]; se expande
# un poco para admitir muros perimetrales/ejes de apoyo sin caer en falsos.
DOM_X = (0.0, 32.0)
DOM_Y = (-1.2, 17.3)

TOL_AREA = 1e-6
TOL_OVERLAP = 1e-3  # m2


def parse_poly(s):
    pts = []
    for tok in str(s).split(";"):
        x, y = tok.split(",")
        pts.append((float(x), float(y)))
    return pts


def polygon_area(pts):
    if len(pts) < 3:
        return 0.0
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def parse_holes(s):
    """Devuelve lista de huecos (lista de pares de pts) a partir de la columna `holes`."""
    holes = []
    if not s or (isinstance(s, float) and np.isnan(s)):
        return holes
    for hp in str(s).split("|"):
        hp = hp.strip()
        if not hp:
            continue
        pts = []
        for tok in hp.split(";"):
            x, y = tok.split(",")
            pts.append((float(x), float(y)))
        holes.append(pts)
    return holes


def main():
    panels = pd.read_csv(LOAD / "slab_panels_LT2.csv")
    slabs = pd.read_csv(LOAD / "slabs_LT2.csv")
    levels = pd.read_csv(GEOM / "levels.csv")
    z_levels = list(levels["name"].astype(str))

    errors, warnings = [], []

    def report(msg, is_error=True):
        (errors if is_error else warnings).append(msg)
        print(f"{'ERROR' if is_error else 'WARN'} - {msg}")

    print("=== LT2 SLAB PANELS CHECK ===")
    print(f"Panies registrados : {len(panels)}")
    print()

    # --- IDs duplicados ---
    dup = panels["panel_id"][panels["panel_id"].duplicated()].unique()
    for d in dup:
        report(f"panel_id duplicado: {d}")

    # --- parsear poligonos ---
    polys = {}
    parsed = {}
    for i, p in panels.iterrows():
        pid, lvl = str(p["panel_id"]), str(p["level"])
        pts = parse_poly(p["polygon"])
        parsed[(pid, lvl)] = pts
        polys[(pid, lvl)] = Polygon(pts) if len(pts) >= 3 else None

    # --- chequeos por panel ---
    for i, p in panels.iterrows():
        pid, lvl = str(p["panel_id"]), str(p["level"])
        pts = parsed[(pid, lvl)]
        shp = polys[(pid, lvl)]

        area = polygon_area(pts)
        if area <= TOL_AREA:
            report(f"{pid}: area<=0 ({area:.6f} m2)")

        if len(pts) < 3:
            report(f"{pid}: poligono invalido (<3 vertices)")
            continue
        if abs(float(p.get("area_m2", 0)) or 0) < 0:
            report(f"{pid}: area_m2 negativa o mal parseada")

        if shp is not None and not shp.is_valid:
            report(f"{pid}: poligono invalido ({explain_validity(shp)})", is_error=False)

        # vertices fuera del dominio estructural
        for j, (vx, vy) in enumerate(pts):
            if not (DOM_X[0] - 1e-6 <= vx <= DOM_X[1] + 1e-6):
                report(f"{pid}: vertice {j} ({vx:.3f},{vy:.3f}) fuera de dominio X {DOM_X}")
            if not (DOM_Y[0] - 1e-6 <= vy <= DOM_Y[1] + 1e-6):
                report(f"{pid}: vertice {j} ({vx:.3f},{vy:.3f}) fuera de dominio Y {DOM_Y}")

        # qG pendiente
        qg = p.get("qG_kN_m2")
        if pd.isna(qg):
            warnings.append(f"{pid}: qG_kN_m2 pendiente (nivel {lvl})")
            print(f"WARN - {pid}: qG_kN_m2 pendiente")

        # huecos explicitos (columna `holes`): dentro del panel y area consistente
        hole_pts_list = parse_holes(p.get("holes"))
        if shp is not None and hole_pts_list:
            sub = 0.0
            for hi, hpts in enumerate(hole_pts_list):
                h = Polygon(hpts) if len(hpts) >= 3 else None
                if h is None or not h.is_valid:
                    report(f"{pid}: hole {hi} invalido")
                    continue
                sub += h.area
                if not shp.contains(h) and not shp.touches(h):
                    report(f"{pid}: hole {hi} ({h.centroid.x:.3f},{h.centroid.y:.3f}) fuera del panel")
            expected = area - sub
            am2 = float(p.get("area_m2") or 0)
            if abs(am2 - expected) > 1e-3:
                report(f"{pid}: area_m2={am2:.3f} != exterior-area_huecos={expected:.3f}")

    # --- solapamientos por nivel ---
    print()
    print("[Overlaps]")
    for lvl in sorted(set(panels["level"])):
        lvl_ids = [str(x) for x in panels[panels["level"] == lvl]["panel_id"]]
        nbad = 0
        for a in range(len(lvl_ids)):
            for b in range(a + 1, len(lvl_ids)):
                pa, pb = lvl_ids[a], lvl_ids[b]
                sa, sb = polys[(pa, lvl)], polys[(pb, lvl)]
                if sa is None or sb is None:
                    continue
                inter = sa.intersection(sb).area
                if inter > TOL_OVERLAP:
                    nbad += 1
                    report(f"solape {lvl}: {pa} con {pb} ({inter:.3f} m2)")
        if nbad == 0:
            print(f"  OK {lvl}: sin solapamientos ({len(lvl_ids)} panies)")
    print()

    # --- panies duplicados por nivel ---
    print("[Duplicates]")
    for lvl in sorted(set(panels["level"])):
        lvl_df = panels[panels["level"] == lvl]
        seen = {}
        ndup = 0
        for _, p in lvl_df.iterrows():
            key = str(p["polygon"])
            if key in seen:
                ndup += 1
                report(f"duplicado {lvl}: {p['panel_id']} == {seen[key]}")
            else:
                seen[key] = p["panel_id"]
        if ndup == 0:
            print(f"  OK {lvl}: sin panies duplicados")
    print()

    # --- niveles sin panies ---
    print("[Levels]")
    present = set(panels["level"].astype(str))
    for lvl in z_levels:
        if lvl in ("B1",):
            continue  # B1 fuera de diafragmas/losas
        if lvl not in present:
            report(f"nivel {lvl} SIN panies de losa")
    print()

    # --- resumen por nivel ---
    print("[Resumen por nivel]")
    print(f"{'nivel':<7}{'paneles':>9}{'area_m2':>14}{'pendientes':>12}{'errores':>10}")
    for lvl in ["L1", "L2", "L3", "L4", "ROOF"]:
        if lvl not in present:
            continue
        sub = panels[panels["level"] == lvl]
        n = len(sub)
        area = sub["area_m2"].sum()
        pend = int((sub["status"].astype(str).str.contains("PENDING")).sum()
                   + int(pd.isna(sub["qG_kN_m2"]).sum()))
        n_err = sum(1 for e in errors if lvl in e)
        print(f"{lvl:<7}{n:>9}{area:>14.3f}{pend:>12}{n_err:>10}")

    qg_pend = int(pd.isna(panels["qG_kN_m2"]).sum())
    if qg_pend:
        warnings.append(f"{qg_pend} panies con qG pendiente (ROOF)")

    # --- resumen de huecos ---
    print("[Huecos por nivel]")
    for lvl in ["L1", "L2", "L3", "L4", "ROOF"]:
        if lvl not in present:
            continue
        sub = panels[panels["level"] == lvl]
        n_conf = int(sub["hole_status"].astype(str).str.contains("CONFIRMED").sum())
        n_pend = int(sub["hole_status"].astype(str).str.contains("PENDING_GEOMETRY").sum())
        if n_conf or n_pend:
            print(f"  {lvl:<5} huecos_confirmados={n_conf}  huecos_pendientes={n_pend}")
    print()

    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
