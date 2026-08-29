"""Pruebas unitarias del digitador de muros LT2."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import wall_digitizer_lt2 as wd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"


@pytest.fixture(scope="module")
def axes():
    gx = pd.read_csv(GEOM / "grid_x.csv")
    gy = pd.read_csv(GEOM / "grid_y.csv")
    x_axis = {str(a): float(x) for a, x in zip(gx["axis_id"], gx["x_m"])}
    y_axis = {str(a): float(y) for a, y in zip(gy["axis_id"], gy["y_m"])}
    return x_axis, y_axis


def test_eje_sin_offset(axes):
    x_axis, y_axis = axes
    x, y = wd.define_point("B", "2", x_axis, y_axis)
    assert x == pytest.approx(11.250)
    assert y == pytest.approx(8.900)


def test_offset_positivo(axes):
    x_axis, y_axis = axes
    x, y = wd.define_point("A' + 0.20 m", "1A + 0.10", x_axis, y_axis)
    assert x == pytest.approx(0.200)
    assert y == pytest.approx(4.365)


def test_offset_negativo(axes):
    x_axis, y_axis = axes
    x, y = wd.define_point("A - 0.40", "1A - 0.40 m", x_axis, y_axis)
    assert x == pytest.approx(3.350)
    assert y == pytest.approx(3.865)


def test_eje_inexistente(axes):
    x_axis, y_axis = axes
    with pytest.raises(ValueError):
        wd.define_point("Z + 0.10", "1", x_axis, y_axis)


def test_muro_horizontal(axes):
    x_axis, y_axis = axes
    x1, y1 = wd.define_point("A", "2", x_axis, y_axis)
    x2, y2 = wd.define_point("C", "2", x_axis, y_axis)
    w = wd.build_wall("H001", x1, y1, x2, y2, 0.20, "LT2_PTYPE")
    assert w["orientation"] == "X"
    assert w["warning"] is None
    assert w["length"] == pytest.approx(17.500)


def test_muro_vertical(axes):
    x_axis, y_axis = axes
    x1, y1 = wd.define_point("B", "1", x_axis, y_axis)
    x2, y2 = wd.define_point("B", "2", x_axis, y_axis)
    w = wd.build_wall("V001", x1, y1, x2, y2, 0.20, "LT2_PTYPE")
    assert w["orientation"] == "Y"
    assert w["warning"] is None
    assert w["length"] == pytest.approx(8.900)


def test_id_duplicado(axes):
    x_axis, y_axis = axes
    x1, y1 = wd.define_point("A", "1", x_axis, y_axis)
    x2, y2 = wd.define_point("A", "2", x_axis, y_axis)
    with pytest.raises(ValueError):
        wd.build_wall("W001", x1, y1, x2, y2, 0.20, "LT2_PTYPE",
                      existing_ids=["W001"])


def test_exige_thickness_y_source(axes):
    x_axis, y_axis = axes
    x1, y1 = wd.define_point("A", "1", x_axis, y_axis)
    x2, y2 = wd.define_point("A", "2", x_axis, y_axis)
    with pytest.raises(ValueError):
        wd.build_wall("T001", x1, y1, x2, y2, None, "LT2_PTYPE")
    with pytest.raises(ValueError):
        wd.build_wall("T002", x1, y1, x2, y2, 0.2, None)