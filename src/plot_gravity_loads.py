# -*- coding: utf-8 -*-
"""Visualizacion QA de las cargas gravitacionales aplicadas LT2 (L1-L4).

Para cada viga se dibuja la banda de carga longitudinal: el ancho de cada
franja (STEP=0.05 m) es proporcional a w(s) = P_franja / STEP (carga por
unidad de longitud). Color por forma de distribucion (uniforme / triangular /
trapezoidal). Tambien se vuelca el perfil a CSV por nivel para rastreo.

Genera:
    figures/gravity_loads_L1.png         (por defecto nivel L1)
    results/gravity_profiles_<LEVEL>.csv
"""
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
FIGD = ROOT / "figures"
RES = ROOT / "results"

sys.path.insert(0, str(ROOT / "src"))
import gravity_loads  # noqa: E402


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


def main():
    levels_arg = sys.argv[1:] or ["L1"]
    beams = gravity_loads.load_beams()
    points, _ = gravity_loads.build_point_loads()

    shape_color = {
        "uniforme": "tab:blue",
        "triangular": "tab:green",
        "trapezoidal": "tab:red",
        "sin_carga": "lightgray",
    }

    FIGD.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    for level in levels_arg:
        prof = gravity_loads.distribution_profile(level, points)
        # acumular perfil bruto para la figura
        fig, ax = plt.subplots(figsize=(16, 10))
        xmin, ymin = np.inf, np.inf
        xmax, ymax = -np.inf, -np.inf
        wmax = 0.0
        for p in prof:
            bid = p["beam_id"]
            row = beams[beams.beam_id == bid].iloc[0]
            x1, y1 = float(row.x1_m), float(row.y1_m)
            x2, y2 = float(row.x2_m), float(row.y2_m)
            L = max(np.hypot(x2 - x1, y2 - y1), 1e-12)
            ux, uy = (x2 - x1) / L, (y2 - y1) / L
            nx, ny = -uy, ux
            w = p["w_kN_m"]
            wmax = max(wmax, float(np.max(w)) if w.size else 0.0)
            for k in range(p["n_strips"]):
                s0, s1 = k * gravity_loads.STEP, (k + 1) * gravity_loads.STEP
                b0x, b0y = x1 + ux * s0, y1 + uy * s0
                b1x, b1y = x1 + ux * s1, y1 + uy * s1
                half = w[k] / (2.0 * wmax) * 1.2  # ancho proporcional a w(s)
                rect = np.array([
                    (b0x - nx * half, b0y - ny * half),
                    (b1x - nx * half, b1y - ny * half),
                    (b1x + nx * half, b1y + ny * half),
                    (b0x + nx * half, b0y + ny * half),
                ])
                fc = shape_color.get(p["shape"], "tab:purple")
                ax.add_patch(Polygon(rect, closed=True, facecolor=fc,
                                     edgecolor="none", alpha=0.5, zorder=1))
            xmin = min(xmin, x1, x2); xmax = max(xmax, x1, x2)
            ymin = min(ymin, y1, y2); ymax = max(ymax, y1, y2)
            # linea de viga
            ax.plot([x1, x2], [y1, y2], color="black", lw=0.8, zorder=3)

        pad = max(xmax - xmin, ymax - ymin) * 0.06
        ax.set_xlim(xmin - pad, xmax + pad)
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.set_aspect("equal")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        q = float(points[points.level == level]["load_kN"].sum())
        ax.set_title(
            f"LT2 Cargas gravitacionales aplicadas - nivel {level}  |  "
            f"{points[points.level == level].beam_id.nunique()} vigas  |  "
            f"carga total {q:.1f} kN  |  ancho -> w(s)", fontsize=11)
        handles = [
            plt.Line2D([0], [0], color="tab:blue", lw=5, label="uniforme"),
            plt.Line2D([0], [0], color="tab:green", lw=5, label="triangular"),
            plt.Line2D([0], [0], color="tab:red", lw=5, label="trapezoidal"),
            plt.Line2D([0], [0], color="black", lw=1.5, label="viga"),
        ]
        ax.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.9)
        out = FIGD / f"gravity_loads_{level}.png"
        fig.savefig(out, dpi=200, bbox_inches="tight")
        plt.close(fig)

        # volcar perfil
        rows = []
        for p in prof:
            for k, wv in enumerate(p["w_kN_m"]):
                rows.append({
                    "level": level, "beam_id": p["beam_id"],
                    "k": k, "s_from_m": k * gravity_loads.STEP,
                    "s_to_m": (k + 1) * gravity_loads.STEP,
                    "w_kN_m": round(float(wv), 9),
                })
        pd.DataFrame(rows).to_csv(RES / f"gravity_profiles_{level}.csv", index=False)
        shapes = [p["shape"] for p in prof]
        print(f"Figura: {out}  ({len(prof)} vigas, formas: {dict(Counter(shapes))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())