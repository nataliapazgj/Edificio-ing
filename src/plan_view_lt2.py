"""Plan viewer 2D de la geometria LT2, para un nivel dado.

Uso:
    python src/plan_view_lt2.py L2

Lee los mismos archivos que el viewer 3D y dibuja, para el nivel indicado:
grilla de ejes, columnas, muros y vigas (con IDs). Guarda:
    figures/lt2_plan_<LEVEL>.png
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"
OUT_DIR = ROOT / "figures"


def segment_rect(x1, y1, x2, y2, width):
    """Poligono (4 esquinas) de un segmento (x1,y1)-(x2,y2) con ancho `width`."""
    dx, dy = x2 - x1, y2 - y1
    length = max(np.hypot(dx, dy), 1e-12)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    return np.array([
        (x1 - nx * width / 2, y1 - ny * width / 2),
        (x2 - nx * width / 2, y2 - ny * width / 2),
        (x2 + nx * width / 2, y2 + ny * width / 2),
        (x1 + nx * width / 2, y1 + ny * width / 2),
    ])


def section_dims(section_geom, sid):
    if sid not in section_geom:
        return None
    b, h, _t = section_geom[sid]
    if np.isnan(b) or np.isnan(h):
        return None
    return b, h


def spans(z, z_from, z_to, tol=1e-9):
    lo, hi = min(z_from, z_to), max(z_from, z_to)
    return lo - tol <= z <= hi + tol


def main():
    if len(sys.argv) < 2:
        print("Uso: python src/plan_view_lt2.py <LEVEL>   (ej: L2)")
        return 1
    level = sys.argv[1]

    levels = pd.read_csv(GEOM / "levels.csv")
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    vertical = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    x_axis = {str(ax): float(x) for ax, x in zip(grid_x["axis_id"], grid_x["x_m"])}
    y_axis = {str(ay): float(y) for ay, y in zip(grid_y["axis_id"], grid_y["y_m"])}
    z_level = {str(nm): float(z) for nm, z in zip(levels["name"], levels["z_m"])}
    section_geom = {
        str(s): (float(b), float(h), float(t) if pd.notna(t) else np.nan)
        for s, b, h, t in zip(
            sections["section_id"],
            sections["b_m"],
            sections["h_m"],
            sections.get("t_m", [np.nan] * len(sections)),
        )
    }

    if level not in z_level:
        print(f"ERROR - Nivel '{level}' no existe en levels.csv")
        print(f"Niveles disponibles: {sorted(z_level)}")
        return 1

    z = z_level[level]
    columns = vertical[vertical["type"] == "column"] if "type" in vertical else vertical

    print("=== LT2 PLAN VIEW ===")
    print(f"Nivel            : {level} (z={z:.2f} m)")

    def count_columns():
        n = 0
        for _, c in columns.iterrows():
            fl, tl = str(c["from_level"]), str(c["to_level"])
            if fl in z_level and tl in z_level and spans(z, z_level[fl], z_level[tl]):
                n += 1
        return n

    def count_walls():
        n = 0
        for _, w in walls.iterrows():
            fl, tl = str(w["from_level"]), str(w["to_level"])
            if fl in z_level and tl in z_level and spans(z, z_level[fl], z_level[tl]):
                n += 1
        return n

    print(f"Columnas en nivel: {count_columns()}")
    print(f"Muros en nivel   : {count_walls()}")
    print(f"Vigas en nivel   : {sum(1 for _, b in beams.iterrows() if str(b['level']) == level)}")
    print()

    fig, ax = plt.subplots(figsize=(12, 8))

    xmin, xmax = min(x_axis.values()), max(x_axis.values())
    ymin, ymax = min(y_axis.values()), max(y_axis.values())
    span = max(xmax - xmin, ymax - ymin)
    pad = span * 0.08

    # Grilla de ejes con etiquetas
    for aid, x in x_axis.items():
        ax.axvline(x, color="gray", lw=0.6, alpha=0.7)
        ax.text(x, ymin - pad * 0.35, aid, ha="center", va="top", fontsize=8, color="dimgray")
    for aid, y in y_axis.items():
        ax.axhline(y, color="gray", lw=0.6, alpha=0.7)
        ax.text(xmin - pad * 0.25, y, aid, ha="right", va="center", fontsize=8, color="dimgray")

    # Columnas: cuadrado segun seccion, si cruzan el nivel
    for _, c in columns.iterrows():
        fl, tl = str(c["from_level"]), str(c["to_level"])
        if fl not in z_level or tl not in z_level:
            continue
        if not spans(z, z_level[fl], z_level[tl]):
            continue
        x, y = x_axis[str(c["axis_x"])], y_axis[str(c["axis_y"])]
        dims = section_dims(section_geom, str(c["section"]))
        if dims is not None:
            b, h = dims
            ax.add_patch(Rectangle((x - b / 2, y - h / 2), b, h,
                                   facecolor="tab:blue", edgecolor="black", lw=0.8, alpha=0.9,
                                   label="columna"))
            ax.text(x, y - h / 2 - pad * 0.08, str(c["element_id"]),
                    ha="center", va="top", fontsize=6, color="tab:blue")
        else:
            ax.plot(x, y, "s", color="tab:blue", ms=5)

    # Muros: poligono con espesor real si esta definido; si no, linea central
    wall_handles = []
    for _, w in walls.iterrows():
        fl, tl = str(w["from_level"]), str(w["to_level"])
        if fl not in z_level or tl not in z_level:
            continue
        if not spans(z, z_level[fl], z_level[tl]):
            continue
        x1, y1, x2, y2 = (float(w[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
        t = pd.to_numeric(w["thickness_m"], errors="coerce")
        if pd.notna(t) and t > 0:
            poly = Polygon(segment_rect(x1, y1, x2, y2, float(t)),
                           facecolor="tab:orange", edgecolor="black", lw=0.8,
                           closed=True, alpha=0.9, label="muro")
            ax.add_patch(poly)
            wall_handles.append(poly)
            ax.plot([x1, x2], [y1, y2], color="k", lw=0.5, alpha=0.6)
        else:
            (cent, ) = ax.plot([x1, x2], [y1, y2], color="tab:orange", lw=2.0,
                               label="muro (sin espesor)")
            wall_handles.append(cent)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, str(w["wall_id"]),
                ha="center", va="center", fontsize=6, color="black",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7))

    # Vigas: solo en este nivel, ancho segun seccion si existe
    for _, b in beams.iterrows():
        if str(b["level"]) != level:
            continue
        x1, y1, x2, y2 = (float(b[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
        dims = section_dims(section_geom, str(b["section"]))
        if dims is not None:
            bw, _bh = dims
            ax.add_patch(Polygon(segment_rect(x1, y1, x2, y2, bw),
                                 facecolor="tab:green", edgecolor="black", lw=0.8,
                                 closed=True, alpha=0.9, label="viga"))
        else:
            ax.plot([x1, x2], [y1, y2], color="tab:green", lw=3.0, label="viga (sin seccion)")
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, str(b["beam_id"]),
                ha="center", va="center", fontsize=6, color="black",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7))

    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad * 1.4, ymax + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_title(f"LT2 - Planta nivel {level} (z={z:.2f} m)")
    ax.grid(False)

    handles, labels = ax.get_legend_handles_labels()
    unique = {}
    for h, l in zip(handles, labels):
        unique[l] = h
    if unique:
        ax.legend(unique.values(), unique.keys(), loc="upper right", fontsize=8, framealpha=0.9,
                  title="Elementos")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"lt2_plan_{level}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    print(f"Figura guardada en: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())