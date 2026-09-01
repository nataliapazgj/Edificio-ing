# -*- coding: utf-8 -*-
"""Tests del BLOQUE 3: cargas gravitacionales LT2 (L1-L4) sobre vigas."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))

import gravity_loads  # noqa: E402

LEVELS = gravity_loads.LEVELS
STEP = gravity_loads.STEP
TAG_BEAM_BASE = gravity_loads.TAG_BEAM_BASE
Q_G = gravity_loads.Q_G

EXPECTED_TOTAL = 11541.2916  # kN (beam_gravity_loads_LT2, L1-L4, beams)
N_BEAMS = 184


@pytest.fixture(scope="module")
def point_loads():
    pts, cells = gravity_loads.build_point_loads()
    return pts, cells


@pytest.fixture(scope="module")
def pts(point_loads):
    return point_loads[0]


@pytest.fixture(scope="module")
def cells(point_loads):
    return point_loads[1]


@pytest.fixture(scope="module")
def expected():
    return gravity_loads.expected_beam_loads().set_index(["level", "beam_id"])


# ---------------------------------------------------------------------------
# estructura / alcance
# ---------------------------------------------------------------------------
def test_columnas_de_puntos(pts):
    for c in ["level", "beam_id", "element_tag", "L", "xloc", "load_kN", "k", "s_m"]:
        assert c in pts.columns


def test_solo_L1_a_L4_y_solo_vigas(pts):
    assert set(pts["level"].unique()) == set(LEVELS)
    assert not pts.empty


def test_numero_de_vigas(pts):
    assert pts["beam_id"].nunique() == N_BEAMS


def test_cargas_positivas_y_xloc_valido(pts):
    assert (pts["load_kN"] > 0).all()
    assert (pts["xloc"] >= -1e-9).all()
    assert (pts["xloc"] <= 1 + 1e-9).all()


def test_beam_ids_validos(pts):
    beam_ids = set(gravity_loads.load_beams()["beam_id"])
    assert set(pts["beam_id"]).issubset(beam_ids)


def test_tags_trazables(pts):
    tag_map = dict(zip(gravity_loads.load_beams()["beam_id"],
                       TAG_BEAM_BASE + gravity_loads.load_beams().index))
    for _, r in pts.iterrows():
        assert int(r["element_tag"]) == tag_map[r["beam_id"]]


# ---------------------------------------------------------------------------
# conservacion de fuerza total (global y por viga)
# ---------------------------------------------------------------------------
def test_carga_total_igual_esperado(pts):
    tot = pts["load_kN"].sum()
    assert tot == pytest.approx(EXPECTED_TOTAL, abs=1e-2)


def test_carga_por_viga_igual_esperado(pts, expected):
    for (lv, bid), g in pts.groupby(["level", "beam_id"]):
        assert g["load_kN"].sum() == pytest.approx(
            expected.loc[(lv, bid), "total_slab_load_kN"], rel=1e-4)


def test_carga_por_nivel(pts):
    for lv in LEVELS:
        sub = pts[pts["level"] == lv]
        assert sub["load_kN"].sum() == pytest.approx(
            EXPECTED_TOTAL / len(LEVELS), rel=1e-4)


# ---------------------------------------------------------------------------
# conservacion de primer momento (vs geometrias de celdas fuente)
# ---------------------------------------------------------------------------
def test_primer_momento_conservado_global(pts, cells):
    m_app = float((pts["load_kN"] * pts["s_m"]).sum())
    m_exp = float(sum(c["M"] for c in cells.values()))
    assert m_app == pytest.approx(m_exp, rel=1e-6)


def test_primer_momento_conservado_por_viga(pts, cells):
    for key, g in pts.groupby(["level", "beam_id"]):
        c = cells.get(key)
        if c is None:
            continue
        m_app = float((g["load_kN"] * g["s_m"]).sum())
        assert m_app == pytest.approx(c["M"], rel=1e-6)