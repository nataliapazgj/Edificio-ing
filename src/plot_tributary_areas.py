# -*- coding: utf-8 -*-
"""Visualizacion QA de areas tributarias LT2: vigas, panos, huecos y
poligonos tributarios con su receptor (beam_id), area y carga.

Genera:
    figures/tributary_areas_<LEVEL>.png

Uso:
    python src/plot_tributary_areas.py L1 [L2 ...]
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"
LOAD = ROOT / "data" / "loads"
OUT = ROOT / "figures"


def parse_poly(s):
    return np.array([[float(v) for v in p.split(",")] for p in s.split(";")])


def parse_polys(s):
    parts = []
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return parts
    for r in str(s).split("|"):
        r = r.strip()
        if not r:
            continue
        parts.append(parse_poly(r))
    return parts


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


def _ring_area(pts):
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def main():
    levels_arg = sys.argv[1:] or ["L1"]
    grid_x = pd.read_csv(GEOM / "grid_x.csv")
    grid_y = pd.read_csv(GEOM / "grid_y.csv")
    spansz = pd.read_csv(GEOM / "levels.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    panels = pd.read_csv(LOAD / "slab_panels_LT2.csv")
    trib = pd.read_csv(LOAD / "tributary_areas_LT2.csv")
    beam_loads = pd.read_csv(LOAD / "beam_gravity_loads_LT2.csv")
    sections = pd.read_csv(SECT / "sections_LT2.csv")

    x_axis = {str(a): float(x) for a, x in zip(grid_x["axis_id"], grid_x["x_m"])}
    y_axis = {str(a): float(y) for a, y in zip(grid_y["axis_id"], grid_y["y_m"])}
    z_level = {str(n): float(z) for n, z in zip(spansz["name"], spansz["z_m"])}
    section_geom = {
        str(s): (float(b), float(h))
        for s, b, h in zip(sections["section_id"], sections["b_m"], sections["h_m"])
    }

    cmap = plt.get_cmap("tab20")
    beam_colors = {}
    for i, bid in enumerate(
            sorted(set(beam_loads["beam_id"][beam_loads["receiver_type"] == "BEAM"]))):
        beam_colors[bid] = cmap(i % 20)

    OUT.mkdir(parents=True, exist_ok=True)
    for level in levels_arg:
        if level not in z_level:
            print(f"Nivel {level} no existe; disponibles: {sorted(z_level)}")
            continue
        z = z_level[level]
        fig, ax = plt.subplots(figsize=(16, 10))

        xmin, xmax = min(x_axis.values()), max(x_axis.values())
        ymin, ymax = min(y_axis.values()), max(y_axis.values())
        span = max(xmax - xmin, ymax - ymin)
        pad = span * 0.09

        for aid, x in x_axis.items():
            ax.axvline(x, color="gray", lw=0.5, alpha=0.5)
            ax.text(x, ymin - pad * 0.3, aid, ha="center", va="top",
                    fontsize=8, color="dimgray")
        for aid, y in y_axis.items():
            ax.axhline(y, color="gray", lw=0.5, alpha=0.5)
            ax.text(xmin - pad * 0.2, y, aid, ha="right", va="center",
                    fontsize=8, color="dimgray")

        def present(fl, tl):
            if fl not in z_level or tl not in z_level:
                return False
            lo, hi = min(z_level[fl], z_level[tl]), max(z_level[fl], z_level[tl])
            return lo - 1e-9 <= z <= hi + 1e-9

        # Panos de losa (borde suave)
        lvl_panels = panels[panels["level"] == level]
        for _, p in lvl_panels.iterrows():
            poly = parse_poly(p["polygon"])
            ax.add_patch(Polygon(poly, closed=True, facecolor="none",
                                 edgecolor="black", lw=1.2, zorder=2))
            for h in parse_holes(p.get("holes")):
                ax.add_patch(Polygon(np.asarray(h), closed=True, facecolor="white",
                                     edgecolor="red", lw=1.2, zorder=3, hatch="//"))

        # Areas tributarias
        lvl_trib = trib[trib["level"] == level]
        for _, r in lvl_trib.iterrows():
            polys = parse_polys(r["polygon"])
            if not polys:
                continue
            if str(r["receiver_type"]) == "WALL":
                fc = "tab:orange"
            else:
                fc = beam_colors.get(str(r["beam_id"]), "gray")
            for poly in polys:
                ax.add_patch(Polygon(poly, closed=True, facecolor=fc,
                                     edgecolor="black", lw=0.4, alpha=0.45, zorder=1))
            poly = max(polys, key=lambda a: _ring_area(a))
            cx, cy = poly.mean(axis=0)
            bid = str(r["beam_id"])
            if str(r["receiver_type"]) == "BEAM":
                ax.text(cx, cy, f"{bid}\n{r['area_m2']:.1f} m2 | {r['load_kN']:.0f} kN",
                        ha="center", va="center", fontsize=4.5, color="black", zorder=4)
            else:
                ax.text(cx, cy, f"WALL {str(r['receiver_id'])}\n"
                                f"{r['area_m2']:.1f} m2 | {r['load_kN']:.0f} kN",
                        ha="center", va="center", fontsize=4.5, color="black", zorder=4)

        # Muros
        for _, w in walls.iterrows():
            if not present(str(w["from_level"]), str(w["to_level"])):
                continue
            x1, y1, x2, y2 = (float(w[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            t = pd.to_numeric(w["thickness_m"], errors="coerce")
            if pd.notna(t) and t > 0:
                ax.add_patch(Polygon(segment_rect(x1, y1, x2, y2, float(t)),
                                     facecolor="tab:orange", edgecolor="black", lw=0.8,
                                     closed=True, alpha=0.85, zorder=5))
            else:
                ax.plot([x1, x2], [y1, y2], color="tab:orange", lw=2.0, zorder=5)

        # Vigas
        for _, b in beams.iterrows():
            if str(b["level"]) != level:
                continue
            x1, y1, x2, y2 = (float(b[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
            dims = section_geom.get(str(b["section"]))
            if dims:
                bw, _ = dims
                ax.add_patch(Polygon(segment_rect(x1, y1, x2, y2, bw),
                                     facecolor="tab:gray", edgecolor="black", lw=0.6,
                                     closed=True, alpha=0.5, zorder=6))
            else:
                ax.plot([x1, x2], [y1, y2], color="tab:gray", lw=3.0, zorder=6)

        ax.set_xlim(xmin - pad, xmax + pad)
        ax.set_ylim(ymin - pad * 1.4, ymax + pad)
        ax.set_aspect("equal")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        n_beam = int((lvl_trib["receiver_type"] == "BEAM").sum())
        n_wall = int((lvl_trib["receiver_type"] == "WALL").sum())
        q = lvl_trib["load_kN"].sum()
        ax.set_title(
            f"LT2 Areas tributarias - nivel {level} (z={z:.2f} m)  |  "
            f"{len(lvl_trib)} tributarias ({n_beam} viga / {n_wall} muro)  |  "
            f"carga total {q:.0f} kN", fontsize=11)
        handles = [
            plt.Line2D([0], [0], color="w", lw=0, marker="s", markersize=9,
                       markerfacecolor="tab:orange", markeredgecolor="black",
                       label="tributaria -> muro (WALL_EDGE_PENDING)"),
            plt.Line2D([0], [0], color="w", lw=0, marker="s", markersize=9,
                       markerfacecolor="tab:blue", markeredgecolor="black",
                       label="tributaria -> viga"),
            plt.Line2D([0], [0], color="white", lw=0, marker="s", markersize=9,
                       markerfacecolor="white", markeredgecolor="red", label="Hueco"),
            plt.Line2D([0], [0], color="tab:orange", lw=3, label="muro"),
            plt.Line2D([0], [0], color="tab:gray", lw=4, label="viga"),
        ]
        ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.9)
        out = OUT / f"tributary_areas_{level}.png"
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"Figura: {out}  ({len(lvl_trib)} tributarias, {n_beam} viga / {n_wall} muro)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())