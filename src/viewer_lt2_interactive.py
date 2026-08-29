"""Viewer 3D interactivo de la geometria LT2.

Genera figures/lt2_geometry_interactive.html con Plotly:
  - columnas                (prisma por segmento, azul)
  - muros                   (prisma por segmento, naranja)
  - vigas                   (por nivel, color por seccion)
  - plano de ejes           (rejilla gris por nivel)
  - master nodes propuestos (NM_L1..NM_ROOF, morado, con hover)
Slider: seleccion de nivel (oculta vigas de otros niveles).
Elementos hover: ID + coordenadas + nivel/seccion/espesor.
No modifica archivos de geometria.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
FIGD = ROOT / "figures"

COL_COLOR = "#1f6fb2"
WALL_COLOR = "#e07b1a"
SECTION_COLORS = {
    "V60x80": "#2ca02c",
    "V40x80": "#9467bd",
    "V30x80": "#17becf",
}
MASTER_COLOR = "#7b2fbe"

LEVELS_ALL = ["L1", "L2", "L3", "L4", "ROOF"]


def fnum(v):
    return float(pd.to_numeric(v, errors="coerce"))


def load():
    levels = pd.read_csv(GEOM / "levels.csv")
    gx = pd.read_csv(GEOM / "grid_x.csv")
    gy = pd.read_csv(GEOM / "grid_y.csv")
    cols = pd.read_csv(GEOM / "vertical_elements_LT2.csv")
    walls = pd.read_csv(GEOM / "walls_LT2.csv")
    beams = pd.read_csv(GEOM / "beams_LT2.csv")
    col_seg = pd.read_csv(GEOM / "column_segments_LT2.csv")
    wall_seg = pd.read_csv(GEOM / "wall_segments_LT2.csv")

    axx = {str(r.axis_id): fnum(r.x_m) for _, r in gx.iterrows()}
    ayy = {str(r.axis_id): fnum(r.y_m) for _, r in gy.iterrows()}
    zlvl = {}
    for _, r in levels.iterrows():
        zlvl[str(r["name"])] = fnum(r["z_m"])
    return levels, gx, gy, cols, walls, beams, col_seg, wall_seg, axx, ayy, zlvl


def line_points(points, texts, name, color, width=6, dash=None):
    """Scatter3d con saltos de linea (None) y hover por vertice."""
    xs, ys, zs, ts = [], [], [], []
    for (x, y, z), t in zip(points, texts):
        if x is None:
            xs.append(None); ys.append(None); zs.append(None); ts.append(None)
        else:
            xs.append(x); ys.append(y); zs.append(z); ts.append(t)
    return go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines",
        line=dict(width=width, color=color, dash=dash),
        name=name, text=ts, hoverinfo="text",
    )


def build_beams(beams, zlvl):
    """Una traza por (nivel, seccion)."""
    traces = []
    order = []
    for lvl in LEVELS_ALL:
        bl = beams[beams["level"].astype(str) == lvl]
        for sec in SECTION_COLORS:
            bs = bl[bl["section"].astype(str) == sec]
            if bs.empty:
                continue
            xs, ys, zs, ts = [], [], [], []
            for _, r in bs.iterrows():
                z = zlvl[lvl]
                xs += [fnum(r.x1_m), fnum(r.x2_m), None]
                ys += [fnum(r.y1_m), fnum(r.y2_m), None]
                zs += [z, z, None]
                ts += [f"{r.beam_id}<br>{sec}<br>nivel {lvl}<br>x1,y1 = {fnum(r.x1_m):.3f},{fnum(r.y1_m):.3f}<br>x2,y2 = {fnum(r.x2_m):.3f},{fnum(r.y2_m):.3f}", None, None]
            traces.append(go.Scatter3d(
                x=xs, y=ys, z=zs, mode="lines",
                line=dict(width=8, color=SECTION_COLORS[sec]),
                name=f"{sec} {lvl}", text=ts, hoverinfo="text",
                legendgroup=sec, showlegend=lvl == "L1",
            ))
            order.append((lvl, sec))
    return traces, order


def build_columns(col_seg, zlvl):
    """Una traza por columna (todos los segmentos)."""
    traces = []
    for pid, grp in col_seg.groupby("parent_id"):
        x, y = fnum(grp.iloc[0]["x_m"]), fnum(grp.iloc[0]["y_m"])
        arr = sorted(grp.to_dict("records"), key=lambda d: zlvl[str(d["from_level"])])
        xs, ys, zs, ts = [], [], [], []
        for seg in arr:
            z1, z2 = zlvl[str(seg["from_level"])], zlvl[str(seg["to_level"])]
            xs += [x, x, None]; ys += [y, y, None]; zs += [z1, z2, None]
            ts += [f"{pid}<br>{seg['section']}<br>{seg['from_level']} - {seg['to_level']}", None, None]
        traces.append(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(width=10, color=COL_COLOR),
            name=pid, text=ts, hoverinfo="text", legendgroup="col",
            showlegend=False,
        ))
    return traces


def build_walls(wall_seg, zlvl):
    """Una traza por muro (todos los segmentos)."""
    traces = []
    for pid, grp in wall_seg.groupby("parent_id"):
        first = grp.iloc[0]
        x1, y1, x2, y2 = (fnum(first[c]) for c in ("x1_m", "y1_m", "x2_m", "y2_m"))
        arr = sorted(grp.to_dict("records"), key=lambda d: zlvl[str(d["from_level"])])
        xs, ys, zs, ts = [], [], [], []
        for seg in arr:
            z1, z2 = zlvl[str(seg["from_level"])], zlvl[str(seg["to_level"])]
            for (px, py) in ((x1, y1), (x2, y2)):
                xs += [px, px, None]; ys += [py, py, None]; zs += [z1, z2, None]
                ts += [f"{pid}<br>e = {fnum(first['thickness_m']):.3f} m<br>{seg['from_level']} - {seg['to_level']}", None, None]
        traces.append(go.Scatter3d(
            x=xs, y=ys, z=zs, mode="lines",
            line=dict(width=12, color=WALL_COLOR),
            name=pid, text=ts, hoverinfo="text", legendgroup="wall",
            showlegend=False,
        ))
    return traces


def build_grid(gx, gy, zlvl):
    """Rejilla X/Y por nivel (gris)."""
    traces = []
    xs_ax = [fnum(r.x_m) for _, r in gx.iterrows()]
    ys_ax = [fnum(r.y_m) for _, r in gy.iterrows()]
    for lvl in LEVELS_ALL:
        z = zlvl[lvl]
        xspan = (min(xs_ax) - 0.25, max(xs_ax) + 0.25)
        yspan = (min(ys_ax) - 0.25, max(ys_ax) + 0.25)
        gx_list, gy_list, gz_list = [], [], []
        for x in xs_ax:
            gx_list += [x, x, None]; gy_list += [yspan[0], yspan[1], None]; gz_list += [z, z, None]
        for y in ys_ax:
            gx_list += [xspan[0], xspan[1], None]; gy_list += [y, y, None]; gz_list += [z, z, None]
        traces.append(go.Scatter3d(
            x=gx_list, y=gy_list, z=gz_list, mode="lines",
            line=dict(width=1, color="rgba(120,120,120,0.45)"),
            name=f"ejes {lvl}", text=None, hoverinfo="skip",
            legendgroup="grid", showlegend=False,
        ))
    return traces


def build_masters(zlvl, xm=15.675, ym=8.073):
    """MASTER node traces propuestos (archivo futuro)."""
    traces = []
    xs, ys, zs, ts = [], [], [], []
    for lvl in LEVELS_ALL:
        z = zlvl[lvl]
        xs.append(xm); ys.append(ym); zs.append(z)
        ts.append(f"NM_{lvl}<br>master propuesto<br>x,y = {xm:.3f},{ym:.3f}<br>z = {z:.3f}")
    traces.append(go.Scatter3d(
        x=xs, y=ys, z=zs, mode="markers+text",
        marker=dict(size=7, color=MASTER_COLOR, symbol="diamond"),
        text=ts,
        textposition="top center", textfont=dict(size=9, color=MASTER_COLOR),
        name="master (propuesto)", hoverinfo="text",
    ))
    return traces


def main():
    out = FIGD / "lt2_geometry_interactive.html"
    levels, gx, gy, cols, walls, beams, col_seg, wall_seg, axx, ayy, zlvl = load()

    col_traces = build_columns(col_seg, zlvl)
    wall_traces = build_walls(wall_seg, zlvl)
    beam_traces, beam_order = build_beams(beams, zlvl)
    grid_traces = build_grid(gx, gy, zlvl)
    master_traces = build_masters(zlvl)
    traces = col_traces + wall_traces + beam_traces + grid_traces + master_traces

    n_col = len(col_traces)
    n_wall = len(wall_traces)
    beam_start = n_col + n_wall
    print(f"traces: {len(traces)}  (col {n_col}, wall {n_wall}, "
          f"beam {len(beam_traces)}, grid {len(grid_traces)}, master {len(master_traces)})")
    assert len(traces) == beam_start + len(beam_traces) + len(grid_traces) + len(master_traces)

    def visible_for(beam_levels):
        vis = [True] * len(traces)
        for i, (bl, _sec) in enumerate(beam_order):
            vis[beam_start + i] = bl in beam_levels
        return vis

    steps = [dict(label="Todos", method="restyle", args=[{"visible": visible_for(set(LEVELS_ALL))}])]
    for lvl in LEVELS_ALL:
        steps.append(dict(label=lvl, method="restyle", args=[{"visible": visible_for({lvl})}]))

    fig = go.Figure(data=traces)
    zmin = min(zlvl.values()); zmax = max(zlvl.values())
    fig.update_layout(
        title=dict(text="Edificio de Ingenieria - LT2 - Viewer 3D interactivo", font=dict(size=16)),
        scene=dict(
            xaxis=dict(title="X [m]"), yaxis=dict(title="Y [m]"), zaxis=dict(title="Z [m]"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=1.2, z=1.6)),
        ),
        height=820,
        sliders=[dict(
            active=0, y=0.02,
            steps=steps,
            font=dict(size=12),
        )],
    )
    fig.write_html(out, include_plotlyjs=True, full_html=True)
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()