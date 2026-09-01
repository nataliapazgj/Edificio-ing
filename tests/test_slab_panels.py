# -*- coding: utf-8 -*-
"""Tests del bloque 2A: geometria de panes de losa LT2."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "data" / "loads" / "slab_panels_LT2.csv"
TYP_LEVELS = ["L1", "L2", "L3", "L4"]

CONFIRMED = ("S_L1_TYP", "S_L2_TYP", "S_L3_TYP", "S_L4_TYP")


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(PANELS)


def _polygon_points(s):
    return [(float(v.split(",")[0]), float(v.split(",")[1]))
            for v in str(s).split(";")]


def _area(pts):
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def test_20_panels_por_nivel(df):
    for lvl in TYP_LEVELS + ["ROOF"]:
        assert len(df[df["level"] == lvl]) == 20


def test_plantilla_tipo_reutilizada(df):
    """L1-L4 reutilizan la misma topologia (mismos poligonos)."""
    ref = df[df["level"] == "L1"].set_index("panel_id")["polygon"].sort_index()

    def desig(pids):
        return [str(x).split("_P_")[1] for x in pids]

    ref_desig = desig(ref.index)
    for lvl in TYP_LEVELS[1:]:
        cur = df[df["level"] == lvl].set_index("panel_id")["polygon"].sort_index()
        assert desig(cur.index) == ref_desig
        # la geometria (orden canonico) debe coincidir
        cur_geo = cur.reset_index().sort_values("panel_id")["polygon"].values
        ref_geo = ref.reset_index().sort_values("panel_id")["polygon"].values
        assert (cur_geo == ref_geo).all()


def test_area_tipo_igual_entre_L(df):
    a = df[df["level"] == "L1"]["area_m2"].sum()
    for lvl in TYP_LEVELS[1:]:
        assert df[df["level"] == lvl]["area_m2"].sum() == pytest.approx(a)


def test_roof_area_menor_por_huecos(df):
    """Los huecos de escalera documentados reducen el area de ROOF."""
    area_tip = df[df["level"] == "L1"]["area_m2"].sum()
    area_roof = df[df["level"] == "ROOF"]["area_m2"].sum()
    assert area_roof < area_tip


def test_qg_confirmado_L_y_pendiente_roof(df):
    for lvl in TYP_LEVELS:
        assert ~df[df["level"] == lvl]["qG_kN_m2"].isna().any()
    assert df[df["level"] == "ROOF"]["qG_kN_m2"].isna().all()


def test_qg_conversion_L(df):
    """qG kN/m2 = 635*9.81/1000 para L1-L4."""
    for lvl in TYP_LEVELS:
        vals = df[df["level"] == lvl]["qG_kN_m2"].unique()
        assert all(v == pytest.approx(635 * 9.81 / 1000) for v in vals)


def test_sin_duplicados_ni_poligonos_nulos(df):
    assert not df["panel_id"].duplicated().any()
    for _, p in df.iterrows():
        assert _area(_polygon_points(p["polygon"])) > 0


def test_thickness_tipo_y_pending_roof(df):
    for lvl in TYP_LEVELS:
        assert (df[df["level"] == lvl]["thickness_m"] == 0.15).all()
    assert df[df["level"] == "ROOF"]["thickness_m"].isna().all()


def test_vertices_dentro_del_dominio_modelo(df):
    for _, p in df.iterrows():
        for x, y in _polygon_points(p["polygon"]):
            assert 0.0 <= x <= 32.0
            assert -1.2 <= y <= 17.3


def test_slab_id_coherente(df):
    for lvl in TYP_LEVELS:
        lid = {"L1": "S_L1_TYP", "L2": "S_L2_TYP",
               "L3": "S_L3_TYP", "L4": "S_L4_TYP"}[lvl]
        assert (df[df["level"] == lvl]["slab_id"] == lid).all()
    assert (df[df["level"] == "ROOF"]["slab_id"] == "S_ROOF_TYP").all()
