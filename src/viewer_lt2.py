"""Viewer 3D preliminar de la geometria LT2.

Lee exclusivamente los archivos de geometria y secciones:

  data/geometry/levels.csv
  data/geometry/grid_x.csv
  data/geometry/grid_y.csv
  data/geometry/vertical_elements_LT2.csv
  data/geometry/walls_LT2.csv
  data/geometry/beams_LT2.csv
  data/sections/sections_LT2.csv

No hardcodea coordenadas: toda la geometria proviene de esos CSVs.
Reporta por consola cualquier referencia a ejes o niveles inexistentes.
"""

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"
OUT = ROOT / "figures" / "lt2_geometry_preview.png"


def load_data():
    """Carga los archivos soportados y devuelve tablas y diccionarios."""
    levels = pd.read_csv(GEOM / "levels.csv")
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    vertical = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    col_seg = wall_seg = None
    if (GEOM / "column_segments_LT2.csv").exists():
        col_seg = pd.read_csv(GEOM / "column_segments_LT2.csv")
    if (GEOM / "wall_segments_LT2.csv").exists():
        wall_seg = pd.read_csv(GEOM / "wall_segments_LT2.csv")

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
    return levels, grid_x, grid_y, vertical, walls, beams, col_seg, wall_seg, x_axis, y_axis, z_level, section_geom


def check_references(vertical, walls, beams, x_axis, y_axis, z_level, section_geom):
    """Reporta referencias a ejes, niveles o secciones inexistentes."""
    problems = []

    for _, e in vertical.iterrows():
        eid = str(e["element_id"])
        ax = str(e["axis_x"])
        ay = str(e["axis_y"])
        if ax not in x_axis:
            problems.append(f"{eid}: eje X '{ax}' no existe en grid_x.csv")
        if ay not in y_axis:
            problems.append(f"{eid}: eje Y '{ay}' no existe en grid_y.csv")
        for tag, ref in (("from_level", str(e["from_level"])), ("to_level", str(e["to_level"]))):
            if ref not in z_level:
                problems.append(f"{eid}: nivel {tag} '{ref}' no existe en levels.csv")
        if str(e["section"]) not in section_geom:
            problems.append(f"{eid}: seccion '{e['section']}' no existe en sections_LT2.csv")

    for _, w in walls.iterrows():
        wid = str(w["wall_id"])
        for tag, ref in (("from_level", str(w["from_level"])), ("to_level", str(w["to_level"]))):
            if ref not in z_level:
                problems.append(f"{wid}: nivel {tag} '{ref}' no existe en levels.csv")

    for _, b in beams.iterrows():
        bid = str(b["beam_id"])
        if str(b["level"]) not in z_level:
            problems.append(f"{bid}: nivel '{b['level']}' no existe en levels.csv")
        if str(b["section"]) not in section_geom:
            problems.append(f"{bid}: seccion '{b['section']}' no existe en sections_LT2.csv")

    if problems:
        print("ERRORES - referencias a ejes, niveles o secciones inexistentes:")
        for p in problems:
            print(f"  - {p}")
    else:
        print("OK - todas las referencias a ejes, niveles y secciones existen.")
    return len(problems) > 0


def draw_box(ax, x0, y0, x1, y1, z0, z1, color="tab:blue", lw=2.0):
    """Dibuja las 12 aristas de una caja alineada con los ejes globales."""
    corners = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),  # base
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),  # tope
    ]
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    for i, j in edges:
        xs = [corners[i][0], corners[j][0]]
        ys = [corners[i][1], corners[j][1]]
        zs = [corners[i][2], corners[j][2]]
        ax.plot(xs, ys, zs, color=color, lw=lw)


def draw_global_axes(ax, z_origin):
    """Ejes globales X/Y/Z desde el origen de coordenadas (x=0, y=0, z=z_origin)."""
    length = 12.0
    colors = {"X": "tab:red", "Y": "tab:green", "Z": "tab:purple"}
    endpoints = {"X": (length, 0, 0), "Y": (0, length, 0), "Z": (0, 0, length)}
    for name, (dx, dy, dz) in endpoints.items():
        ax.quiver(0, 0, z_origin, dx, dy, dz, color=colors[name], length=length, arrow_length_ratio=0.08, lw=2)
        ax.text(dx * 1.15, dy * 1.15, z_origin + dz * 1.15, name, color=colors[name], fontsize=12, weight="bold")


