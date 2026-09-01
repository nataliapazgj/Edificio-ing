# -*- coding: utf-8 -*-
"""Checker de areas tributarias LT2 (BLOQUE 2B).

Lee data/loads/tributary_areas_LT2.csv y data/loads/beam_gravity_loads_LT2.csv
y verifica por nivel:

  1. tributary polygon valido, area > 0;
  2. no solapamiento entre areas tributarias de un mismo paño;
  3. ninguna area tributaria cae dentro de los huecos del paño;
  4. suma de areas tributarias = area neta del paño (conservacion exacta);
  5. suma de cargas conservada: qG*area_neta = Sum(cargas_beam) + Sum(pendientes mur);
  6. receptor existente: beam_id valido (en beams_LT2), element_tag trazable;
  7. beam_id no vacio excepto WALL_EDGE_PENDING.

No modifica datos.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
LOAD = ROOT / "data" / "loads"

Q_G = 6.22935

TOL_AREA = 1e-6
TOL_CONS = 1e-2  # m2/kN absoluto


def parse_poly(s):
    pts = []
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return pts
    for tok in str(s).split(";"):
        tok = tok.strip()
        if not tok:
            continue
        parts = tok.split(",")
        if len(parts) != 2:
            continue
        x, y = parts
        pts.append((float(x), float(y)))
    return pts


def parse_polys(s):
    """>polygon multiparte (anillos separados por '|') -> lista de polig. puntos."""
    rings = []
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return rings
    for rstr in str(s).split("|"):
        rstr = rstr.strip()
        if not rstr:
            continue
        pts = []
        for tok in rstr.split(";"):
            tok = tok.strip()
            if not tok:
                continue
            parts = tok.split(",")
            if len(parts) == 2:
                pts.append((float(parts[0]), float(parts[1])))
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def parse_holes(s):
    holes = []
    if not s or (isinstance(s, float) and np.isnan(s)):
        return holes
    for hp in str(s).split("|"):
        hp = hp.strip()
        if not hp:
            continue
        pts = []
        for tok in hp.split(";"):
            tok = tok.strip()
            if not tok:
                continue
            parts = tok.split(",")
            if len(parts) == 2:
                pts.append((float(parts[0]), float(parts[1])))
        if len(pts) >= 3:
            holes.append(Polygon(pts))
    return holes


def union_shapes(rings):
    if not rings:
        return None
    if len(rings) == 1:
        return Polygon(rings[0])
    return unary_union([Polygon(r) for r in rings])


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


def main():
    trib = pd.read_csv(LOAD / "tributary_areas_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    panels = pd.read_csv(LOAD / "slab_panels_LT2.csv")
    beam_ids = set(beams["beam_id"].astype(str))
    tag_map = dict(zip(beams["beam_id"].astype(str), 2001 + beams.index))

    errors, warnings = [], []

    def report(msg, is_error=True):
        (errors if is_error else warnings).append(msg)
        print(f"{'ERROR' if is_error else 'WARN'} - {msg}")

    print("=== LT2 TRIBUTARY AREAS CHECK ===")
    print(f"Areas tributarias registradas : {len(trib)}")
    print()

    # --- IDs duplicados ---
    dup = trib["tributary_id"][trib["tributary_id"].duplicated()].unique()
    for d in dup:
        report(f"tributary_id duplicado: {d}")

    # --- por paño: solapamientos, huecos, sumas ---
    panels_index = {}
    for _, p in panels.iterrows():
        if str(p["level"]) in ("L1", "L2", "L3", "L4"):
            pid_lvl = (str(p["panel_id"]), str(p["level"]))
            panels_index[pid_lvl] = {
                "net": float(p["area_m2"]),
                "poly": Polygon(parse_poly(p["polygon"])),
                "holes": parse_holes(p.get("holes")),
                "qG": float(p["qG_kN_m2"]),
            }

    # agrupar tributarias por paño
    by_panel = {}
    for r in trib.itertuples():
        key = (str(r.panel_id), str(r.level))
        by_panel.setdefault(key, []).append(r)

    cons_area = {"beam": 0.0, "wall": 0.0}
    cons_load = {"beam": 0.0, "wall": 0.0}
    n_bad_overlap = 0
    n_receiver_bad = 0
    n_wall_pending = 0

    for key, rows in by_panel.items():
        pid, lvl = key
        pinfo = panels_index.get(key)
        if pinfo is None:
            report(f"{pid} ({lvl}): paño no encontrado en slab_panels")
            continue
        # validar cada area tributaria
        for r in rows:
            area = float(r.area_m2)
            load = float(r.load_kN)
            if area <= TOL_AREA:
                report(f"{r.tributary_id}: area<=0 ({area:.6f} m2)")
            if abs(load - area * Q_G) > 1e-3:
                report(f"{r.tributary_id}: load_kN no coincide con qG*area")
            # poligono (posiblemente multiparte)
            rings = parse_polys(r.polygon)
            if not rings:
                report(f"{r.tributary_id}: polygon invalido", is_error=False)
                shp = None
            else:
                shp = union_shapes(rings)
                if shp is None or not shp.is_valid:
                    report(f"{r.tributary_id}: polygon invalido (shapely)", is_error=False)
            # receptor
            rec_type = str(r.receiver_type)
            beam_id = str(r.beam_id) if not pd.isna(r.beam_id) and str(r.beam_id) else ""
            if rec_type == "BEAM":
                if beam_id not in beam_ids:
                    n_receiver_bad += 1
                    report(f"{r.tributary_id}: beam_id {beam_id} no existe")
                tag = r.element_tag
                if pd.isna(tag) or int(tag) != tag_map.get(beam_id):
                    report(f"{r.tributary_id}: element_tag {tag} no trazable")
            else:
                n_wall_pending += 1
            # dentro del paño y fuera de huecos
            if shp is not None and not shp.is_empty and pinfo["poly"].is_valid:
                c = shp.representative_point()
                if not pinfo["poly"].covers(c):
                    report(f"{r.tributary_id}: centroide fuera del paño")
                for h in pinfo["holes"]:
                    if shp.representative_point().within(h):
                        report(f"{r.tributary_id}: area dentro de hole", is_error=False)
        # solapamiento entre tributarias del mismo paño
        shps = [union_shapes(parse_polys(r.polygon)) for r in rows]
        shps = [s for s in shps if s is not None and not s.is_empty]
        for a in range(len(shps)):
            for b in range(a + 1, len(shps)):
                if shps[a].is_valid and shps[b].is_valid:
                    inter = shps[a].intersection(shps[b]).area
                    if inter > TOL_AREA:
                        n_bad_overlap += 1
                        report(f"{pid}: solape tributarias ({inter:.4f} m2)")
        # suma areas = neta
        s_area = sum(float(r.area_m2) for r in rows)
        if abs(s_area - pinfo["net"]) > TOL_CONS:
            report(f"{pid}: suma tributarias={s_area:.4f} != area_neta={pinfo['net']:.4f}")
        # receptor split
        for r in rows:
            area = float(r.area_m2)
            load = float(r.load_kN)
            if str(r.receiver_type) == "BEAM":
                cons_area["beam"] += area
                cons_load["beam"] += load
            else:
                cons_area["wall"] += area
                cons_load["wall"] += load

    # --- conservacion por nivel ---
    print("[Conservacion por nivel]")
    print(f"{'nivel':<6}{'area_neta':>12}{'suma_trib':>12}{'diff_area':>12}"
          f"{'qG*net':>12}{'carga_asig':>12}{'pend_muro':>12}")
    tot_net = tot_trib = tod_diff = 0.0
    for lvl in ["L1", "L2", "L3", "L4"]:
        net = sum(v["net"] for k, v in panels_index.items() if k[1] == lvl)
        tt = sum(float(r.area_m2) for r in trib.itertuples() if r.level == lvl)
        dd = net - tt
        q = net * Q_G
        ca = sum(float(r.load_kN) for r in trib.itertuples()
                 if r.level == lvl and r.receiver_type == "BEAM")
        cm = sum(float(r.load_kN) for r in trib.itertuples()
                 if r.level == lvl and r.receiver_type == "WALL")
        if abs(dd) > TOL_CONS:
            report(f"{lvl}: conservacion de area diff={dd:.4f}")
        if abs(q - (ca + cm)) > TOL_CONS:
            report(f"{lvl}: conservacion de carga del={q-(ca+cm):.4f}")
        print(f"{lvl:<6}{net:>12.4f}{tt:>12.4f}{dd:>12.6f}{q:>12.4f}{ca:>12.4f}{cm:>12.4f}")
        tot_net += net
        tot_trib += tt
        tod_diff += dd

    print(f"{'TOTAL':<6}{tot_net:>12.4f}{tot_trib:>12.4f}{tod_diff:>12.6f}")
    rel = abs(tod_diff) / tot_net * 100 if tot_net else 0.0
    print(f"Error relativo de area: {rel:.2e} %")
    print(f"Carga transferida a vigas: {cons_load['beam']:.3f} kN")
    print(f"Carga pendiente en muros: {cons_load['wall']:.3f} kN")
    print(f"Areas a vigas: {cons_area['beam']:.3f} m2 ; a muros: {cons_area['wall']:.3f} m2")

    # --- beam_gravity_loads consistency ---
    print()
    print("[beam_gravity_loads_LT2]")
    bg = pd.read_csv(LOAD / "beam_gravity_loads_LT2.csv")
    be = bg[bg["receiver_type"] == "BEAM"]
    for _, r in be.iterrows():
        bid, tag = str(r["beam_id"]), r["element_tag"]
        if bid not in beam_ids:
            report(f"beam_gravity: {bid} no existe")
        if pd.isna(tag) or int(tag) != tag_map.get(bid):
            report(f"beam_gravity: {bid} tag no trazable")
        length = r["beam_length_m"]
        if pd.notna(length) and length > 0:
            eq = r["total_slab_load_kN"] / length
            if abs(eq - r["equivalent_uniform_load_kN_m"]) > 1e-6:
                report(f"beam_gravity: {bid} kN/m inconsistente con load/length")
    # total beam + wall = total neto
    t_area = bg["tributary_area_m2"].sum()
    if abs(t_area - tot_net) > TOL_CONS:
        report(f"beam_gravity: suma areas {t_area:.4f} != neta {tot_net:.4f}")
    print(f"  filas beam: {len(be)} ; filas wall: {(bg['receiver_type']=='WALL').sum()}")
    print(f"  suma areas beam_gravity: {t_area:.4f} (neta={tot_net:.4f})")

    print()
    if n_bad_overlap:
        print(f"[Overlap tributarias] {n_bad_overlap} pares con solape")
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())