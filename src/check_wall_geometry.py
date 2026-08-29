"""Chequeos de la digitalizacion de muros LT2.

Solo lectura de data/geometry/wall_points_LT2.csv y walls_LT2.csv.
Detecta:
  - IDs duplicados;
  - puntos duplicados (dentro de tolerancia 1e-6 m);
  - longitud de cada muro;
  - orientacion (aproximadamente paralelo a X o a Y);
  - muros ni horizontales ni verticales (fuera de tolerancia angular);
  - muros de longitud cero;
  - espesores faltantes.

No modifica ningun archivo de datos.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"

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


def duplicates_close(points):
    """Pares de indices con |dx|<=tol y |dy|<=tol dentro de la lista de puntos."""
    tol = TOL_DUP
    pairs = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if abs(points[i][0] - points[j][0]) <= tol and abs(points[i][1] - points[j][1]) <= tol:
                pairs.append((i, j))
    return pairs


def wall_orientation(L, dx, dy):
    """Devuelve ('X'|'Y'|None, theta_rad) para un muro de longitud L > 0."""
    theta = abs(math.atan2(dy, dx))
    if theta <= TOL_ANGLE:
        return "X", theta
    if abs(math.pi / 2 - theta) <= TOL_ANGLE:
        return "Y", theta
    return None, theta


def main():
    wall_points = pd.read_csv(GEOM / "wall_points_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")

    errors, warnings = [], []

    def report(msg, is_error=True):
        tag = "ERROR" if is_error else "WARN"
        (errors if is_error else warnings).append(msg)
        print(f"{tag}  - {msg}")

    print("=== LT2 WALL GEOMETRY CHECK ===")
    print()
    print(f"Wall points      : {len(wall_points)}")
    print(f"Walls            : {len(walls)}")
    print()

    # ------------------------------------------------ wall points
    print("[Wall points]")
    if len(wall_points):
        dup_ids = list_duplicates(wall_points["point_id"])
        if dup_ids:
            report(f"Duplicated point IDs: {dup_ids}")
        else:
            print("  OK - No duplicated point IDs.")

        pts = [(
            cfloat(r["x_m"]) if isinstance(r["x_m"], str) else float(r["x_m"]),
            cfloat(r["y_m"]) if isinstance(r["y_m"], str) else float(r["y_m"]),
        ) for _, r in wall_points.iterrows()]

        nan_pts = [str(wall_points["point_id"].iloc[i]) for i, p in enumerate(pts)
                   if np.isnan(p[0]) or np.isnan(p[1])]
        if nan_pts:
            report(f"NaN coordinates in points: {nan_pts}")

        pairs = duplicates_close(pts)
        if pairs:
            for i, j in pairs:
                report(f"Duplicate points within {TOL_DUP:g} m: "
                       f"{wall_points['point_id'].iloc[i]} and {wall_points['point_id'].iloc[j]} "
                       f"at ({pts[i][0]:.6f}, {pts[i][1]:.6f})")
        else:
            print(f"  OK - No duplicate points within {TOL_DUP:g} m.")
    else:
        print("  INFO - No wall points registered.")
    print()

    # ---------------------------------------------------- walls
    print("[Walls]")
    if len(walls) == 0:
        print("  INFO - No walls registered. (Walls digitization pending.)")
    else:
        dup_ids = list_duplicates(walls["wall_id"])
        if dup_ids:
            report(f"Duplicated wall IDs: {dup_ids}")
        else:
            print("  OK - No duplicated wall IDs.")

        for i, w in walls.iterrows():
            wid = str(w["wall_id"])
            x1, y1, x2, y2 = (cfloat(w[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            t = cfloat(w["thickness_m"])

            # espesor
            if np.isnan(t) or t <= 0:
                report(f"{wid}: espesor faltante o no positivo (thickness_m={w['thickness_m']!r})")
                thickness_missing = True
            else:
                thickness_missing = False

            # longitud
            if np.isnan(x1) or np.isnan(y1) or np.isnan(x2) or np.isnan(y2):
                report(f"{wid}: coordenadas NaN, no se puede calcular longitud")
                continue

            L = math.hypot(x2 - x1, y2 - y1)
            if L <= TOL_DUP:
                report(f"{wid}: muro de longitud cero ({L:.6f} m)")
                continue

            ori = wall_orientation(L, x2 - x1, y2 - y1)
            if ori[0] == "X":
                orient_str = "paralelo a X"
            elif ori[0] == "Y":
                orient_str = "paralelo a Y"
            else:
                report(f"{wid}: no es horizontal ni vertical "
                       f"(angulo {math.degrees(ori[1]):.3f} deg respecto al eje X)", is_error=False)
                orient_str = f"inclinado ({math.degrees(ori[1]):.3f} deg)"
            missing = ", espesor faltante" if thickness_missing else ""
            print(f"  {wid}: L={L:.3f} m, {orient_str}{missing}")

    print()

    if len(walls) == 0:
        warnings.append("Wall digitization pending.")
        print("WARN - Walls digitization pending.")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())