def draw_strip_box(ax, x1, y1, x2, y2, width, z0, z1, color, lw=2.0):
    """Caja 3D que recorre el segmento (x1,y1)-(x2,y2) en planta, con ancho
    transversal `width`, extendida verticalmente de z0 a z1 (caja envolvente)."""
    dx, dy = x2 - x1, y2 - y1
    length = max(math.hypot(dx, dy), 1e-12)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    corners = [
        (cx - ux * length / 2 - nx * width / 2, cy - uy * length / 2 - ny * width / 2),
        (cx + ux * length / 2 - nx * width / 2, cy + uy * length / 2 - ny * width / 2),
        (cx + ux * length / 2 + nx * width / 2, cy + uy * length / 2 + ny * width / 2),
        (cx - ux * length / 2 + nx * width / 2, cy - uy * length / 2 + ny * width / 2),
    ]
    x0 = min(c[0] for c in corners)
    x1b = max(c[0] for c in corners)
    y0 = min(c[1] for c in corners)
    y1b = max(c[1] for c in corners)
    draw_box(ax, x0, y0, x1b, y1b, z0, z1, color, lw)


def section_dims(section_geom, sid):
    """Dimensiones (b, h) de una seccion; None si no esta definida o es NaN."""
    if sid not in section_geom:
        return None
    b, h, _t = section_geom[sid]
    if np.isnan(b) or np.isnan(h):
        return None
    return b, h


