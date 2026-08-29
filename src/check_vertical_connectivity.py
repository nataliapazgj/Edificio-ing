"""Chequeos de conectividad vertical LT2 (segmentos derivados).

Solo lectura de:
  data/geometry/levels.csv
  data/geometry/grid_x.csv, grid_y.csv
  data/geometry/vertical_elements_LT2.csv  (parentes, fuente de verdad)
  data/geometry/walls_LT2.csv              (parentes, fuente de verdad)
  data/geometry/column_segments_LT2.csv    (derivado)
  data/geometry/wall_segments_LT2.csv      (derivado)
  data/geometry/beams_LT2.csv

Valida segmentos derivados y reporta conectividad viga vs columnas/muros.
Los puntos conocidos (caja de escalera, lineas intermedias) se reportan
en una seccion de revision, no como errores. No modifica archivos.
"""

import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"

INTERVALS = [("B1", "L1"), ("L1", "L2"), ("L2", "L3"), ("L3", "L4"), ("L4", "ROOF")]
TOL = 1e-6
END_TOL = 1e-3  # tolerancia XY para coincidencia de extremos/nodos (m)

LEVELS_BEAMS = ["L1", "L2", "L3", "L4", "ROOF"]


def cfloat(v):
    return pd.to_numeric(v, errors="coerce")


def list_duplicates(values):
    seen, dups = set(), []
    for v in values:
        s = str(v)
        if s in seen and s not in dups:
            dups.append(s)
        seen.add(s)
    return dups


