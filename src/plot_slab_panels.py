# -*- coding: utf-8 -*-
"""Visualizacion QA de panes de losa LT2 superpuestos con vigas/columnas/muros.

Genera:
    figures/slab_panels_<LEVEL>.png

Uso:
    python src/plot_slab_panels.py L1 [L2 ...]
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
LOAD = ROOT / "data" / "loads"
OUT = ROOT / "figures"

STATUS_COLORS = {
    "CONFIRMED_SLAB": "tab:green",
    "CONFIRMADO": "tab:green",
    "PENDING_VISUAL_CONFIRMATION": "tab:orange",
    "ABERTURA": "white",
    "SIN_LOSA_HUECO": "white",
    "PARCIAL_ABERTURA": "tab:olive",
}


def parse_holes(s):
    holes = []
    if not s or (isinstance(s, float)):
        return holes
    for hp in str(s).split("|"):
        hp = hp.strip()
        if not hp:
            continue
        holes.append(parse_poly(hp))
    return holes


def segment_rect(x1, y1, x2, y2, width):
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


def parse_poly(s):
    return np.array([[float(v) for v in p.split(",")] for p in s.split(";")])


def main():
    levels_arg = sys.argv[1:] or ["L1"]
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    spansz = pd.read_csv(GEOM / "levels.csv")
    vertical = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    panels = pd.read_csv(LOAD / "slab_panels_LT2.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    x_axis = {str(a): float(x) for a, x in zip(grid_x["axis_id"], grid_x["x_m"])}
    y_axis = {str(a): float(y) for a, y in zip(grid_y["axis_id"], grid_y["y_m"])}
    z_level = {str(n): float(z) for n, z in zip(spansz["name"], spansz["z_m"])}
    section_geom = {
        str(s): (float(b), float(h))
        for s, b, h in zip(sections["section_id"], sections["b_m"], sections["h_m"])
    }

    INT_CAT = {  # categorias visuales de vigas
        "VI": "V.I.",
        "CONV": "viga",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    for level in levels_arg:
        if level not in z_level:
            print(f"Nivel {level} no existe; disponibles: {sorted(z_level)}")
            continue
        z = z_level[level]
        fig, ax = plt.subplots(figsize=(14, 9))

        xmin, xmax = min(x_axis.values()), max(x_axis.values())
        ymin, ymax = min(y_axis.values()), max(y_axis.values())
        span = max(xmax - xmin, ymax - ymin)
        pad = span * 0.08

        for aid, x in x_axis.items():
            ax.axvline(x, color="gray", lw=0.5, alpha=0.5)
            ax.text(x, ymin - pad * 0.3, aid, ha="center", va="top", fontsize=8, color="dimgray")
        for aid, y in y_axis.items():
            ax.axhline(y, color="gray", lw=0.5, alpha=0.5)
            ax.text(xmin - pad * 0.2, y, aid, ha="right", va="center", fontsize=8, color="dimgray")

        def present(fl, tl):
            if fl not in z_level or tl not in z_level:
                return False
            lo, hi = min(z_level[fl], z_level[tl]), max(z_level[fl], z_level[tl])
            return lo - 1e-9 <= z <= hi + 1e-9

        # Paneles de losa
        lvl_panels = panels[panels["level"] == level]
        for _, p in lvl_panels.iterrows():
            poly = parse_poly(p["polygon"])
            c = STATUS_COLORS.get(p["status"], "lightgray")
            ax.add_patch(Polygon(poly, closed=True, facecolor=c, edgecolor="black",
                                 lw=1.0, alpha=0.55, zorder=2))
            cx, cy = poly.mean(axis=0)
            ax.text(cx, cy, str(p["panel_id"]).split("_P_")[1], ha="center", va="center",
                    fontsize=6, color="black", zorder=3,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.75))
            # huecos (blancos sobre el panel)
            for h in parse_holes(p.get("holes")):
                ax.add_patch(Polygon(np.asarray(h), closed=True, facecolor="white",
                                     edgecolor="red", lw=1.2, zorder=3, hatch="//"))

        # Muros
        for _, w in walls.iterrows():
            if not present(str(w["from_level"]), str(w["to_level"])):
                continue
            x1, y1, x2, y2 = (float(w[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            t = pd.to_numeric(w["thickness_m"], errors="coerce")
            if pd.notna(t) and t > 0:
                ax.add_patch(Polygon(segment_rect(x1, y1, x2, y2, float(t)),
                                     facecolor="tab:orange", edgecolor="black", lw=0.8,
                                     closed=True, alpha=0.85, zorder=4))
            else:
                ax.plot([x1, x2], [y1, y2], color="tab:orange", lw=2.0, zorder=4)

        # Columnas
        for _, c in vertical.iterrows():
            if str(c["type"]) != "column":
                continue
            if not present(str(c["from_level"]), str(c["to_level"])):
                continue
            x, y = x_axis[str(c["axis_x"])], y_axis[str(c["axis_y"])]
            if str(c["section"]) in section_geom:
                b, h = section_geom[str(c["section"])]
                ax.add_patch(Rectangle((x - b / 2, y - h / 2), b, h,
                                       facecolor="tab:blue", edgecolor="black", lw=0.8,
                                       zorder=5, alpha=0.95))
            else:
                ax.plot(x, y, "s", color="tab:blue", ms=5, zorder=5)

        # Vigas
        for _, b in beams.iterrows():
            if str(b["level"]) != level:
                continue
            x1, y1, x2, y2 = (float(b[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            dims = section_geom.get(str(b["section"]))
            staging = str(b.get("stage", ""))
            colr = "tab:purple" if staging == "VI" else "black"
            if dims:
                bw, _ = dims
                ax.add_patch(Polygon(segment_rect(x1, y1, x2, y2, bw),
                                     facecolor=colr, edgecolor="black", lw=0.6,
                                     closed=True, alpha=0.5, zorder=6))
            else:
                ax.plot([x1, x2], [y1, y2], color=colr, lw=3.0, zorder=6)

        ax.set_xlim(xmin - pad, xmax + pad)
        ax.set_ylim(ymin - pad * 1.4, ymax + pad)
        ax.set_aspect("equal")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        n_pend = int((lvl_panels["status"] == "PENDING_VISUAL_CONFIRMATION").sum())
        n_conf = int((lvl_panels["status"] == "CONFIRMED_SLAB").sum())
        ax.set_title(f"LT2 Paños de losa - nivel {level} (z={z:.2f} m)  |  "
                     f"{len(lvl_panels)} paños, {n_conf} CONFIRMED_SLAB, {n_pend} PENDING")
        handles = [
            plt.Line2D([0], [0], color="tab:green", lw=6, label="CONFIRMED_SLAB"),
            plt.Line2D([0], [0], color="tab:orange", lw=6, label="PENDING_VISUAL_CONFIRMATION"),
            plt.Line2D([0], [0], color="white", lw=0, marker="s", markerfacecolor="white", markeredgecolor="red", label="Hueco"),
            plt.Line2D([0], [0], color="tab:orange", lw=3, label="muro"),
            plt.Line2D([0], [0], color="tab:blue", lw=0, marker="s", markersize=8, label="columna"),
            plt.Line2D([0], [0], color="black", lw=4, label="viga"),
            plt.Line2D([0], [0], color="tab:purple", lw=4, label="viga V.I. (ROOF)"),
        ]
        ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
        out = OUT / f"slab_panels_{level}.png"
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Figura: {out}  ({len(lvl_panels)} paneles, {n_conf} CONFIRMED_SLAB, {n_pend} PENDING)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