def main():
    show = "--show" in sys.argv
    (
        levels, grid_x, grid_y, vertical, walls, beams,
        col_seg, wall_seg, x_axis, y_axis, z_level, section_geom,
    ) = load_data()

    print("=== LT2 VIEWER ===")
    print(f"Niveles          : {len(levels)}")
    print(f"Ejes X           : {len(grid_x)}")
    print(f"Ejes Y           : {len(grid_y)}")
    print(f"Elementos vert.  : {len(vertical)}")
    print(f"Muros            : {len(walls)}")
    print(f"Vigas            : {len(beams)}")
    if col_seg is not None:
        print(f"Col segments     : {len(col_seg)} (derivados)")
    if wall_seg is not None:
        print(f"Wall segments    : {len(wall_seg)} (derivados)")
    print()
    check_references(vertical, walls, beams, x_axis, y_axis, z_level, section_geom)
    print()

    xmin, xmax = grid_x["x_m"].min(), grid_x["x_m"].max()
    ymin, ymax = grid_y["y_m"].min(), grid_y["y_m"].max()
    zmin, zmax = z_level[min(z_level, key=z_level.get)], z_level[max(z_level, key=z_level.get)]

    fig = plt.figure(figsize=(13, 9))
    ax = fig.add_subplot(111, projection="3d")

    draw_global_axes(ax, zmin)

    # Rejilla de ejes (contexto)
    z_grid = z_level["L2"]
    for axv in x_axis.values():
        ax.plot([axv, axv], [ymin, ymax], [z_grid, z_grid], color="gray", lw=0.5, alpha=0.6)
    for ayv in y_axis.values():
        ax.plot([xmin, xmax], [ayv, ayv], [z_grid, z_grid], color="gray", lw=0.5, alpha=0.6)

    # Columnas: prisma segun seccion con ID en el tope
    if col_seg is not None:
        for _, seg in col_seg.iterrows():
            fl = str(seg["from_level"])
            tl = str(seg["to_level"])
            if fl not in z_level or tl not in z_level:
                continue
            x, y = float(seg["x_m"]), float(seg["y_m"])
            z1, z2 = z_level[fl], z_level[tl]
            sid = str(seg["section"])
            dims = section_dims(section_geom, sid)
            if dims is not None:
                b, h = dims
                draw_box(ax, x - b / 2, y - h / 2, x + b / 2, y + h / 2, z1, z2,
                         color="tab:blue", lw=2.0)
            else:
                ax.plot([x, x], [y, y], [z1, z2], color="tab:blue", lw=2.0)
    else:
        columns = vertical[vertical["type"] == "column"] if "type" in vertical else vertical
        for _, col in columns.iterrows():
            axv = str(col["axis_x"])
            ayv = str(col["axis_y"])
            if axv not in x_axis or ayv not in y_axis:
                continue
            fl = str(col["from_level"])
            tl = str(col["to_level"])
            if fl not in z_level or tl not in z_level:
                continue

            x = x_axis[axv]
            y = y_axis[ayv]
            z1, z2 = z_level[fl], z_level[tl]

            sid = str(col["section"])
            dims = section_dims(section_geom, sid)
            if dims is not None:
                b, h = dims
                draw_box(ax, x - b / 2, y - h / 2, x + b / 2, y + h / 2, z1, z2,
                         color="tab:blue", lw=2.0)
            else:
                print(f"  - {col['element_id']}: seccion '{sid}' no definida, dibujando como linea")
                ax.plot([x, x], [y, y], [z1, z2], color="tab:blue", lw=2.0)

            ax.text(x + 0.4, y + 0.4, z2, str(col["element_id"]), fontsize=7, color="tab:blue")

    # Muros: prisma con espesor y ID
    if wall_seg is not None:
        for _, seg in wall_seg.iterrows():
            fl = str(seg["from_level"])
            tl = str(seg["to_level"])
            if fl not in z_level or tl not in z_level:
                continue
            x1, y1, x2, y2 = (float(seg[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            t = float(seg["thickness_m"])
            draw_strip_box(ax, x1, y1, x2, y2, t, z_level[fl], z_level[tl],
                           color="tab:orange", lw=2.0)
    else:
        for _, w in walls.iterrows():
            fl = str(w["from_level"])
            tl = str(w["to_level"])
            if fl not in z_level or tl not in z_level:
                continue
            x1, y1, x2, y2 = (float(w[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            t = float(w["thickness_m"])
            draw_strip_box(ax, x1, y1, x2, y2, t, z_level[fl], z_level[tl],
                           color="tab:orange", lw=2.0)
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, z_level[tl], str(w["wall_id"]),
                    fontsize=7, color="tab:orange")

    # Vigas: prisma en el nivel indicado; sin seccion se dibujan como linea
    for _, b in beams.iterrows():
        lv = str(b["level"])
        if lv not in z_level:
            continue
        x1, y1, x2, y2 = (float(b[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
        z = z_level[lv]
        dims = section_dims(section_geom, str(b["section"]))
        if dims is not None:
            bw, bh = dims
            draw_strip_box(ax, x1, y1, x2, y2, bw, z, z + bh,
                           color="tab:green", lw=2.0)
        else:
            ax.plot([x1, x2], [y1, y2], [z, z], color="tab:green", lw=3.0)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, z, str(b["beam_id"]),
                fontsize=7, color="tab:green")

    # Niveles (piezas de planta en el contorno del edificio)
    for _, lv in levels.iterrows():
        z = float(lv["z_m"])
        nm = str(lv["name"])
        ax.plot([xmin, xmax], [ymin, ymin], [z, z], color="black", lw=0.8)
        ax.plot([xmax, xmax], [ymin, ymax], [z, z], color="black", lw=0.8)
        ax.plot([xmax, xmin], [ymax, ymax], [z, z], color="black", lw=0.8)
        ax.plot([xmin, xmin], [ymax, ymin], [z, z], color="black", lw=0.8)
        ax.text(xmin + 0.3, ymin + 0.3, z, f"{nm} z={z:.2f} m", fontsize=8, color="black")

    # Limites y aspecto
    margin = max(xmax - xmin, ymax - ymin, zmax - zmin) * 0.05
    ax.set_xlim(xmin - margin, xmax + margin)
    ax.set_ylim(ymin - margin, ymax + margin)
    ax.set_zlim(zmin - margin, zmax + margin)
    ax.set_box_aspect((xmax - xmin, ymax - ymin, zmax - zmin))

    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")
    ax.set_title("LT2 - Viewer geometrico preliminar")

    ax.view_init(elev=22, azim=-55)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200, bbox_inches="tight")
    print(f"Figura guardada en: {OUT}")

    if show:
        matplotlib.use("TkAgg")
        plt.show()


if __name__ == "__main__":
    main()