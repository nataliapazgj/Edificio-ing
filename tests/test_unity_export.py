# -*- coding: utf-8 -*-
"""Tests del BLOQUE 4A: export Unity (data/unity/edificio_lt2.json)."""

from pathlib import Path

import json
import math
import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))

import export_unity_model  # noqa: E402
from build_opensees_model import ModelBuilder  # noqa: E402

OUTFILE = ROOT / "data" / "unity" / "edificio_lt2.json"


@pytest.fixture(scope="module")
def doc():
    with open(OUTFILE, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def builder():
    return ModelBuilder()


# ---------------------------------------------------------------------------
# estructura del documento
# ---------------------------------------------------------------------------
def test_esquema_completo(doc):
    for k in ("meta", "levels", "nodes", "master_nodes", "beams", "columns",
              "walls", "supports", "diaphragms", "slabs"):
        assert k in doc


def test_meta_modelo(doc):
    assert doc["meta"]["model"] == "LT2"
    assert doc["meta"]["units"] == "meters"


def test_niveles(doc):
    names = [l["name"] for l in doc["levels"]]
    assert names == ["B1", "L1", "L2", "L3", "L4", "ROOF"]


# ---------------------------------------------------------------------------
# conteos
# ---------------------------------------------------------------------------
def test_conteos(doc, builder):
    assert len(doc["nodes"]) == len(builder.structural_tags) == 272
    assert len(doc["master_nodes"]) == len(builder.masters) == 5
    assert len(doc["beams"]) == len(builder.beams) == 237
    assert len(doc["columns"]) == len(builder.columns) == 50
    assert len(doc["walls"]) == len(builder.walls) == 40
    assert len(doc["supports"]) == len(builder.supports) == 22
    assert len(doc["diaphragms"]) == len(builder.diaphs) == 5
    assert len(doc["slabs"]) == 100


# ---------------------------------------------------------------------------
# IDs unicos y tags
# ---------------------------------------------------------------------------
def test_ids_unicos(doc):
    assert len({b["beam_id"] for b in doc["beams"]}) == len(doc["beams"])
    assert len({c["column_id"] for c in doc["columns"]}) == len(doc["columns"])
    assert len({w["wall_id"] for w in doc["walls"]}) == len(doc["walls"])
    assert len({m["master_id"] for m in doc["master_nodes"]}) == len(
        doc["master_nodes"])


def test_nodos_tags_1_a_n(doc):
    tags = [n["tag"] for n in doc["nodes"]]
    assert sorted(tags) == list(range(1, 273))


def test_coords_finitas(doc):
    def finite(row, keys):
        return all(math.isfinite(row[k]) for k in keys)
    assert all(finite(n, ("x", "y", "z")) for n in doc["nodes"])
    # beams/columnas van por nodos referenciales
    for b in doc["beams"]:
        assert isinstance(b["node_i"], int) and isinstance(b["node_j"], int)


# ---------------------------------------------------------------------------
# elementTags consistentes
# ---------------------------------------------------------------------------
def test_element_tag_vigas(doc):
    for i, b in enumerate(doc["beams"]):
        assert b["elementTag"] == 2001 + i


def test_element_tag_columnas(doc):
    for i, c in enumerate(doc["columns"]):
        assert c["elementTag"] == 3001 + i


def test_nodos_viga_existen(doc, builder):
    all_tags = set(range(1, 273))
    for b in doc["beams"]:
        assert b["node_i"] in all_tags and b["node_j"] in all_tags


# ---------------------------------------------------------------------------
# muros pendientes
# ---------------------------------------------------------------------------
def test_muros_pending(doc):
    assert all(w["status"] == "PENDING_WALL_CONVENTION" for w in doc["walls"])
    assert all(w["thickness_m"] > 0 and w["nodes"] is not None
               for w in doc["walls"])


# ---------------------------------------------------------------------------
# cargas tributarias (solo vigas BEAM)
# ---------------------------------------------------------------------------
def test_cargas_solo_vigas_beam(doc):
    loads = export_unity_model.load_beam_loads()
    n_loaded = sum(1 for b in doc["beams"]
                   if b["load_status"] != "NO_TRIBUTARY_AREA")
    assert n_loaded == len(loads) == 184
    # las cargas solo en las 184 vigas correctas, con los valores exactos
    for b in doc["beams"]:
        lr = loads.get((b["level"], b["beam_id"]))
        if lr is None:
            assert b["load_status"] == "NO_TRIBUTARY_AREA"
        else:
            assert b["tributary_area_m2"] == pytest.approx(
                lr.tributary_area_m2, abs=1e-6)
            assert b["slab_load_kN"] == pytest.approx(lr.total_slab_load_kN,
                                                      abs=1e-6)


def test_export_es_reproducible(doc):
    # re-exportar y asegurar misma estructura (sin contar timestamp)
    out_path = ROOT / "data" / "unity" / "_tmp_repro.json"
    export_unity_model.export(out_path=out_path)
    with open(out_path, encoding="utf-8") as fh:
        doc2 = json.load(fh)
    out_path.unlink()
    assert len(doc2["nodes"]) == len(doc["nodes"])
    assert len(doc2["beams"]) == len(doc["beams"])
    assert len(doc2["columns"]) == len(doc["columns"])
    assert len(doc2["walls"]) == len(doc["walls"])


# ---------------------------------------------------------------------------
# losas QA (representacion en el viewer)
# ---------------------------------------------------------------------------
def test_losas_20_por_nivel(doc):
    from collections import Counter
    c = Counter(s["level"] for s in doc["slabs"])
    assert c == {"L1": 20, "L2": 20, "L3": 20, "L4": 20, "ROOF": 20}


def test_losas_coinciden_con_fuente(doc):
    panels = export_unity_model.load_slab_panels()
    src_ids = set(panels["panel_id"])
    assert len(doc["slabs"]) == len(panels) == 100
    assert {s["panel_id"] for s in doc["slabs"]} == src_ids
    assert len({s["panel_id"] for s in doc["slabs"]}) == 100


def test_losas_campos_presentes(doc):
    for s in doc["slabs"]:
        assert isinstance(s["panel_id"], str) and s["panel_id"]
        assert s["level"] in {"L1", "L2", "L3", "L4", "ROOF"}
        assert s["area_m2"] > 0
        assert len(s["polygon"].split(";")) >= 3


def test_losas_con_holes_no_plasmados_como_superficie(doc):
    panels = export_unity_model.load_slab_panels()
    n_src = 0
    for r in panels.itertuples():
        if r.holes is not None and not isinstance(r.holes, float) and \
                str(r.holes).strip():
            n_src += 1
    n_doc = sum(1 for s in doc["slabs"] if s["holes"])
    assert n_src == n_doc == 13
    # cada panel conserva el numero de anillos de hole de la fuente
    for r in panels.itertuples():
        if r.holes is None or isinstance(r.holes, float) or \
                not str(r.holes).strip():
            continue
        s = next(x for x in doc["slabs"] if x["panel_id"] == r.panel_id)
        src_rings = [x for x in str(r.holes).split("|")
                     if len(x.split(";")) >= 3]
        assert len(s["holes"]) == len(src_rings)


def test_losas_z_del_nivel(doc):
    z_by_level = {l["name"]: l["z"] for l in doc["levels"]}
    for s in doc["slabs"]:
        assert s["z"] == pytest.approx(z_by_level[s["level"]], abs=1e-6)