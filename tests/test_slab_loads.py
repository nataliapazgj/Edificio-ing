"""Pruebas de definicion de cargas de losa LT2 (q_G)."""

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
LOADS = ROOT / "data" / "loads"

G = 9.81
DENSITY_DEFAULT = 2500.0


@pytest.fixture(scope="module")
def slabs():
    return pd.read_csv(LOADS / "slabs_LT2.csv", dtype={"slab_id": str, "level": str})


@pytest.fixture(scope="module")
def lineals():
    return pd.read_csv(LOADS / "linear_loads_LT2.csv", dtype=str)


def row(slabs, sid):
    return slabs[slabs["slab_id"] == sid].iloc[0]


def test_columnas_requeridas(slabs):
    required = ["slab_id", "level", "source_plan", "thickness_cm", "thickness_m",
                "density_kg_m3", "self_weight_kg_m2", "finishes_kg_m2",
                "qG_kg_m2", "qG_kN_m2", "status"]
    for c in required:
        assert c in slabs.columns


def test_L1_confirmado(slabs):
    r = row(slabs, "S_L1_TYP")
    assert r["thickness_m"] == pytest.approx(0.15)
    assert r["density_kg_m3"] == pytest.approx(DENSITY_DEFAULT)
    assert r["self_weight_kg_m2"] == pytest.approx(0.15 * DENSITY_DEFAULT)  # 375
    assert r["finishes_kg_m2"] == pytest.approx(260)
    assert r["qG_kg_m2"] == pytest.approx(375 + 260)  # 635
    assert r["qG_kN_m2"] == pytest.approx(635 * G / 1000)  # 6.22935


def test_L2_L3_L4_iguales_a_L1(slabs):
    for sid in ("S_L2_TYP", "S_L3_TYP", "S_L4_TYP"):
        r = row(slabs, sid)
        assert r["thickness_m"] == pytest.approx(0.15)
        assert r["qG_kg_m2"] == pytest.approx(635)
        assert r["qG_kN_m2"] == pytest.approx(6.22935)
        assert r["status"] == "CONFIRMADO_e15"


CONFIRMED = ("S_L1_TYP", "S_L2_TYP", "S_L3_TYP", "S_L4_TYP")


def test_conversion_kg_kN(slabs):
    for sid in CONFIRMED:
        r = row(slabs, sid)
        assert r["qG_kN_m2"] == pytest.approx(r["qG_kg_m2"] * G / 1000)


def test_SC_no_incluida(slabs):
    # q_G debe ser exactamente PP + finishes (sin componente SC)
    for sid in CONFIRMED:
        r = row(slabs, sid)
        assert r["qG_kg_m2"] == pytest.approx(r["self_weight_kg_m2"] + r["finishes_kg_m2"])


def test_L4_confirmado(slabs):
    r = row(slabs, "S_L4_TYP")
    assert r["thickness_m"] == pytest.approx(0.15)
    assert r["self_weight_kg_m2"] == pytest.approx(375)
    assert r["finishes_kg_m2"] == pytest.approx(260)
    assert r["qG_kg_m2"] == pytest.approx(635)


def test_ROOF_pendiente(slabs):
    r = row(slabs, "S_ROOF_TYP")
    assert r["status"] == "PENDING_VISUAL_CONFIRMATION"
    # espesor indefinido: no inventar
    assert pd.isna(r["thickness_m"])


def test_ROOF_finishes_superficial_confirmado(slabs):
    r = row(slabs, "S_ROOF_TYP")
    assert r["finishes_kg_m2"] == pytest.approx(200)
    assert pd.isna(r["qG_kg_m2"])  # sin q_G definitivo sin espesor


def test_carga_lineal_separada(lineals):
    # PM_ADIC = 1500 kg/m como carga lineal separada, no superficial
    r = lineals.iloc[0]
    assert r["level"] == "ROOF"
    assert r["value_kg_m"] == "1500"
    assert float(r["value_kN_m"]) == pytest.approx(1500 * G / 1000)
    assert "lineal" in r["type"].lower() or "linear" in r["type"].lower()
