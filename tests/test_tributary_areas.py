# -*- coding: utf-8 -*-
"""Tests del bloque 2B: areas tributarias y transferencia qG a vigas (LT2)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
LOAD = ROOT / "data" / "loads"

LEVELS = ["L1", "L2", "L3", "L4"]
Q_G = 635 * 9.81 / 1000  # 6.22935 kN/m2
TAG_BEAM_BASE = 2001


@pytest.fixture(scope="module")
def trib():
    return pd.read_csv(LOAD / "tributary_areas_LT2.csv")


@pytest.fixture(scope="module")
def bload():
    return pd.read_csv(LOAD / "beam_gravity_loads_LT2.csv")


@pytest.fixture(scope="module")
def panels():
    return pd.read_csv(LOAD / "slab_panels_LT2.csv")


@pytest.fixture(scope="module")
def beams():
    return pd.read_csv(GEOM / "beams_LT2.csv")


def _pts(s):
    """>polygon (anillos por '|') -> lista de anillos."""
    rings = []
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return rings
    for rstr in str(s).split("|"):
        rstr = rstr.strip()
        if not rstr:
            continue
        pts = []
        for tok in rstr.split(";"):
            tok = tok.strip()
            if not tok:
                continue
            p = tok.split(",")
            if len(p) != 2:
                continue
            pts.append((float(p[0]), float(p[1])))
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def _poly(s):
    rings = _pts(s)
    if not rings:
        return None
    if len(rings) == 1:
        return Polygon(rings[0])
    return unary_union([Polygon(r) for r in rings])


# ---------------------------------------------------------------------------
# estructura de archivos
# ---------------------------------------------------------------------------
def test_columnas_tributary(trib):
    required = ["level", "panel_id", "tributary_id", "receiver_type",
                "receiver_id", "beam_id", "element_tag", "area_m2",
                "qG_kN_m2", "load_kN", "polygon", "status"]
    for c in required:
        assert c in trib.columns


def test_columnas_beam_gravity(bload):
    required = ["level", "beam_id", "element_tag", "receiver_type",
                "tributary_area_m2", "total_slab_load_kN", "beam_length_m",
                "equivalent_uniform_load_kN_m", "status"]
    for c in required:
        assert c in bload.columns


def test_solo_L1_a_L4(trib, bload):
    for df in (trib, bload):
        assert set(df["level"].unique()) == set(LEVELS)


def test_ids_unicos(trib):
    assert not trib["tributary_id"].duplicated().any()


def test_filas_beam_y_wall(bload):
    assert (bload["receiver_type"] == "BEAM").sum() == 184
    assert (bload["receiver_type"] == "WALL").sum() == 20


# ---------------------------------------------------------------------------
# conservacion de area: suma tributarias == area neta del pano
# ---------------------------------------------------------------------------
def test_suma_trib_igual_area_neta_por_nivel(trib, panels):
    for lvl in LEVELS:
        net = panels.loc[panels["level"] == lvl, "area_m2"].sum()
        tt = trib.loc[trib["level"] == lvl, "area_m2"].sum()
        assert tt == pytest.approx(net, abs=1e-3)


def test_suma_trib_por_pano(trib, panels):
    for lvl in LEVELS:
        for _, p in panels[panels["level"] == lvl].iterrows():
            sub = trib[(trib["level"] == lvl) & (trib["panel_id"] == p["panel_id"])]
            assert sub["area_m2"].sum() == pytest.approx(p["area_m2"], abs=1e-3)


# ---------------------------------------------------------------------------
# conservacion de carga
# ---------------------------------------------------------------------------
def test_load_igual_qG_por_area(trib, bload):
    for df in (trib,):
        for _, r in df.iterrows():
            assert r["load_kN"] == pytest.approx(r["area_m2"] * Q_G, abs=1e-3)


def test_carga_conservada_por_nivel(trib, panels):
    for lvl in LEVELS:
        net = panels.loc[panels["level"] == lvl, "area_m2"].sum()
        q = trib.loc[trib["level"] == lvl, "load_kN"].sum()
        assert q == pytest.approx(net * Q_G, abs=1e-3)


def test_carga_total(trib):
    q_tot = trib["load_kN"].sum()
    assert q_tot == pytest.approx(1955.2129 * Q_G, abs=1e-3)


# ---------------------------------------------------------------------------
# receptores validos y trazables
# ---------------------------------------------------------------------------
def test_beam_ids_existen_y_tags_trazables(trib, beams):
    beam_ids = set(beams["beam_id"])
    tag_map = dict(zip(beams["beam_id"], TAG_BEAM_BASE + beams.index))
    sub = trib[trib["receiver_type"] == "BEAM"]
    for _, r in sub.iterrows():
        assert r["beam_id"] in beam_ids
        assert int(r["element_tag"]) == tag_map[r["beam_id"]]


def test_wall_rows_element_tag_nulo(trib):
    sub = trib[trib["receiver_type"] == "WALL"]
    assert not sub.empty
    assert sub["element_tag"].isna().all()
    assert (sub["status"] == "WALL_EDGE_PENDING").all()


def test_beam_gravity_coincide_con_tributary(trib, bload):
    agg = (trib[trib["receiver_type"] == "BEAM"]
           .groupby(["level", "beam_id"])[["area_m2", "load_kN"]].sum())
    agg.columns = ["tributary_area_m2", "total_slab_load_kN"]
    merged = bload[bload["receiver_type"] == "BEAM"].merge(
        agg.reset_index(), on=["level", "beam_id"], suffixes=("", "_agg"))
    assert len(merged) == len(bload[bload["receiver_type"] == "BEAM"])
    for _, r in merged.iterrows():
        assert r["tributary_area_m2"] == pytest.approx(r["tributary_area_m2_agg"], abs=1e-4)
        assert r["total_slab_load_kN"] == pytest.approx(r["total_slab_load_kN_agg"], abs=1e-3)


def test_beam_gravity_longitud_y_carga_equivalente(bload):
    sub = bload[bload["receiver_type"] == "BEAM"]
    for _, r in sub.iterrows():
        L = float(r["beam_length_m"])
        assert L > 0
        assert r["equivalent_uniform_load_kN_m"] == pytest.approx(
            r["total_slab_load_kN"] / L, abs=1e-3)


# ---------------------------------------------------------------------------
# geometria de los poligonos tributarios
# ---------------------------------------------------------------------------
def test_poligonos_poblados_y_validos(trib):
    for _, r in trib.iterrows():
        rings = _pts(r["polygon"])
        assert rings, r["tributary_id"]
        assert all(len(x) >= 3 for x in rings), r["tributary_id"]
        shp = _poly(r["polygon"])
        assert shp.is_valid, r["tributary_id"]


def test_poligono_area_coherente(trib):
    for _, r in trib.iterrows():
        shp = _poly(r["polygon"])
        # area del poligono (celdas+redondeo) cercana al area muestreada
        assert shp.area == pytest.approx(r["area_m2"], rel=0.25), r["tributary_id"]


def test_sin_solape_entre_tributarias(trib):
    by_panel = {}
    for _, r in trib.iterrows():
        by_panel.setdefault((r["level"], r["panel_id"]), []).append(_poly(r["polygon"]))
    for key, polys in by_panel.items():
        for a in range(len(polys)):
            for b in range(a + 1, len(polys)):
                ov = polys[a].intersection(polys[b]).area
                assert ov < 1e-6, f"solape {key} {ov:.4f}"


def test_centroide_dentro_del_pano_y_fuera_de_huecos(trib, panels):
    def parse_holes(s):
        out = []
        if not s or (isinstance(s, float) and np.isnan(s)):
            return out
        for hp in str(s).split("|"):
            hp = hp.strip()
            if not hp:
                continue
            out.append(Polygon(_pts(hp)[0]))
        return out

    for lvl in LEVELS:
        for _, p in panels[panels["level"] == lvl].iterrows():
            pshp = _poly(p["polygon"])
            holes = parse_holes(p["holes"])
            for _, r in trib[(trib["level"] == lvl)
                             & (trib["panel_id"] == p["panel_id"])].iterrows():
                shp = _poly(r["polygon"])
                c = shp.representative_point()
                assert pshp.covers(c), r["tributary_id"]
                for h in holes:
                    assert not h.covers(c), f"{r['tributary_id']} en hueco"


# ---------------------------------------------------------------------------
# politicas: sin invencion de dimensiones
# ---------------------------------------------------------------------------
def test_no_hay_datos_de_roof(trib):
    assert "ROOF" not in set(trib["level"])


def test_qG_consistente(trib):
    assert np.allclose(trib["qG_kN_m2"].astype(float), Q_G, atol=1e-6)