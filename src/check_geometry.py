"""Chequeos geometricos LT2.

Valida IDs duplicados, longitudes cero, coordenadas NaN, referencias a
niveles y secciones inexistentes, y reporta la longitud geometrica de cada
muro y viga, ademas del numero total de columnas, muros y vigas.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"


def cfloat(value):
    return pd.to_numeric(value, errors="coerce")


def list_duplicates(values):
    """Devuelve los valores duplicados (en orden), sin repetirlos."""
    seen, dups = set(), []
    for v in values:
        s = str(v)
        if s in seen and s not in dups:
            dups.append(s)
        seen.add(s)
    return dups


def seg_length(x1, y1, x2, y2):
    return float(np.hypot(x1 - x2, y1 - y2))


def main():
    levels = pd.read_csv(GEOM / "levels.csv")
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    vertical = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    columns = vertical[vertical["type"] == "column"] if "type" in vertical else vertical
    errors, warnings = [], []

    def report(msg, is_error=True):
        tag = "ERROR" if is_error else "WARN"
        (errors if is_error else warnings).append(msg)
        print(f"{tag}  - {msg}")

    print("=== LT2 GEOMETRY CHECK ===")
    print()
    print(f"Columns registered : {len(columns)}")
    print(f"Walls registered   : {len(walls)}")
    print(f"Beams registered   : {len(beams)}")
    print()

    # ---------------------------------------------------------- IDs
    print("[IDs]")
    col_dups = list_duplicates(columns["element_id"])
    wall_dups = list_duplicates(walls["wall_id"]) if len(walls) else []
    beam_dups = list_duplicates(beams["beam_id"]) if len(beams) else []

    if col_dups:
        report(f"Duplicated column IDs: {col_dups}")
    else:
        print("  OK - No duplicated column IDs.")
    if wall_dups:
        report(f"Duplicated wall IDs: {wall_dups}")
    else:
        print("  OK - No duplicated wall IDs.")
    if beam_dups:
        report(f"Duplicated beam IDs: {beam_dups}")
    else:
        print("  OK - No duplicated beam IDs.")

    id_owner = {}
    for i in columns["element_id"]:
        id_owner.setdefault(str(i), set()).add("column")
    for i in walls["wall_id"]:
        id_owner.setdefault(str(i), set()).add("wall")
    for i in beams["beam_id"]:
        id_owner.setdefault(str(i), set()).add("beam")
    collisions = [k for k, v in id_owner.items() if len(v) > 1]
    if collisions:
        report(f"Global ID collisions between element classes: {collisions}")
    else:
        print("  OK - No global ID collisions between element classes.")
    print()

    # ------------------------------------------------------- niveles
    print("[Levels]")
    z_level = set(levels["name"].astype(str))
    missing_level = []

    def check_level(ref, elem):
        if ref not in z_level:
            missing_level.append(f"{elem}: undefined level '{ref}'")

    for _, e in vertical.iterrows():
        check_level(str(e["from_level"]), e["element_id"])
        check_level(str(e["to_level"]), e["element_id"])
    for _, w in walls.iterrows():
        check_level(str(w["from_level"]), w["wall_id"])
        check_level(str(w["to_level"]), w["wall_id"])
    for _, b in beams.iterrows():
        check_level(str(b["level"]), b["beam_id"])

    if missing_level:
        for m in missing_level:
            report(m)
    else:
        print("  OK - All referenced levels exist.")
    print()

    # ----------------------------------------------------- secciones
    print("[Sections]")
    defined = set(sections["section_id"].astype(str))
    missing_section = []
    for _, e in columns.iterrows():
        if str(e["section"]) not in defined:
            missing_section.append(f"{e['element_id']}: undefined section '{e['section']}'")
    for _, b in beams.iterrows():
        if str(b["section"]) not in defined:
            missing_section.append(f"{b['beam_id']}: undefined section '{b['section']}'")

    if missing_section:
        for m in missing_section:
            report(m)
    else:
        print("  OK - All referenced sections are defined.")
    if len(sections):
        print("  Columns by section:")
        print(columns["section"].value_counts().to_string())
    print()

    # --------------------------------------------------- V.I. ROOF
    print("[V.I. ROOF]")
    vi_prefix = "ROOF_VI_"
    vi_beams = beams[beams["beam_id"].astype(str).str.startswith(vi_prefix)]
    conv_beams = beams[~beams["beam_id"].astype(str).str.startswith(vi_prefix)]
    expected_vi_ids = [f"ROOF_VI_{i:02d}" for i in range(1, 8)]
    expected_absent = [f"ROOF_VI_{i:02d}" for i in (8, 9, 10)]
    present_vi_ids = sorted(vi_beams["beam_id"].astype(str).tolist())

    if present_vi_ids == expected_vi_ids:
        print(f"  OK - VI-01..07 present ({len(vi_beams)} beams).")
    else:
        missing_vi = set(expected_vi_ids) - set(present_vi_ids)
        extra_vi = set(present_vi_ids) - set(expected_vi_ids)
        if missing_vi:
            report(f"VI beams missing: {sorted(missing_vi)}")
        if extra_vi:
            report(f"Unexpected VI beams: {sorted(extra_vi)}")

    found_absent = [bid for bid in expected_absent
                    if bid in beams["beam_id"].astype(str).values]
    if found_absent:
        report(f"VI-08..10 should be absent but found: {found_absent}")
    else:
        print("  OK - VI-08..10 absent from model.")

    roof_conv = beams[(beams["level"] == "ROOF")
                      & (~beams["beam_id"].astype(str).str.startswith(vi_prefix))]
    replaced = []
    for _, rc in roof_conv.iterrows():
        for _, vb in vi_beams.iterrows():
            if (abs(cfloat(rc["x1_m"]) - cfloat(vb["x1_m"])) < 1e-6
                    and abs(cfloat(rc["y1_m"]) - cfloat(vb["y1_m"])) < 1e-6
                    and abs(cfloat(rc["x2_m"]) - cfloat(vb["x2_m"])) < 1e-6
                    and abs(cfloat(rc["y2_m"]) - cfloat(vb["y2_m"])) < 1e-6):
                replaced.append(f"{rc['beam_id']} == {vb['beam_id']}")
    if replaced:
        report(f"VI replaced conventional beams: {replaced}")
    else:
        print("  OK - No VI beam replaced a conventional beam.")

    section_notes = {str(r["section_id"]): str(r.get("notes", ""))
                     for _, r in sections.iterrows()}
    vi_pending = []
    vi_ready = []
    for _, vb in vi_beams.iterrows():
        sid = str(vb["section"])
        notes = section_notes.get(sid, "")
        if "analysis_status=PENDING_VARIABLE_SECTION" in notes:
            vi_pending.append(str(vb["beam_id"]))
        else:
            vi_ready.append(str(vb["beam_id"]))
    if vi_pending:
        print(f"  [PEND] VI beams with PENDING_VARIABLE_SECTION: {vi_pending}")
    print(f"  OK - VI analysis_ready beams: {vi_ready}")

    roof_total = len(beams[beams["level"] == "ROOF"])
    lt2_total = len(beams)
    expected_roof = 53
    expected_lt2 = 237
    if roof_total != expected_roof:
        report(f"ROOF beams: {roof_total} (expected {expected_roof})")
    else:
        print(f"  OK - ROOF geometric beams: {roof_total}")
    if lt2_total != expected_lt2:
        report(f"LT2 geometric beams: {lt2_total} (expected {expected_lt2})")
    else:
        print(f"  OK - LT2 geometric beams: {lt2_total}")

    n_analysis_ready = lt2_total - len(vi_pending)
    print(f"  Geometric beams (all) : {lt2_total}")
    print(f"  Analysis-ready beams  : {n_analysis_ready} "
          f"({len(vi_pending)} pending variable section)")
    print()

    # --------------------------------------------------- coordenadas
    print("[NaN coordinates]")
    nan_list = []

    def coords_nan(df, kind, idcol, cols):
        for _, r in df.iterrows():
            for c in cols:
                if pd.isna(cfloat(r.get(c))):
                    nan_list.append(f"{r[idcol]}: NaN en coordenada '{c}'")

    coords_nan(walls, "wall", "wall_id", ["x1_m", "y1_m", "x2_m", "y2_m", "thickness_m"])
    coords_nan(beams, "beam", "beam_id", ["x1_m", "y1_m", "x2_m", "y2_m"])

    for _, r in levels.iterrows():
        if pd.isna(cfloat(r["z_m"])):
            nan_list.append(f"level {r['name']}: NaN en z_m")
    for _, r in grid_x.iterrows():
        if pd.isna(cfloat(r["x_m"])):
            nan_list.append(f"axis {r['axis_id']}: NaN en x_m")
    for _, r in grid_y.iterrows():
        if pd.isna(cfloat(r["y_m"])):
            nan_list.append(f"axis {r['axis_id']}: NaN en y_m")

    if nan_list:
        for n in nan_list:
            report(n)
    else:
        print("  OK - No NaN coordinates in walls, beams, levels or grids.")
    print()

    # ------------------------------------------------ longitud cero
    print("[Zero length]")
    if len(walls) == 0:
        print("  - Walls: none registered.")
    else:
        zero_walls = []
        for _, w in walls.iterrows():
            L = seg_length(cfloat(w["x1_m"]), cfloat(w["y1_m"]), cfloat(w["x2_m"]), cfloat(w["y2_m"]))
            if L <= 1e-9:
                zero_walls.append(str(w["wall_id"]))
        if zero_walls:
            report(f"Zero-length walls: {zero_walls}")
        else:
            print("  OK - No zero-length walls.")

    if len(beams) == 0:
        print("  - Beams: none registered.")
    else:
        zero_beams = []
        for _, b in beams.iterrows():
            L = seg_length(cfloat(b["x1_m"]), cfloat(b["y1_m"]), cfloat(b["x2_m"]), cfloat(b["y2_m"]))
            if L <= 1e-9:
                zero_beams.append(str(b["beam_id"]))
        if zero_beams:
            report(f"Zero-length beams: {zero_beams}")
        else:
            print("  OK - No zero-length beams.")
    print()

    # ---------------------------------------- longitudes geometricas
    print("[Geometric lengths]")
    if len(walls) == 0:
        print("  Walls: none registered.")
    else:
        for _, w in walls.iterrows():
            L = seg_length(cfloat(w["x1_m"]), cfloat(w["y1_m"]), cfloat(w["x2_m"]), cfloat(w["y2_m"]))
            print(f"  wall {w['wall_id']}: {L:.3f} m")
    if len(beams) == 0:
        print("  Beams: none registered.")
    else:
        for _, b in beams.iterrows():
            L = seg_length(cfloat(b["x1_m"]), cfloat(b["y1_m"]), cfloat(b["x2_m"]), cfloat(b["y2_m"]))
            print(f"  beam {b['beam_id']}: {L:.3f} m")
    print()

    if len(walls) == 0:
        warnings.append("Wall digitization pending.")
        print("WARN - Walls digitization pending.")
    if len(beams) == 0:
        warnings.append("Beam digitization pending.")
        print("WARN - Beams digitization pending.")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())