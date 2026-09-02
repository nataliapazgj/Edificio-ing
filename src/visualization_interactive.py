"""
Visualizacion 3D interactiva del frame.
Genera un HTML con plotly y lo abre en el navegador.
"""

import os
import sys
import webbrowser
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(__file__))
from model import ops

# ── Coordenadas ────────────────────────────────────────────────────────
coords = {tag: ops.nodeCoord(tag) for tag in ops.getNodeTags()}

columns = {1: (1, 5), 2: (2, 7), 3: (3, 8), 4: (4, 10)}
beams_x = {5: (5, 6), 6: (6, 7), 7: (8, 9), 8: (9, 10)}
beams_y = {9: (5, 8), 10: (6, 9), 11: (7, 10)}

fig = go.Figure()

# ── Columnas (rojo) ───────────────────────────────────────────────────
for tag, (ni, nj) in columns.items():
    xi, yi, zi = coords[ni]
    xj, yj, zj = coords[nj]
    fig.add_trace(go.Scatter3d(
        x=[xi, xj], y=[yi, yj], z=[zi, zj],
        mode="lines",
        line=dict(color="red", width=6),
        name=f"Columna E{tag}",
        hoverinfo="text",
        hovertext=f"E{tag} (Col): {ni}->{nj}",
        showlegend=(tag == 1),
    ))

# ── Vigas X (azul) ────────────────────────────────────────────────────
for tag, (ni, nj) in beams_x.items():
    xi, yi, zi = coords[ni]
    xj, yj, zj = coords[nj]
    fig.add_trace(go.Scatter3d(
        x=[xi, xj], y=[yi, yj], z=[zi, zj],
        mode="lines",
        line=dict(color="blue", width=4),
        name=f"Viga X E{tag}",
        hoverinfo="text",
        hovertext=f"E{tag} (Viga X): {ni}->{nj}",
        showlegend=(tag == 5),
    ))

# ── Vigas Y (verde) ───────────────────────────────────────────────────
for tag, (ni, nj) in beams_y.items():
    xi, yi, zi = coords[ni]
    xj, yj, zj = coords[nj]
    fig.add_trace(go.Scatter3d(
        x=[xi, xj], y=[yi, yj], z=[zi, zj],
        mode="lines",
        line=dict(color="green", width=4),
        name=f"Viga Y E{tag}",
        hoverinfo="text",
        hovertext=f"E{tag} (Viga Y): {ni}->{nj}",
        showlegend=(tag == 9),
    ))

# ── Nodos ─────────────────────────────────────────────────────────────
node_tags = list(coords.keys())
xs = [coords[t][0] for t in node_tags]
ys = [coords[t][1] for t in node_tags]
zs = [coords[t][2] for t in node_tags]
labels = [f"Nodo {t}<br>({coords[t][0]:.2f}, {coords[t][1]:.2f}, {coords[t][2]:.2f})" for t in node_tags]
colors = ["red" if t <= 4 else "blue" for t in node_tags]

fig.add_trace(go.Scatter3d(
    x=xs, y=ys, z=zs,
    mode="markers+text",
    marker=dict(size=6, color=colors, line=dict(width=1, color="black")),
    text=[str(t) for t in node_tags],
    textposition="top center",
    textfont=dict(size=11, color="black"),
    hovertext=labels,
    hoverinfo="text",
    name="Nodos",
))

# ── Layout ────────────────────────────────────────────────────────────
fig.update_layout(
    title="Benchmark 3D - Modelo Estructural (rotar con mouse)",
    scene=dict(
        xaxis_title="X [m]",
        yaxis_title="Y [m]",
        zaxis_title="Z [m]",
        aspectmode="data",
    ),
    legend=dict(x=0.01, y=0.99),
    margin=dict(l=0, r=0, t=40, b=0),
)

# ── Guardar y abrir ──────────────────────────────────────────────────
os.makedirs("figures", exist_ok=True)
out = os.path.join("figures", "frame_interactive.html")
fig.write_html(out, auto_open=False)
print(f"Guardado: {out}")
webbrowser.open("file://" + os.path.abspath(out))
print("Abierto en el navegador. Rota con el mouse.")
