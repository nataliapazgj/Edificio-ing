"""
Visor 3D del edificio (HTML interactivo + PNG estatico) con Plotly.

Fuente unica de datos: data/processed/unity_model.json (la misma que alimenta
el viewer de Unity). No modifica ni regenera geometria estructural; solo
representa lo ya existente.

Salidas:
  figures/edificio_3d_interactivo.html   (self-contained, abre en navegador)
  figures/edificio_3d_general.png        (vista isometrica)
  results/edificio_3d_check.txt          (verificaciones automaticas)
"""

import json
import math
import os
import re
import sys

import plotly.graph_objects as go

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "processed", "unity_model.json")
OUT_HTML = os.path.join(ROOT, "figures", "edificio_3d_interactivo.html")
OUT_PNG = os.path.join(ROOT, "figures", "edificio_3d_general.png")
OUT_CHECK = os.path.join(ROOT, "results", "edificio_3d_check.txt")

# ── Colores (equivalentes al viewer de Unity) ──────────────────────────────
C_NODO = "#bfc7cc"
C_COL = "#9e9e9e"
C_BEAM = "#3366ff"
C_WALL = "#d87a26"
C_LOAD = "#e633cc"
C_SUP = "#ffd21f"
C_SLAB = "rgba(77, 204, 255, 0.22)"
C_WALL_SURF = "rgba(216, 122, 38, 0.45)"
C_WALL_SURF_LOAD = "rgba(230, 51, 204, 0.45)"

re_section = re.compile(r"e=([0-9.]+)\s*h=([0-9.]+)")


def P(coords):
    # unity: coords almacenadas como [x, y, z] en metros
    return float(coords[0]), float(coords[1]), float(coords[2])


def elem_label(e):
    tipo = {"column": "Columna", "beam": "Viga", "wall": "Muro"}.get(e["type"], e["type"])
    tag = e["elementTag"]
    if e["type"] == "column":
        tag_s = f"C{tag}"
    elif e["type"] == "wall":
        tag_s = f"M{tag}"
    else:
        tag_s = f"B{tag}" if tag >= 0 else "??"
    xi, yi, zi = P(e["coordinates"]["i"])
    xj, yj, zj = P(e["coordinates"]["j"])
    L = math.sqrt((xj - xi) ** 2 + (yj - yi) ** 2 + (zj - zi) ** 2)
    return (f"{tipo} {tag_s}<br>nivel {e['level']} | {e['analysis_status']}"
            f"<br>L = {L:.2f} m | {e['section']}"
            f"<br>({xi:.2f}, {yi:.2f}, {zi:.2f}) -> ({xj:.2f}, {yj:.2f}, {zj:.2f}) m")


def node_label(n):
    return (f"Nodo {n['nodeTag']}<br>nivel {n['level']}"
            f"<br>({n['x']:.2f}, {n['y']:.2f}, {n['z']:.2f}) m")


# ── Carga ───────────────────────────────────────────────────────────────────
M = json.load(open(SRC, encoding="utf-8"))
nodes, elements, supports, slabs = M["nodes"], M["elements"], M["supports"], M["slabs"]

node_by_tag = {n["nodeTag"]: n for n in nodes}


def level_elev(level):
    zs = [n["z"] for n in nodes if n["level"] == level]
    return min(zs) if zs else None