def dist_to_segment(p, s):
    (x, y), ((x1, y1), (x2, y2)) = p, s
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 <= 0:
        return math.hypot(x - x1, y - y1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def cluster_nodes(endpoints):
    """Agrupa endpoints cercanos en nodos unicos (x, y, beam_ids)."""
    nodes = []
    for e, bids in endpoints:
        hit = None
        for n in nodes:
            if abs(n[0] - e[0]) <= END_TOL and abs(n[1] - e[1]) <= END_TOL:
                hit = n
                break
        if hit is None:
            nodes.append([e[0], e[1], list(bids)])
        else:
            hit[2].extend(bid for bid in bids if bid not in hit[2])
    return nodes


def main():
    levels = pd.read_csv(GEOM / "levels.csv")
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    parents_col = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    parents_wall = pd.read_csv(GEOM / "walls_LT2.csv")
    col_seg = pd.read_csv(GEOM / "column_segments_LT2.csv")
    wall_seg = pd.read_csv(GEOM / "wall_segments_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")

    z_level = set(levels["name"].astype(str))
    lev_z = {str(n): float(z) for n, z in zip(levels["name"], levels["z_m"])}
    errors, warnings = [], []

    def report(msg, is_error=True):
        tag = "ERROR" if is_error else "WARN"
        (errors if is_error else warnings).append(msg)
        print(f"{tag}  - {msg}")

    print("=== LT2 VERTICAL CONNECTIVITY CHECK ===")
    print(f"Column segments : {len(col_seg)}")
    print(f"Wall segments   : {len(wall_seg)}")
    print(f"Parent columns  : {len(parents_col)}")
    print(f"Parent walls    : {len(parents_wall)}")
    print()

    # ------------------------------------------------ conteos
    print("[Counts]")
    if len(col_seg) != 50:
        report(f"Espera 50 column segments, hay {len(col_seg)}")
    else:
        print("  OK - 50 column segments.")
    if len(wall_seg) != 40:
        report(f"Espera 40 wall segments, hay {len(wall_seg)}")
    else:
        print("  OK - 40 wall segments.")

    per_col = col_seg["parent_id"].value_counts().to_dict()
    per_wall = wall_seg["parent_id"].value_counts().to_dict()
    bad_col = {k: v for k, v in per_col.items() if v != 5}
    bad_wall = {k: v for k, v in per_wall.items() if v != 5}
    if bad_col:
        report(f"Columnas sin 5 segmentos: {bad_col}")
    else:
        print("  OK - Cada columna tiene exactamente 5 segmentos.")
    if bad_wall:
        report(f"Muros sin 5 segmentos: {bad_wall}")
    else:
        print("  OK - Cada muro tiene exactamente 5 segmentos.")
    print()

    # ------------------------------------------------ IDs
    print("[IDs]")
    dups = list_duplicates(col_seg["segment_id"]) + list_duplicates(wall_seg["segment_id"])
    if dups:
        report(f"Duplicated segment IDs: {dups}")
    else:
        print("  OK - No duplicated segment IDs.")
    print()

    # ------------------------------------------------ niveles
    print("[Levels]")
    missing = []
    for df, idc in ((col_seg, "segment_id"), (wall_seg, "segment_id")):
        for _, r in df.iterrows():
            for c in ("from_level", "to_level"):
                if str(r[c]) not in z_level:
                    missing.append(f"{r[idc]}: nivel '{c}'='{r[c]}' inexistente")
    if missing:
        for m in missing:
            report(m)
    else:
        print("  OK - All referenced levels exist.")
    print()

    # ------------------------------------------------ altura cero
    print("[Zero height]")
    zero = []
    for df, idc in ((col_seg, "segment_id"), (wall_seg, "segment_id")):
        for _, r in df.iterrows():
            d = abs(lev_z[str(r["to_level"])] - lev_z[str(r["from_level"])])
            if d <= TOL:
                zero.append(str(r[idc]))
    if zero:
        report(f"Zero-height segments: {zero}")
    else:
        print("  OK - No zero-height segments.")
    print()

    # ------------------------------------------------ continuidad
    print("[Continuity]")
    order = {fl: i for i, (fl, _) in enumerate(INTERVALS)}
    cont_errors = []
    for df, idc in ((col_seg, "segment_id"), (wall_seg, "segment_id")):
        for pid, grp in df.groupby("parent_id"):
            segs = grp[["from_level", "to_level"]].values.tolist()
            cover = sorted([(str(f), str(t)) for f, t in segs], key=lambda x: order[x[0]])
            if [fl for fl, _ in cover] != [fl for fl, _ in INTERVALS]:
                cont_errors.append(f"{pid}: intervalos {cover} != {INTERVALS}")
                continue
            for (f1, t1), (f2, t2) in zip(cover, cover[1:]):
                if t1 != f2:
                    cont_errors.append(f"{pid}: gap entre {t1} y {f2}")
    if cont_errors:
        for e in cont_errors:
            report(e)
    else:
        print("  OK - Continuidad exacta por parent_id (sin gaps).")
    print()

    # ------------------------------------------------ geometria parent
    print("[Geometry vs parent]")
    geom_errors = []
    ax_x = {str(r["axis_id"]): float(r["x_m"]) for _, r in grid_x.iterrows()}
    ax_y = {str(r["axis_id"]): float(r["y_m"]) for _, r in grid_y.iterrows()}

    col_by_id = {str(r["element_id"]): r for _, r in parents_col.iterrows()}
    for _, seg in col_seg.iterrows():
        parent = col_by_id.get(str(seg["parent_id"]))
        if parent is None:
            geom_errors.append(f"{seg['segment_id']}: parent no encontrado")
            continue
        ex, ey = ax_x.get(str(parent["axis_x"])), ax_y.get(str(parent["axis_y"]))
        if ex is None or ey is None:
            geom_errors.append(f"{seg['segment_id']}: eje parent no resuelto")
            continue
        if abs(float(seg["x_m"]) - ex) > TOL or abs(float(seg["y_m"]) - ey) > TOL:
            geom_errors.append(f"{seg['segment_id']}: coords difieren del parent")
        if seg["section"] != parent["section"]:
            geom_errors.append(f"{seg['segment_id']}: seccion difiere del parent")

    wall_by_id = {str(r["wall_id"]): r for _, r in parents_wall.iterrows()}
    for _, seg in wall_seg.iterrows():
        parent = wall_by_id.get(str(seg["parent_id"]))
        if parent is None:
            geom_errors.append(f"{seg['segment_id']}: parent no encontrado")
            continue
        for c in ("x1_m", "y1_m", "x2_m", "y2_m", "thickness_m"):
            if abs(float(cfloat(seg[c])) - float(cfloat(parent[c]))) > TOL:
                geom_errors.append(f"{seg['segment_id']}: '{c}' difiere del parent")
    if geom_errors:
        for e in geom_errors:
            report(e)
    else:
        print("  OK - Misma geometria/coordenadas/seccion que el parent.")
    print()

    # ------------------------------------------------ conectividad vigas
    print("[Beam endpoint connectivity]")

    col_nodes = []
    for _, r in parents_col.iterrows():
        ex, ey = ax_x.get(str(r["axis_x"])), ax_y.get(str(r["axis_y"]))
        if ex is not None and ey is not None:
            col_nodes.append((ex, ey))

    wall_lines = []
    for _, r in parents_wall.iterrows():
        t = float(cfloat(r["thickness_m"]))
        wall_lines.append((((float(cfloat(r["x1_m"])), float(cfloat(r["y1_m"]))),
                            (float(cfloat(r["x2_m"])), float(cfloat(r["y2_m"])))), t))

    counts = {"columna": 0, "muro": 0, "viga-viga": 0, "sin_soporte": 0}
    review = []  # (nivel, endpoint, beams) conocidos

    for lvl in LEVELS_BEAMS:
        bl = beams[beams["level"].astype(str) == lvl]
        endpoints = []
        for _, b in bl.iterrows():
            e1 = (float(cfloat(b["x1_m"])), float(cfloat(b["y1_m"])))
            e2 = (float(cfloat(b["x2_m"])), float(cfloat(b["y2_m"])))
            endpoints.append((e1, [str(b["beam_id"])]))
            endpoints.append((e2, [str(b["beam_id"])]))
        nodes = cluster_nodes(endpoints)

        by_col = by_wall = by_beam = unsup = 0
        for n in nodes:
            e = (n[0], n[1])
            if any(abs(e[0] - c[0]) <= END_TOL and abs(e[1] - c[1]) <= END_TOL for c in col_nodes):
                by_col += 1
                continue
            if any(dist_to_segment(e, s) <= t / 2 + END_TOL for s, t in wall_lines):
                by_wall += 1
                continue
            if len(n[2]) >= 2:
                by_beam += 1
                continue
            unsup += 1
            review.append((lvl, e, n[2]))
        counts["columna"] += by_col
        counts["muro"] += by_wall
        counts["viga-viga"] += by_beam
        counts["sin_soporte"] += unsup
        print(f"  {lvl}: nodos={len(nodes)}  columna={by_col}  muro={by_wall}  "
              f"viga-viga={by_beam}  UNSUPPORTED={unsup}")

    print()
    print("[Revision - endpoints sin columna/muro y sin segunda viga]")
    # puntos conocidos de caja escalera / lineas intermedias -> solo revision
    known = {(1.90, 4.265), (1.90, 11.885)}
    if review:
        for lvl, e, bids in review:
            tag = " (conocido: caja escalera)" if (round(e[0], 3), round(e[1], 3)) in known else ""
            print(f"  {lvl}: {e[0]:.3f},{e[1]:.3f}  vigas={bids}{tag}")
    else:
        print("  (ninguno)")

    print()
    print("  Resumen endpoints:")
    print(f"    soportados por columna : {counts['columna']}")
    print(f"    soportados por muro    : {counts['muro']}")
    print(f"    conectados viga-viga   : {counts['viga-viga']}")
    print(f"    pendientes de revision : {counts['sin_soporte']}")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())