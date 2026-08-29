"""Digitador auxiliar de muros LT2 basado en ejes y puntos.

Lee grid_x.csv, grid_y.csv, wall_points_LT2.csv y walls_LT2.csv.

Comandos:
  python src/wall_digitizer_lt2.py define-point X_REF Y_REF
  python src/wall_digitizer_lt2.py add-point POINT_ID X_REF Y_REF --source S [--notes N]
  python src/wall_digitizer_lt2.py add-wall WALL_ID FROM_POINT TO_POINT \\
      --thickness T --source S [--stage ST] [--from_level F] [--to_level TL] [--notes N]

Las referencias a ejes soportan offset, p.ej. "A' + 0.20 m" o "1A - 0.40 m".

--dry-run  muestra las coordenadas calculadas sin modificar ningun CSV.
--save     persiste (solo si se pide explícitamente). Sin --save no escribe nada.

No genera muros automáticamente y nunca sobrescribe IDs existentes.
"""

import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"

GRID_X = GEOM / "grid_x.csv"
GRID_Y = GEOM / "grid_y.csv"
WALL_POINTS = GEOM / "wall_points_LT2.csv"
WALLS = GEOM / "walls_LT2.csv"
LOG = GEOM / "wall_digitization_log_LT2.csv"

POINT_COLS = ["point_id", "x_m", "y_m", "axis_reference", "source", "notes"]
WALL_COLS = ["wall_id", "x1_m", "y1_m", "x2_m", "y2_m", "thickness_m",
             "stage", "from_level", "to_level", "source", "notes"]
LOG_COLS = ["wall_id", "source", "reference_description", "status", "notes"]

TOL_ANGLE = 1e-3  # rad, ~0.057 deg

AXIS_REF_RE = re.compile(
    r"^\s*(?P<axis>[A-Za-z0-9']+)\s*(?:(?P<sign>[-+])\s*(?P<off>\d+(?:\.\d+)?)\s*m?)?\s*$"
)


# ---------------------------------------------------------- helpers
def parse_axis_ref(text):
    """'A' | "A' + 0.20" | '1A - 0.40 m' -> (axis_id, offset)."""
    m = AXIS_REF_RE.match(str(text))
    if not m:
        raise ValueError(f"referencia de eje invalida: '{text}'")
    axis = m.group("axis")
    if m.group("sign") is None:
        return axis, 0.0
    sign = 1.0 if m.group("sign") == "+" else -1.0
    return axis, sign * float(m.group("off"))


def resolve_axis(text, axes):
    """Valor de coordenada para una referencia de eje con offset."""
    axis, offset = parse_axis_ref(text)
    if axis not in axes:
        raise ValueError(f"eje inexistente: '{axis}' (disponibles: {sorted(axes)})")
    return float(axes[axis]) + offset


def define_point(x_ref, y_ref, x_axis, y_axis):
    """Punto (x, y) a partir de una referencia al eje X y otra al eje Y."""
    x = resolve_axis(x_ref, x_axis)
    y = resolve_axis(y_ref, y_axis)
    return x, y


def wall_orientation(dx, dy, length):
    theta = abs(math.atan2(dy, dx))
    if theta <= TOL_ANGLE:
        return "X"
    if abs(math.pi / 2 - theta) <= TOL_ANGLE:
        return "Y"
    return "INCLINED"


def build_wall(wall_id, x1, y1, x2, y2, thickness, source,
               stage="", from_level="", to_level="", notes="", existing_ids=()):
    """Valida y prepara los datos de un muro sin escribir nada."""
    if not str(wall_id).strip():
        raise ValueError("wall_id vacio")
    if str(wall_id) in {str(i) for i in existing_ids}:
        raise ValueError(f"ID '{wall_id}' ya existe; no se sobrescribe")
    try:
        t = float(thickness)
    except (TypeError, ValueError):
        raise ValueError("espesor obligatorio (--thickness) y debe ser un numero")
    if t <= 0:
        raise ValueError("espesor debe ser mayor que cero")
    if source is None or not str(source).strip():
        raise ValueError("source obligatorio (--source)")

    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        raise ValueError(f"muro {wall_id}: longitud cero")

    orientation = wall_orientation(dx, dy, length)
    warning = None
    if orientation == "INCLINED":
        warning = (f"muro {wall_id} no es (aprox.) paralelo a X ni a Y: "
                   f"angulo {math.degrees(abs(math.atan2(dy, dx))):.3f} deg respecto a X")

    # Redondeo a mm para reproducibilidad de IDs/geometria
    return {
        "wall_id": str(wall_id),
        "x1_m": round(x1, 4), "y1_m": round(y1, 4),
        "x2_m": round(x2, 4), "y2_m": round(y2, 4),
        "thickness_m": round(t, 4),
        "stage": str(stage), "from_level": str(from_level), "to_level": str(to_level),
        "source": str(source), "notes": str(notes),
        "length": round(length, 4), "orientation": orientation,
        "warning": warning,
    }


def load_table(path, columns):
    if path.exists() and path.stat().st_size > 0:
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=columns)
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]


def append_rows(path, columns, rows):
    df = load_table(path, columns)
    new = pd.DataFrame([{c: r.get(c, "") for c in columns} for r in rows], columns=columns)
    pd.concat([df, new], ignore_index=True).to_csv(path, index=False)


def load_axes():
    gx = pd.read_csv(GRID_X)
    gy = pd.read_csv(GRID_Y)
    x_axis = {str(a): float(x) for a, x in zip(gx["axis_id"], gx["x_m"])}
    y_axis = {str(a): float(y) for a, y in zip(gy["axis_id"], gy["y_m"])}
    return x_axis, y_axis


