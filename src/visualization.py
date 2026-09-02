"""
Visualizacion 3D del modelo estructural completo.
Nodos + columnas + vigas (sin cargas ni analisis).
"""

import os
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from model import ops

# ── Coordenadas de los 10 nodos ────────────────────────────────────────
node_ids = ops.getNodeTags()
coords = {tag: ops.nodeCoord(tag) for tag in node_ids}

base_ids   = [1, 2, 3, 4]
upper_ids  = [5, 6, 7, 8, 9, 10]

# ── Conectividad de elementos ──────────────────────────────────────────
columns = {1: (1, 5), 2: (2, 7), 3: (3, 8), 4: (4, 10)}
beams_x = {5: (5, 6), 6: (6, 7), 7: (8, 9), 8: (9, 10)}
beams_y = {9: (5, 8), 10: (6, 9), 11: (7, 10)}

# ── Plot ───────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(11, 8))
ax = fig.add_subplot(111, projection="3d")

# --- Dibujar barras ---
def draw_bar(ni, nj, color, lw, label=None):
    xi, yi, zi = coords[ni]
    xj, yj, zj = coords[nj]
    ax.plot([xi, xj], [yi, yj], [zi, zj],
            color=color, linewidth=lw, solid_capstyle="round",
            label=label, zorder=3)

# Columnas (rojo, grueso)
for tag, (ni, nj) in columns.items():
    draw_bar(ni, nj, color="tab:red", lw=3.0,
             label="Columna" if tag == 1 else None)
    mid = ((coords[ni][i] + coords[nj][i]) / 2.0 for i in range(3))
    mx, my, mz = mid
    ax.text(mx, my, mz + 0.25, f"E{tag}", fontsize=8,
            ha="center", color="tab:red", fontweight="bold")

# Vigas X (azul)
for tag, (ni, nj) in beams_x.items():
    draw_bar(ni, nj, color="tab:blue", lw=2.2,
             label="Viga X" if tag == 5 else None)
    mid = ((coords[ni][i] + coords[nj][i]) / 2.0 for i in range(3))
    mx, my, mz = mid
    ax.text(mx, my, mz + 0.25, f"E{tag}", fontsize=8,
            ha="center", color="tab:blue", fontweight="bold")

# Vigas Y (verde)
for tag, (ni, nj) in beams_y.items():
    draw_bar(ni, nj, color="tab:green", lw=2.2,
             label="Viga Y" if tag == 9 else None)
    mid = ((coords[ni][i] + coords[nj][i]) / 2.0 for i in range(3))
    mx, my, mz = mid
    ax.text(mx, my, mz + 0.25, f"E{tag}", fontsize=8,
            ha="center", color="tab:green", fontweight="bold")

# --- Nodos base (circulos rojos) ---
bx = [coords[t][0] for t in base_ids]
by = [coords[t][1] for t in base_ids]
bz = [coords[t][2] for t in base_ids]
ax.scatter(bx, by, bz, c="tab:red", s=90, marker="o",
           edgecolors="black", linewidths=0.8, zorder=5)

# --- Nodos superiores (triangulos azules) ---
ux = [coords[t][0] for t in upper_ids]
uy = [coords[t][1] for t in upper_ids]
uz = [coords[t][2] for t in upper_ids]
ax.scatter(ux, uy, uz, c="tab:blue", s=90, marker="^",
           edgecolors="black", linewidths=0.8, zorder=5)

# --- Etiquetas de nodo ---
for tag in node_ids:
    x, y, z = coords[tag]
    ax.text(x, y, z + 0.30, str(tag), fontsize=10, fontweight="bold",
            ha="center", va="bottom", color="black", zorder=6)

# ── Ejes globales (flechas) ───────────────────────────────────────────
axis_len = 2.5
origin = [0, 0, 0]
ax.quiver(*origin, axis_len, 0, 0, color="gray", arrow_length_ratio=0.15,
          linewidth=1.2, linestyle="--", alpha=0.6)
ax.quiver(*origin, 0, axis_len, 0, color="gray", arrow_length_ratio=0.15,
          linewidth=1.2, linestyle="--", alpha=0.6)
ax.quiver(*origin, 0, 0, axis_len, color="gray", arrow_length_ratio=0.15,
          linewidth=1.2, linestyle="--", alpha=0.6)

ax.text(axis_len + 0.3, 0, 0, "X", fontsize=11, color="gray")
ax.text(0, axis_len + 0.3, 0, "Y", fontsize=11, color="gray")
ax.text(0, 0, axis_len + 0.3, "Z", fontsize=11, color="gray")

# ── Formato ────────────────────────────────────────────────────────────
ax.set_xlabel("X  [m]")
ax.set_ylabel("Y  [m]")
ax.set_zlabel("Z  [m]")
ax.set_title("Benchmark 3D — Modelo Estructural Completo")

# Leyenda sin duplicados
handles, labels = ax.get_legend_handles_labels()
by_label = dict(zip(labels, handles))
ax.legend(by_label.values(), by_label.keys(),
          loc="upper left", fontsize=9)

# Escala proporcional
all_coords = list(coords.values())
max_range = max(
    max(c[i] for c in all_coords) - min(c[i] for c in all_coords)
    for i in range(3)
) / 2.0
mid = [
    (max(c[i] for c in all_coords) + min(c[i] for c in all_coords)) / 2.0
    for i in range(3)
]
ax.set_xlim(mid[0] - max_range * 1.3, mid[0] + max_range * 1.3)
ax.set_ylim(mid[1] - max_range * 1.3, mid[1] + max_range * 1.3)
ax.set_zlim(mid[2] - max_range * 1.3, mid[2] + max_range * 1.3)

# ── Guardar ────────────────────────────────────────────────────────────
os.makedirs("figures", exist_ok=True)
fig.savefig("figures/frame_3d.png", dpi=150, bbox_inches="tight")
print("Figura guardada en figures/frame_3d.png")
try:
    plt.show(block=False)
    plt.pause(2)
except Exception:
    pass
plt.close(fig)