def wall_box(e):
    """Caja/espesor de un muro a partir de los datos EXISTENTES:
    eje (coordenadas node_i->node_j en planta) + seccion 'e=... h=...'.
    Devuelve vertices y triangulos, o None si no hay e/h en la seccion."""
    m = re_section.search(e.get("section") or "")
    if not m:
        return None
    t = float(m.group(1))          # espesor e [m] (de la seccion, no inventado)
    h = float(m.group(2))          # altura h [m] (de la seccion, no inventado)
    x1, y1, z1 = P(e["coordinates"]["i"])
    x2, y2, z2 = P(e["coordinates"]["j"])
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L < 1e-6:
        return None
    nx, ny = -dy / L, dx / L          # normal en planta (espesor)
    ox, oy = nx * t / 2.0, ny * t / 2.0
    zt = z1 + h
    # 8 vertices: cara inferior (z1) y superior (zt)
    v = [
        (x1 - ox, y1 - oy, z1), (x1 + ox, y1 + oy, z1),
        (x2 + ox, y2 + oy, z1), (x2 - ox, y2 - oy, z1),
        (x1 - ox, y1 - oy, zt), (x1 + ox, y1 + oy, zt),
        (x2 + ox, y2 + oy, zt), (x2 - ox, y2 - oy, zt),
    ]
    tris = [
        # inferior
        (0, 1, 2), (0, 2, 3),
        # superior
        (5, 4, 7), (6, 5, 7),
        # laterales
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    return dict(verts=v, tris=tris, h=h, e=t)


def polygon_mesh(poly_xy, z):
    """Triangulacion fan para poligonos planos (losas)."""
    vs = [(p["x"], p["y"], z) for p in poly_xy]
    tris = [(0, i + 1, i + 2) for i in range(len(vs) - 2)]
    return dict(verts=vs, tris=tris)


# ── Verificaciones previas ──────────────────────────────────────────────────
issues = []
checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok:
        issues.append(f"{name}: {detail}")


# Niveles y elevaciones
levels = sorted({n["level"] for n in nodes})
check("niveles", levels == ["P1", "P2", "P3", "P4"],
      f"levels={levels}")

# Conteo de segmentos que se dibujaran == conteo fuente (sin duplicados)
counts = {}
for st, tp in [("FE", "column"), ("FE", "beam"), ("FE", "wall"),
               ("LOAD_ONLY", "beam"), ("LOAD_ONLY", "wall")]:
    n_src = sum(1 for e in elements if e["analysis_status"] == st and e["type"] == tp)
    counts[(st, tp)] = n_src
check("conteo_elementos", sum(counts.values()) == len(elements),
      f"fuente={len(elements)} grupos={sum(counts.values())}")

# NaN / Inf / longitud cero / rango metros
bad = 0
zeros = 0
coords_all = []
for e in elements:
    for k in ("i", "j"):
        c = e["coordinates"][k]
        coords_all.append(tuple(c))
        if any(isinstance(v, float) and (math.isnan(v) or math.isinf(v)) for v in c):
            bad += 1
    xi, yi, zi = P(e["coordinates"]["i"])
    xj, yj, zj = P(e["coordinates"]["j"])
    if math.hypot(xj - xi, yj - yi, zj - zi) < 1e-6:
        zeros += 1
check("nan_inf", bad == 0, f"coincidencias={bad}")
check("longitud_cero", zeros == 0, f"elementos longitud cero={zeros}")
xmin, xmax = min(v[0] for v in coords_all), max(v[0] for v in coords_all)
ymin, ymax = min(v[1] for v in coords_all), max(v[1] for v in coords_all)
zmin, zmax = min(v[2] for v in coords_all), max(v[2] for v in coords_all)
check("unidades_metros",
      abs(xmax) <= 100 and abs(ymax) <= 100 and abs(zmax) <= 30,
      f"rango x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]")

# ── Construccion de la figura ───────────────────────────────────────────────
fig = go.Figure()


def add_lines(name, color, width, elems, legend=True, legendgroup=None):
    x, y, z, text = [], [], [], []
    for e in elems:
        xi, yi, zi = P(e["coordinates"]["i"])
        xj, yj, zj = P(e["coordinates"]["j"])
        x += [xi, xj, None]
        y += [yi, yj, None]
        z += [zi, zj, None]
        lab = elem_label(e)
        text += [lab, lab, None]
    fig.add_trace(go.Scatter3d(
        x=x, y=y, z=z, mode="lines",
        line=dict(color=color, width=width),
        hoverinfo="text", hovertext=text,
        name=name, showlegend=legend,
        legendgroup=legendgroup if legendgroup else name,
    ))


fe_cols = [e for e in elements if e["analysis_status"] == "FE" and e["type"] == "column"]
fe_beams = [e for e in elements if e["analysis_status"] == "FE" and e["type"] == "beam"]
fe_walls = [e for e in elements if e["analysis_status"] == "FE" and e["type"] == "wall"]
lo = [e for e in elements if e["analysis_status"] == "LOAD_ONLY"]

add_lines(f"Columnas ({len(fe_cols)})", C_COL, 9, fe_cols)
add_lines(f"Vigas ({len(fe_beams)})", C_BEAM, 5, fe_beams)
add_lines(f"Muros ({len(fe_walls)})", C_WALL, 5, fe_walls, legendgroup="muros")
add_lines(f"Solo-carga ({len(lo)})", C_LOAD, 5, lo)

# Nodos
fig.add_trace(go.Scatter3d(
    x=[n["x"] for n in nodes], y=[n["y"] for n in nodes], z=[n["z"] for n in nodes],
    mode="markers", marker=dict(size=2.2, color=C_NODO, opacity=0.9),
    hoverinfo="text", hovertext=[node_label(n) for n in nodes],
    name=f"Nodos ({len(nodes)})",
))

# Apoyos base fija (16)
sup_tags = [s["nodeTag"] for s in supports]
sup_nodes = [node_by_tag[t] for t in sup_tags if t in node_by_tag]
fig.add_trace(go.Scatter3d(
    x=[n["x"] for n in sup_nodes], y=[n["y"] for n in sup_nodes], z=[n["z"] for n in sup_nodes],
    mode="markers", marker=dict(size=6, color=C_SUP, symbol="square", line=dict(color="#1a1a1a", width=1)),
    hoverinfo="text",
    hovertext=[f"Nodo {n['nodeTag']} (apoyo, base fija 6 DOF)<br>nivel {n['level']}" for n in sup_nodes],
    name=f"Apoyos base ({len(sup_nodes)})",
))

# Muros: superficie fisica (e y h tomados de la seccion, no inventados)
for e in elements:
    if e["type"] != "wall":
        continue
    box = wall_box(e)
    if box is None:
        continue
    x = [v[0] for v in box["verts"]]
    y = [v[1] for v in box["verts"]]
    z = [v[2] for v in box["verts"]]
    ii = [t[0] for t in box["tris"]]
    jj = [t[1] for t in box["tris"]]
    kk = [t[2] for t in box["tris"]]
    color = C_WALL_SURF if e["analysis_status"] == "FE" else C_WALL_SURF_LOAD
    label = (f"Muro M{e['elementTag']} | superficie e={box['e']:.2f} m, "
             f"h={box['h']:.2f} m (seccion)")
    fig.add_trace(go.Mesh3d(
        x=x, y=y, z=z, i=ii, j=jj, k=kk,
        color=color, opacity=0.55, flatshading=True,
        hoverinfo="text", text=[label] * 8, showscale=False,
        name="Superficie de muros", legendgroup="muros",
        showlegend=(e is fe_walls[0]) if fe_walls else False,
    ))

# Losas (forjados) por nivel
for s in slabs:
    zs = level_elev(s["level"])
    if zs is None:
        continue
    pm = polygon_mesh(s["polygon"], zs)
    x = [v[0] for v in pm["verts"]]
    y = [v[1] for v in pm["verts"]]
    z = [v[2] for v in pm["verts"]]
    ii = [t[0] for t in pm["tris"]]
    jj = [t[1] for t in pm["tris"]]
    kk = [t[2] for t in pm["tris"]]
    label = (f"Losa {s['slab_id']} | nivel {s['level']} | z={zs:.2f} m"
             f"<br>area {s['area_m2']:.2f} m2 | q_G {s['q_G_kN_m2']} kN/m2 | {s['status']}")
    fig.add_trace(go.Mesh3d(
        x=x, y=y, z=z, i=ii, j=jj, k=kk,
        color="rgba(77, 204, 255, 0.20)", opacity=0.35, flatshading=True,
        hoverinfo="text", text=[label] * len(pm["verts"]), showscale=False,
        name=f"Forjado {s['level']}",
    ))

# ── Layout ──────────────────────────────────────────────────────────────────
camera = dict(eye=dict(x=1.50, y=1.50, z=0.95), up=dict(x=0, y=0, z=1))
fig.update_layout(
    title=dict(
        text=(f"Edificio 3D - Modelo estructural (Semana 2)<br>"
              f"<sup>{len(nodes)} nodos · {len(elements)} elementos "
              f"({counts[('FE','column')]} col, {counts[('FE','beam')]} vigas, "
              f"{counts[('FE','wall')]} muros FE + {counts[('LOAD_ONLY','beam')]} vigas, "
              f"{counts[('LOAD_ONLY','wall')]} muros solo-carga) · "
              f"{len(supports)} apoyos · {len(slabs)} losas · niveles {', '.join(levels)}</sup>"),
        x=0.5),
    scene=dict(
        xaxis=dict(title="X [m]", showbackground=False),
        yaxis=dict(title="Y [m]", showbackground=False),
        zaxis=dict(title="Z [m]", showbackground=False),
        aspectmode="data",
        camera=camera,
    ),
    legend=dict(x=0.02, y=0.98, bgcolor="rgba(255,255,255,0.85)", font=dict(size=11)),
    margin=dict(l=0, r=0, t=70, b=0),
    dragmode="turntable",
)

# ── Guardado ────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
os.makedirs(os.path.dirname(OUT_CHECK), exist_ok=True)

fig.write_html(OUT_HTML, include_plotlyjs=True, auto_open=False, config={"scrollZoom": True})
fig.write_image(OUT_PNG, width=1600, height=1050, scale=2)

# ── Verificaciones post-generacion ──────────────────────────────────────────
html_ok = os.path.exists(OUT_HTML) and os.path.getsize(OUT_HTML) > 500_000
png_ok = os.path.exists(OUT_PNG) and os.path.getsize(OUT_PNG) > 50_000
html_self = False
if os.path.exists(OUT_HTML):
    with open(OUT_HTML, encoding="utf-8") as f:
        data = f.read()
    ext_scripts = len(re.findall(r'<script[^>]*src=', data))
    ext_links = any(h.startswith("http") for h in re.findall(r'<link[^>]*href="([^"]+)"', data))
    html_self = (ext_scripts == 0) and (not ext_links) and ("plotly" in data.lower())
check("html_generado", html_ok, f"size={os.path.getsize(OUT_HTML) if os.path.exists(OUT_HTML) else 0} b")
check("html_self_contained", html_self, "sin dependencias externas (plotly.js embebido)")
check("png_generado", png_ok, f"size={os.path.getsize(OUT_PNG) if os.path.exists(OUT_PNG) else 0} b")

# ── Reporte ─────────────────────────────────────────────────────────────────
lines = [
    "Verificaciones - Visor 3D independiente (figures/edificio_3d_*.{html,png})",
    f"Fuente: {os.path.relpath(SRC, ROOT)}",
    "",
]
for name, ok, detail in checks:
    lines.append(f"[{'PASS' if ok else 'FAIL'}] {name} -> {detail}")
lines.append("")
lines.append("VEREDICTO: " + ("PASS" if not issues else f"PROBLEMAS: {'; '.join(issues)}"))
with open(OUT_CHECK, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("\n".join(lines))
print()
for name, ok, detail in checks:
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")
print()
print(f"HTML : {os.path.abspath(OUT_HTML)}")
print(f"PNG  : {os.path.abspath(OUT_PNG)}")
print(f"Check: {os.path.abspath(OUT_CHECK)}")
sys.exit(0 if not issues else 1)