# ------------------------------------------------------------ CLI
def cmd_define_point(args):
    x_axis, y_axis = load_axes()
    x, y = define_point(args.x_ref, args.y_ref, x_axis, y_axis)
    print(f"Punto calculado:")
    print(f"  X = {x:.4f} m   (referencia: {args.x_ref})")
    print(f"  Y = {y:.4f} m   (referencia: {args.y_ref})")
    print("(define-point nunca escribe archivos)")


def cmd_add_point(args):
    x_axis, y_axis = load_axes()
    x, y = define_point(args.x_ref, args.y_ref, x_axis, y_axis)
    print(f"Punto {args.point_id}: X={x:.4f} m, Y={y:.4f} m")

    if args.dry_run:
        print("(dry-run: no se modifica wall_points_LT2.csv)")
        return 0
    if not args.save:
        print("(no se guarda; use --save para persistir)")
        return 0

    points = load_table(WALL_POINTS, POINT_COLS)
    if str(args.point_id) in set(points["point_id"].astype(str)):
        print(f"ERROR - point_id '{args.point_id}' ya existe; no se sobrescribe")
        return 1
    row = {
        "point_id": args.point_id,
        "x_m": round(x, 4), "y_m": round(y, 4),
        "axis_reference": f"{args.x_ref} & {args.y_ref}",
        "source": args.source, "notes": args.notes,
    }
    append_rows(WALL_POINTS, POINT_COLS, [row])
    print(f"Punto guardado en {WALL_POINTS}")
    return 0


def cmd_add_wall(args):
    points = load_table(WALL_POINTS, POINT_COLS)
    walls = load_table(WALLS, WALL_COLS)
    by_id = dict(zip(points["point_id"].astype(str), points.itertuples(index=False)))

    if str(args.from_point) not in by_id or str(args.to_point) not in by_id:
        missing = [p for p in (args.from_point, args.to_point) if str(p) not in by_id]
        print(f"ERROR - Puntos inexistentes en {WALL_POINTS.name}: {missing}")
        return 1

    p1 = by_id[str(args.from_point)]
    p2 = by_id[str(args.to_point)]

    w = build_wall(
        args.wall_id, p1.x_m, p1.y_m, p2.x_m, p2.y_m,
        args.thickness, args.source,
        stage=args.stage, from_level=args.from_level, to_level=args.to_level,
        notes=args.notes, existing_ids=walls["wall_id"].astype(str),
    )

    print(f"Muro {w['wall_id']}: {p1.x_m:.4f},{p1.y_m:.4f} -> {p2.x_m:.4f},{p2.y_m:.4f}")
    print(f"  longitud   : {w['length']:.4f} m")
    print(f"  espesor    : {w['thickness_m']:.4f} m")
    print(f"  orientacion: {w['orientation']}")
    if w["warning"]:
        print(f"  AVISO      : {w['warning']}")

    if args.dry_run:
        print("(dry-run: no se modifica walls_LT2.csv ni el log)")
        return 0
    if not args.save:
        print("(no se guarda; use --save para persistir)")
        return 0

    row = {
        "wall_id": w["wall_id"], "x1_m": w["x1_m"], "y1_m": w["y1_m"],
        "x2_m": w["x2_m"], "y2_m": w["y2_m"], "thickness_m": w["thickness_m"],
        "stage": w["stage"], "from_level": w["from_level"], "to_level": w["to_level"],
        "source": w["source"], "notes": w["notes"],
    }
    append_rows(WALLS, WALL_COLS, [row])

    ref_desc = (f"p{args.from_point}({w['x1_m']:.4f},{w['y1_m']:.4f}) -> "
                f"p{args.to_point}({w['x2_m']:.4f},{w['y2_m']:.4f}) | "
                f"L={w['length']:.4f} m, espesor={w['thickness_m']:.4f} m")
    log_row = {
        "wall_id": w["wall_id"], "source": w["source"],
        "reference_description": ref_desc, "status": "saved",
        "notes": w["notes"],
    }
    append_rows(LOG, LOG_COLS, [log_row])
    print(f"Muro guardado en {WALLS}")
    print(f"Log actualizado en {LOG.name}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Digitador auxiliar de muros LT2")
    parser.add_argument("--dry-run", action="store_true",
                        help="muestra las coordenadas calculadas sin modificar CSV")
    sub = parser.add_subparsers(dest="command", required=True)

    pd_ = sub.add_parser("define-point", help="calcula un punto desde dos referencias de eje")
    pd_.add_argument("x_ref")
    pd_.add_argument("y_ref")
    pd_.set_defaults(func=cmd_define_point)

    ap = sub.add_parser("add-point", help="agrega un punto a wall_points_LT2.csv (con --save)")
    ap.add_argument("point_id")
    ap.add_argument("x_ref")
    ap.add_argument("y_ref")
    ap.add_argument("--source", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--save", action="store_true")
    ap.set_defaults(func=cmd_add_point)

    aw = sub.add_parser("add-wall", help="crea un muro desde dos puntos existentes (con --save)")
    aw.add_argument("wall_id")
    aw.add_argument("from_point")
    aw.add_argument("to_point")
    aw.add_argument("--thickness", required=True)
    aw.add_argument("--source", required=True)
    aw.add_argument("--stage", default="")
    aw.add_argument("--from_level", default="")
    aw.add_argument("--to_level", default="")
    aw.add_argument("--notes", default="")
    aw.add_argument("--save", action="store_true")
    aw.set_defaults(func=cmd_add_wall)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"ERROR - {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())