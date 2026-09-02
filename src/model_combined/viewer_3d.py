"""Visor 3D interactivo del modelo combinado LT1 + LT2 (stand-alone HTML).

Construye LT2 y LT1 en la misma instancia OpenSees (orden del orquestador)
sin cargas y genera una figura plotly self-contained que distingue por color
vigas/columnas/muros de cada torre, la interfaz compartida y los muros FHA de
LT2 (tramos verticales reales, dibujados como volumenes).

NO modifica datos, builders ni resultados; solo escribe:
    results/combined/lt1_lt2_3d.html
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "model_combined"))

import openseespy.opensees as ops  # noqa: E402

from . import config as C  # noqa: E402
from .lt2_builder_wrapper import LT2Model  # noqa: E402
from .lt1_builder_combined import build_ops_model_combined  # noqa: E402


def _wall_box(seg, coord):
    """Tramo de muro LT2 (4 esquinas) -> vertices del prisma para Mesh3d."""
    n00, n10, n01, n11 = (seg[k] for k in ("n00", "n10", "n01", "n11"))
    try:
        c00, c10, c01, c11 = (coord[t] for t in (n00, n10, n01, n11))
    except KeyError:
        return None
    x = (c00[0], c10[0], c11[0], c01[0])
    y = (c00[1], c10[1], c11[1], c01[1])
    zbot, ztop = c00[2], c01[2]
    xs = (c00[0], c10[0], c01[0], c11[0],
          c00[0], c10[0], c01[0], c11[0])
    ys = (c00[1], c10[1], c01[1], c11[1],
          c00[1], c10[1], c01[1], c11[1])
    zs = (zbot, zbot, zbot, zbot, ztop, ztop, ztop, ztop)
    return xs, ys, zs


def collect():
    """Construye LT2 + LT1 y recoge elementos por familia con coords."""
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    lt2 = LT2Model()
    lt2.build(skip_diaphragms=True)

    from model_combined import lt2_walls, lt2_connect
    lt2_walls.materialize_lt2_walls(lt2)
    lt2_connect.connect_floating_beams(lt2)

    from ops_model import load_aligned
    data = load_aligned()
    lt1 = build_ops_model_combined(data, with_init=False, apply_transform=True)

    coord = {t: ops.nodeCoord(t) for t in ops.getNodeTags()}

    families = {
        "LT2 columnas": [],
        "LT2 vigas": [],
        "LT2 muros-col": [],
        "LT2 conectores": [],
        "LT1 columnas": [],
        "LT1 vigas": [],
        "LT1 muros": [],
    }

    def stick(n1, n2, name):
        c1, c2 = coord.get(n1), coord.get(n2)
        if c1 and c2:
            families[name].append((c1, c2))

    for e in lt1.get("col_elements", []):
        stick(e["ni"], e["nj"], "LT1 columnas")
    for e in lt1.get("beam_elements", []):
        stick(e["ni"], e["nj"], "LT1 vigas")
    for e in lt1.get("wall_elements", []):
        stick(e["ni"], e["nj"], "LT1 muros")

    for t in ops.getEleTags():
        if 2001 <= t < 3001:
            stick(*ops.eleNodes(t), "LT2 vigas")
        elif 3001 <= t < 4001:
            stick(*ops.eleNodes(t), "LT2 columnas")
        elif 4001 <= t < 9000:
            stick(*ops.eleNodes(t), "LT2 muros-col")
        elif 9001 <= t < 10000:
            stick(*ops.eleNodes(t), "LT2 conectores")

    wall_boxes = []
    for seg in lt2.builder.elems["walls"]:
        b = _wall_box(seg, coord)
        if b:
            wall_boxes.append(b)

    return families, wall_boxes, coord


def write(camera=None, out_name=None):
    import plotly.graph_objects as go

    camera = dict(x=1.7, y=1.7, z=1.25) if camera is None else camera
    eyex, eyey, eyez = camera["x"], camera["y"], camera["z"]
    families, wall_boxes, coord = collect()
    fig = go.Figure()

    cmap = [
        ("LT2 columnas", "#d62728", 3.6),
        ("LT2 vigas", "#ff7f0e", 2.2),
        ("LT2 muros-col", "#2ca02c", 5.0),
        ("LT2 conectores", "#000000", 3.0),
        ("LT1 columnas", "#1f77b4", 3.6),
        ("LT1 vigas", "#7fb3d5", 2.2),
        ("LT1 muros", "#9467bd", 3.0),
    ]
    for name, color, width in cmap:
        x2, y2, z2 = [], [], []
        for c1, c2 in families.get(name, []):
            x2 += [c1[0], c2[0], None]
            y2 += [c1[1], c2[1], None]
            z2 += [c1[2], c2[2], None]
        if not x2:
            continue
        fig.add_trace(go.Scatter3d(
            x=x2, y=y2, z=z2, mode="lines",
            line=dict(color=color, width=width),
            name=name))

    # Muros FHA LT2 (volumenes) como trazas separadas para poder ocultarlas
    colormap = ["#2ca02c", "#98df8a", "#8c564b", "#17becf"]
    for i, (xs, ys, zs) in enumerate(wall_boxes):
        seg_name = f"Muro M.H.A. LT2 (tramo {i + 1}/40)"
        fig.add_trace(go.Mesh3d(
            x=xs, y=ys, z=zs, alphahull=0, opacity=0.4,
            color=colormap[i % len(colormap)],
            name=seg_name, showlegend=True,
            lighting=dict(ambient=0.6, diffuse=0.7),
            legendgroup="muros_lt2"))

    # Interfaz LT1-LT2 (nodos compartidos)
    ip = [t for t in C.INTERFACE_LT2_TAGS if t in coord]
    fig.add_trace(go.Scatter3d(
        x=[coord[t][0] for t in ip],
        y=[coord[t][1] for t in ip],
        z=[coord[t][2] for t in ip],
        mode="markers", marker=dict(color="#000000", size=6, symbol="diamond"),
        name="Interfaz LT1 / LT2"))

    # Nodos (punteado fino) para dar volumen a la estructura
    nx = [coord[t][0] for t in coord]
    ny = [coord[t][1] for t in coord]
    nz = [coord[t][2] for t in coord]
    fig.add_trace(go.Scatter3d(
        x=nx, y=ny, z=nz, mode="markers",
        marker=dict(color="#555555", size=1.2, opacity=0.5),
        name="Nodos", showlegend=False))

    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis_title="X [m]", yaxis_title="Y [m]", zaxis_title="Z [m]",
            xaxis=dict(backgroundcolor="rgb(240,242,246)", gridcolor="white"),
            yaxis=dict(backgroundcolor="rgb(240,242,246)", gridcolor="white"),
            zaxis=dict(backgroundcolor="rgb(240,242,246)", gridcolor="white")),
        title=dict(
            text="Modelo estructural combinado LT1 + LT2 — Edificio de Ingeniería",
            x=0.5),
        scene_camera=dict(eye=dict(x=eyex, y=eyey, z=eyez)),
        margin=dict(l=0, r=0, b=0, t=40),
        font=dict(size=12),
    )
    out = C.RESULTS / (out_name or "lt1_lt2_3d.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(fig.to_html(include_plotlyjs="cdn", config={
            "scrollZoom": True, "displaylogo": False}))
    print("Escrito:", out)


def write_views():
    """Genera las 4 vistas finales: isometrica, lateral, frontal-alzado y planta."""
    views = {
        "lt1_lt2_3d_isometrico.html": dict(x=1.9, y=2.1, z=1.1),
        "lt1_lt2_3d_lateral_X.html":   dict(x=1e-4, y=2.6, z=0.5),
        "lt1_lt2_3d_lateral_Y.html":   dict(x=2.6, y=1e-4, z=0.5),
        "lt1_lt2_3d_planta.html":      dict(x=1e-4, y=1e-4, z=3.0),
    }
    for name, cam in views.items():
        write(camera=cam, out_name=name)


if __name__ == "__main__":
    write_views()