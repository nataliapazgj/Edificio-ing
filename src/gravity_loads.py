# -*- coding: utf-8 -*-
"""BLOQUE 3 — Cargas gravitacionales en el modelo OpenSees (L1-L4).

Consume las salidas del BLOQUE 2B (data/loads/tributary_areas_LT2.csv) y
convierte cada area tributaria BEAM de L1-L4 en una distribucion longitudinal
de carga sobre la viga receptora, aplicable con `eleLoad -beamPoint`.

Rastreabilidad: paño -> area tributaria -> beam_id -> element_tag -> xloc -> P.

Metodo (documentado, sin inventar distribuciones):
- La celda de muestreo 2B es un cuadrado STEP=0.05 m centrado en la grilla del
  paño. Para cada area tributaria se regenera la grilla del paño y se
  conservan las celdas cuyo centro cae dentro del poligono tributario
  (misma regla geometrica que genero el CSV).
- La tabla 2B renorma por paño; aqui se renorma por tributaria al area_m2 del
  CSV, con lo que cada fila cierra EXACTAMENTE a su carga declarada.
- Cada celda aporta P = Q_G*STEP^2 sobre la viga, en su proyeccion perpendicular
  con clamp al segmento (la misma regla de asignacion de 2B).
- Las celdas se agrupan en franjas de ancho STEP a lo largo de la viga. Cada
  franja se sustituye por UN punto equivalente (-beamPoint) situado en el
  centro de masa longitudinal de sus celdas: fuerza total y primer momento
  respecto del extremo se preservan EXACTAMENTE por construccion.

Salidas (resultados de trabajo, no fuente de datos):
  results/gravity_loads_applied_LT2.csv   -> cargas punto por viga (xloc,P)
  results/gravity_loads_beam_summary_LT2.csv -> metricas por viga
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.vectorized import contains as vec_contains
from shapely import contains_xy

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
LOADS = ROOT / "data" / "loads"
RES = ROOT / "results"

BEAMS_CSV = GEOM / "beams_LT2.csv"
LEVELS_CSV = GEOM / "levels.csv"
PANELS_CSV = LOADS / "slab_panels_LT2.csv"
TRIB_CSV = LOADS / "tributary_areas_LT2.csv"
BEAM_LOAD_CSV = LOADS / "beam_gravity_loads_LT2.csv"

OUT_POINTS = RES / "gravity_loads_applied_LT2.csv"
OUT_BEAMS = RES / "gravity_loads_beam_summary_LT2.csv"

Q_G = 6.22935  # kN/m2, planta tipo L1-L4
STEP = 0.05    # tamano de celda del muestreo 2B
LEVELS = ["L1", "L2", "L3", "L4"]
TAG_BEAM_BASE = 2001


# ---------------------------------------------------------------------------
# helpers CSV
# ---------------------------------------------------------------------------
def _bbox_of_ring(s):
    """Cadena de puntos 'x,y;x,y;...' -> bbox (x0,y0,x1,y1)."""
    pts = [tuple(map(float, t.split(","))) for t in
           (str(s).replace(", ", ",").split(";"))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _poly_of_rings(s):
    """'>polygon' (anillos por '|') -> geometria (Polygon/MultiPolygon)."""
    shapes = []
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return None
    for rstr in str(s).split("|"):
        rstr = rstr.strip()
        if not rstr:
            continue
        pts = []
        for tok in rstr.split(";"):
            tok = tok.strip()
            if not tok:
                continue
            try:
                pts.append(tuple(map(float, tok.split(","))))
            except ValueError:
                continue
        if len(pts) >= 3:
            shapes.append(Polygon(pts))
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]
    return unary_union(shapes)


# ---------------------------------------------------------------------------
# agregados bases
# ---------------------------------------------------------------------------
def load_beams():
    """beams_LT2.csv con tag = TAG_BEAM_BASE + indice global de fila."""
    beams = pd.read_csv(BEAMS_CSV)
    beams = beams.reset_index(drop=True)
    beams["tag"] = TAG_BEAM_BASE + beams.index
    return beams


def expected_beam_loads():
    """beam_gravity_loads_LT2.csv (filas TRANSFERIDO L1-L4)."""
    df = pd.read_csv(BEAM_LOAD_CSV)
    return df[(df.receiver_type == "BEAM")
              & (df.level.isin(LEVELS))
              & (df.status == "TRANSFERIDO")].copy()


def tributary_rows():
    """Areas tributarias BEAM L1-L4 (fuente de distribucion)."""
    df = pd.read_csv(TRIB_CSV)
    return df[(df.receiver_type == "BEAM")
              & (df.level.isin(LEVELS))
              & (df.status == "TRANSFERIDO")].copy()


# ---------------------------------------------------------------------------
# distribucion longitudinal exacta
# ---------------------------------------------------------------------------
def _panel_grid(panel):
    """Grilla de centros de celda del paño (mismo muestreo que 2B)."""
    x0, y0, x1, y1 = panel
    xs = np.arange(x0 + STEP / 2, x1, STEP)
    ys = np.arange(y0 + STEP / 2, y1, STEP)
    if xs.size == 0 or ys.size == 0:
        return np.empty(0), np.empty(0)
    xg, yg = np.meshgrid(xs, ys)
    return xg.ravel(), yg.ravel()


def _project_onto_beam(cx, cy, p0x, p0y, dx, dy, L2):
    """Proyeccion perpendicular con clamp al segmento (regla 2B)."""
    t = ((cx - p0x) * dx + (cy - p0y) * dy) / L2
    return np.clip(t, 0.0, 1.0)


def build_point_loads():
    """Cargas punto por viga (level, beam_id, element_tag, L, xloc, P, k).

    La fuerza total y el primer momento respecto del extremo inicial de la
    viga se preservan exactamente respecto de la geometria de celdas 2B.
    """
    beams = load_beams()
    trib = tributary_rows()
    panels = pd.read_csv(PANELS_CSV)

    panel_bbox = {}
    for _, pr in panels.iterrows():
        panel_bbox[pr.panel_id] = _bbox_of_ring(pr.polygon)

    beam_geom = {}
    for _, br in beams.iterrows():
        beam_geom[br.beam_id] = dict(
            x1=float(br.x1_m), y1=float(br.y1_m),
            x2=float(br.x2_m), y2=float(br.y2_m),
            L=math.hypot(float(br.x2_m) - float(br.x1_m),
                         float(br.y2_m) - float(br.y1_m)))

    da = STEP * STEP
    rows = []          # filas de puntos aplicables (por franja)
    per_beam_cells = {}  # para momentos "esperados" desde celdas

    groups = trib.groupby("panel_id", sort=False)
    for panel_id, g in groups:
        bbox = panel_bbox.get(panel_id)
        if bbox is None:
            continue
        cx, cy = _panel_grid(bbox)
        if cx.size == 0:
            continue
        for _, tr in g.iterrows():
            geom = _poly_of_rings(tr.polygon)
            if geom is None:
                continue
            inside = contains_xy(geom, cx, cy)
            n_sel = int(inside.sum())
            if n_sel == 0:
                continue
            renorm = float(tr.area_m2) / (n_sel * da)
            gx = cx[inside]
            gy = cy[inside]

            bg = beam_geom.get(tr.beam_id)
            if bg is None:
                continue
            dx = bg["x2"] - bg["x1"]
            dy = bg["y2"] - bg["y1"]
            L = bg["L"]
            L2 = max(dx * dx + dy * dy, 1e-12)
            s = _project_onto_beam(gx, gy, bg["x1"], bg["y1"], dx, dy, L2) * L

            pcell = np.full(n_sel, Q_G * da * renorm, dtype=float)
            nmax = max(1, int(np.ceil(L / STEP - 1e-9)))
            k = np.minimum((s / STEP).astype(int), nmax - 1)
            # agregacion por franja de ancho STEP
            sump = np.bincount(k, weights=pcell, minlength=nmax)
            sumps = np.bincount(k, weights=pcell * s, minlength=nmax)
            active = np.nonzero(sump > 0)[0]
            for ki in active:
                sc = sumps[ki] / sump[ki]
                rows.append({
                    "level": tr.level,
                    "beam_id": tr.beam_id,
                    "element_tag": int(tr.element_tag),
                    "L": round(L, 6),
                    "xloc": round(sc / L, 9) if L > 0 else 0.0,
                    "load_kN": round(float(sump[ki]), 9),
                    "k": int(ki),
                    "s_m": round(float(sc), 9),
                })
            key = (tr.level, tr.beam_id)
            acc = per_beam_cells.setdefault(
                key, {"P": 0.0, "M": 0.0, "n": 0, "area": 0.0})
            acc["P"] += float((pcell * np.ones(n_sel)).sum())
            acc["M"] += float((pcell * s).sum())
            acc["n"] += n_sel
            acc["area"] += float(pcell.sum()) / Q_G

    df = pd.DataFrame(rows)
    return df, per_beam_cells


def beam_summary(points, per_beam_cells):
    """Metricas por viga: esperado vs aplicado (fuerza y primer momento)."""
    beams = load_beams()
    beam_idx = {(b.level, b.beam_id): i for i, b in
                enumerate(beams.itertuples())}
    exp = expected_beam_loads().set_index(["level", "beam_id"])

    rows = []
    for (lv, bid), cells in per_beam_cells.items():
        sub = points[(points.level == lv) & (points.beam_id == bid)]
        P_app = float(sub["load_kN"].sum())
        M_app = float((sub["load_kN"] * sub["s_m"]).sum())
        P_exp = float(exp.loc[(lv, bid), "total_slab_load_kN"])
        # momento esperado: desde las celdas (geometria fuente exacta 2B)
        M_exp = cells["M"]
        rows.append({
            "level": lv,
            "beam_id": bid,
            "element_tag": int(beams.iloc[beam_idx[(lv, bid)]]["tag"]),
            "length_m": round(float(sub["L"].iloc[0]) if len(sub) else 0.0, 6),
            "tributary_load_kN": round(P_exp, 6),
            "applied_load_kN": round(P_app, 9),
            "abs_err_load_kN": round(abs(P_app - P_exp), 9),
            "rel_err_load": abs(P_app - P_exp) / max(abs(P_exp), 1e-12),
            "expected_first_moment_kN_m": round(M_exp, 9),
            "applied_first_moment_kN_m": round(M_app, 9),
            "abs_err_moment_kN_m": round(abs(M_app - M_exp), 9),
            "rel_err_moment": abs(M_app - M_exp)
            / max(abs(M_exp), 1e-12),
            "n_loads": int(len(sub)),
        })
    return pd.DataFrame(rows)


def distribution_shape(w):
    """nivela el perfil w(s): uniforme / triangular / trapezoidal.

    Las celdas extremo de una viga son parciales (borde del poligono), por lo
    que la clasificacion se hace sobre las franjas INTERIORES.
    """
    w = np.asarray(w, dtype=float)
    if w.size == 0:
        return "sin_carga"
    core = w if w.size < 3 else w[1:-1]
    denom = max(float(np.abs(core).max()), 1e-12)
    if (np.ptp(core) / denom) < 1e-3:
        return "uniforme"
    # ajuste lineal minimos cuadrados sobre el perfil interior
    x = np.arange(core.size, dtype=float)
    a, b = np.polyfit(x, core, 1)
    resid = np.abs(core - (a + b * x))
    if resid.max() / denom < 0.05:
        lo = a + b * (core.size - 1)
        if min(a, lo) / denom < 0.10 and max(a, lo) / denom > 0.60:
            return "triangular"
    return "trapezoidal"


def distribution_profile(level, points=None):
    """Perfil w(s) por franja para un nivel (para figura/analisis)."""
    if points is None:
        points, _ = build_point_loads()
    sub = points[points.level == level].copy()
    out = []
    for bid, g in sub.groupby("beam_id", sort=False):
        nmax = int(max(g["k"])) + 1
        w = np.zeros(nmax)
        w[g["k"].to_numpy()] = g["load_kN"].to_numpy() / STEP
        out.append({
            "beam_id": bid,
            "level": level,
            "n_strips": nmax,
            "shape": distribution_shape(w),
            "w_kN_m": w,
        })
    return out


def export():
    points, cells = build_point_loads()
    if points.empty:
        raise SystemExit("sin cargas punto generadas (revisar fuentes 2B)")
    RES.mkdir(parents=True, exist_ok=True)
    points.to_csv(OUT_POINTS, index=False)
    summ = beam_summary(points, cells)
    summ.to_csv(OUT_BEAMS, index=False)
    print(f"Escrito: {OUT_POINTS}  ({len(points)} puntos)")
    print(f"Escrito: {OUT_BEAMS}  ({len(summ)} vigas)")
    for lv in LEVELS:
        sub = points[points.level == lv]
        print(f"  {lv}: vigas={sub.beam_id.nunique()} "
              f"puntos={len(sub)} P={sub.load_kN.sum():.4f} kN")
    print(f"  TOTAL aplicado = {points.load_kN.sum():.6f} kN")
    tot_exp = float(expected_beam_loads()["total_slab_load_kN"].sum())
    print(f"  TOTAL esperado (beam_gravity_loads) = {tot_exp:.6f} kN")
    return points, summ


if __name__ == "__main__":
    export()