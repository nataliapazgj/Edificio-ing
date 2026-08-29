"""Chequeos de la digitalizacion de vigas LT2.

Solo lectura de data/geometry/beams_LT2.csv (con levels.csv y sections_LT2.csv).
Para cada viga:
  - longitud geometrica;
  - IDs duplicados;
  - vigas de longitud cero;
  - niveles inexistentes;
  - secciones inexistentes;
  - coordenadas NaN;
  - orientacion X/Y/inclinada;
y ademas el numero de vigas por seccion y por nivel.

No modifica datos.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"

TOL_DUP = 1e-6
TOL_ANGLE = 1e-3  # rad, ~0.057 deg


def cfloat(value):
    return pd.to_numeric(value, errors="coerce")


def list_duplicates(values):
    seen, dups = set(), []
    for v in values:
        s = str(v)
        if s in seen and s not in dups:
            dups.append(s)
        seen.add(s)
    return dups


def beam_orientation(L, dx, dy):
    theta = abs(math.atan2(dy, dx))
    if theta <= TOL_ANGLE:
        return "X"
    if abs(math.pi / 2 - theta) <= TOL_ANGLE:
        return "Y"
    return "INCLINED"


def main():
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    levels = pd.read_csv(GEOM / "levels.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    z_level = set(levels["name"].astype(str))
    section_ids = set(sections["section_id"].astype(str))

    errors, warnings = [], []

    def report(msg, is_error=True):
        tag = "ERROR" if is_error else "WARN"
        (errors if is_error else warnings).append(msg)
        print(f"{tag}  - {msg}")

    print("=== LT2 BEAM GEOMETRY CHECK ===")
    print()
    print(f"Beams registered : {len(beams)}")
    print()

    # ---------------------------------------------------------- IDs
    print("[IDs]")
    dup = list_duplicates(beams["beam_id"]) if len(beams) else []
    if dup:
        report(f"Duplicated beam IDs: {dup}")
    else:
        print("  OK - No duplicated beam IDs.")
    print()

    # ---------------------------------------------- por elemento
    print("[Beams]")
    if len(beams) == 0:
        print("  INFO - No beams registered. (Beam digitization pending.)")
    else:
        for i, b in beams.iterrows():
            bid = str(b["beam_id"])
            x1, y1, x2, y2 = (cfloat(b[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))

            if any(np.isnan(v) for v in (x1, y1, x2, y2)):
                report(f"{bid}: coordenadas NaN en x/y")
                continue

            L = math.hypot(x2 - x1, y2 - y1)
            if L <= TOL_DUP:
                report(f"{bid}: viga de longitud cero ({L:.6f} m)")
                continue

            ori = beam_orientation(L, x2 - x1, y2 - y1)
            if ori == "INCLINED":
                report(f"{bid}: viga inclinada "
                       f"({math.degrees(abs(math.atan2(y2 - y1, x2 - x1))):.3f} deg respecto a X)",
                       is_error=False)
            print(f"  {bid}: L={L:.3f} m, orientacion={ori}, "
                  f"nivel={b['level']}, seccion={b['section']}")

    print()

    # ------------------------------------------------------- niveles
    print("[Levels]")
    if len(beams):
        bad = []
        for _, b in beams.iterrows():
            if str(b["level"]) not in z_level:
                bad.append(f"{b['beam_id']}: undefined level '{b['level']}'")
        if bad:
            for m in bad:
                report(m)
        else:
            print("  OK - All referenced levels exist.")
    else:
        print("  - No beams to check.")
    print()

    # ----------------------------------------------------- secciones
    print("[Sections]")
    if len(beams):
        bad = []
        for _, b in beams.iterrows():
            if str(b["section"]) not in section_ids:
                bad.append(f"{b['beam_id']}: undefined section '{b['section']}'")
        if bad:
            for m in bad:
                report(m)
        else:
            print("  OK - All referenced sections exist.")
    else:
        print("  - No beams to check.")
    print()

    # ------------------------------------------------ coordenadas NaN
    print("[NaN coordinates]")
    bad = []
    for _, b in beams.iterrows():
        for c in ("x1_m", "y1_m", "x2_m", "y2_m"):
            if pd.isna(cfloat(b[c])):
                bad.append(f"{b['beam_id']}: NaN en coordenada '{c}'")
    if bad:
        for m in bad:
            report(m)
    else:
        print("  OK - No NaN coordinates in beams.")
    print()

    # --------------------------------------------- resumen por clase
    print("[Counts]")
    if len(beams):
        print("  Beams by section:")
        print(beams["section"].value_counts().to_string())
        print()
        print("  Beams by level:")
        print(beams["level"].value_counts().to_string())
    else:
        print("  - No beams registered.")
    print()

    if len(beams) == 0:
        warnings.append("Beam digitization pending.")
        print("WARN - Beams digitization pending.")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())