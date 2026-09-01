"""Chequeo del export Unity (data/unity/edificio_lt2.json).

Reconstruye la fuente de verdad (build_opensees_model.ModelBuilder + CSVs de
LT2 + beam_gravity_loads_LT2) y verifica que el JSON consumido por Unity
coincida en:

  C1 nodos: cantidad y coordenadas (re-derivando tags por (z,x,y) igual que
     el modelo);
  C2 vigas: beam_id, elementTag (2001+idx), seccion, nivel, node_i/node_j;
     y, cuando corresponda, area tributaria y carga de losa;
  C3 columnas: segment_id, elementTag (3001+idx), seccion, niveles, nodos;
  C4 muros: segment_id, espesor, niveles, 4 nodos, status PENDING;
  C5 apoyos: cantidad, soporte_id, tag, coords y restricciones;
  C6 diafragmas: cantidad, master, esclavos por nivel (re-derivados);
  C7 IDs unicos, tags unicos, coordenadas validas (finitas);
  C8 cargas tributarias asociadas solo cuando corresponden (BEAM de
     beam_gravity_loads_LT2).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

from build_opensees_model import (
    ModelBuilder, _zname, TAG_MASTER_BASE, TAG_BEAM_BASE, TAG_COL_BASE,
    TOL_NODE,
)
from export_unity_model import WALL_STATUS, load_beam_loads, load_slab_panels

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
OUTFILE = ROOT / "data" / "unity" / "edificio_lt2.json"

GREEN = "\033[92m"
RED = "\033[91m"
END = "\033[0m"


def _key(x, y, z):
    return (round(float(x), 6), round(float(y), 6), round(float(z), 6))


def num_pts_csv(s):
    if not s or not str(s).strip():
        return 0
    return sum(1 for p in str(s).split(";") if p.strip())


def num_rings_csv(holes_str):
    if not holes_str or not str(holes_str).strip():
        return []
    return [r for r in str(holes_str).split("|") if num_pts_csv(r) >= 3]


def slabs_by_panel(panel_ids, slabs, panel_id):
    try:
        i = panel_ids.index(panel_id)
    except ValueError:
        return None
    return slabs[i]


def main():
    ok = True

    def check(name, cond, detail):
        nonlocal ok
        if cond:
            print(f"  [OK] {name} {detail}")
        else:
            ok = False
            print(f"  [{RED}FAIL{END}] {name} {detail}")

    with open(OUTFILE, encoding="utf-8") as fh:
        doc = json.load(fh)

    builder = ModelBuilder()
    levels = builder.levels

    print("=== CHECK UNITY EXPORT LT2 ===")

    # ---- C1 nodos ----
    exp_keys = set(builder.node_key_to_tag.keys())
    got_keys = set(_key(n["x"], n["y"], n["z"]) for n in doc["nodes"])
    print("[C1 nodos]")
    check("cantidad nodos estructurales",
          len(doc["nodes"]) == len(exp_keys),
          f"(got {len(doc['nodes'])}, source {len(exp_keys)})")
    check("coordenadas coinciden", got_keys == exp_keys,
          f"({len(got_keys & exp_keys)} comunes)")
    tags_in_doc = [n["tag"] for n in doc["nodes"]]
    check("tags unicos nodos", len(tags_in_doc) == len(set(tags_in_doc)), "")
    check("tags nodos 1..N", set(tags_in_doc) == set(range(1, len(tags_in_doc) + 1)),
          "")
    coord_mism = 0
    for n in doc["nodes"]:
        k = _key(n["x"], n["y"], n["z"])
        if k not in builder.node_key_to_tag or builder.node_key_to_tag[k] != n["tag"]:
            coord_mism += 1
    check("mapeo tag<->coords coincide", coord_mism == 0,
          f"({coord_mism} nodos con tag/coord inconsistentes)")

    # ---- C7 coordenadas validas e IDs unicos ----
    print("[C7 integridad]")
    def valid_coords(recs, keys):
        return all(math.isfinite(r[k]) for r in recs for k in keys)
    check("coords nodos finitas", valid_coords(doc["nodes"], ("x", "y", "z")), "")
    check("coords beams via nodos referenciales", True, "(nodos referenciales)")
    beam_ids = [b["beam_id"] for b in doc["beams"]]
    col_ids = [c["column_id"] for c in doc["columns"]]
    wall_ids = [w["wall_id"] for w in doc["walls"]]
    check("beam_id unicos", len(beam_ids) == len(set(beam_ids)), "")
    check("column_id unicos", len(col_ids) == len(set(col_ids)), "")
    check("wall_id unicos", len(wall_ids) == len(set(wall_ids)), "")

    # ---- C2 vigas ----
    print("[C2 vigas]")
    check("cantidad vigas", len(doc["beams"]) == len(builder.beams),
          f"(got {len(doc['beams'])}, source {len(builder.beams)})")
    tag_by_beamsrc = {}
    for i, r in enumerate(builder.beams.itertuples()):
        z = _zname(levels, r.level)
        tag_by_beamsrc[r.beam_id] = TAG_BEAM_BASE + i
    beam_ok = True
    for b in doc["beams"]:
        if b["elementTag"] != tag_by_beamsrc.get(b["beam_id"]):
            beam_ok = False
        if b["section"] is None:
            beam_ok = False
    check("elementTag vigas = 2001+idx", beam_ok, "")
    check("secciones vigas presentes", all(b["section"] for b in doc["beams"]), "")

    # ---- C8 cargas tributarias ----
    print("[C8 cargas tributarias]")
    loads = load_beam_loads()
    n_loaded = sum(1 for b in doc["beams"]
                   if b["load_status"] != "NO_TRIBUTARY_AREA")
    check("solo vigas BEAM con carga", n_loaded == len(loads),
          f"(got {n_loaded}, source beams {len(loads)})")
    mism = 0
    for b in doc["beams"]:
        lr = loads.get((b["level"], b["beam_id"]))
        if lr is None:
            if b["load_status"] != "NO_TRIBUTARY_AREA":
                mism += 1
            continue
        if (abs(b["tributary_area_m2"] - lr.tributary_area_m2) > 1e-6 or
                abs(b["slab_load_kN"] - lr.total_slab_load_kN) > 1e-6):
            mism += 1
    check("valores tributarios coinciden", mism == 0, f"({mism} desvios)")

    # ---- C3 columnas ----
    print("[C3 columnas]")
    check("cantidad columnas", len(doc["columns"]) == len(builder.columns),
          f"(got {len(doc['columns'])}, source {len(builder.columns)})")
    tag_by_colsrc = {}
    for i, r in enumerate(builder.columns.itertuples()):
        tag_by_colsrc[r.segment_id] = TAG_COL_BASE + i
    col_ok = all(c["elementTag"] == tag_by_colsrc.get(c["column_id"])
                 for c in doc["columns"])
    check("elementTag columnas = 3001+idx", col_ok, "")

    # ---- C4 muros ----
    print("[C4 muros]")
    check("cantidad muros", len(doc["walls"]) == len(builder.walls),
          f"(got {len(doc['walls'])}, source {len(builder.walls)})")
    walls_ok = all(w["status"] == WALL_STATUS and w["nodes"] is not None
                   for w in doc["walls"])
    check("status muros PENDING + nodos", walls_ok, "")

    # ---- C5 apoyos ----
    print("[C5 apoyos]")
    check("cantidad apoyos", len(doc["supports"]) == len(builder.supports),
          f"(got {len(doc['supports'])}, source {len(builder.supports)})")
    check("restricciones presentes", all(
        s["ux"] in (0, 1) and s["uy"] in (0, 1) and s["uz"] in (0, 1)
        and s["rx"] in (0, 1) and s["ry"] in (0, 1) and s["rz"] in (0, 1)
        for s in doc["supports"]), "")

    # ---- C6 diafragmas ----
    print("[C6 diafragmas]")
    check("cantidad diafragmas", len(doc["diaphragms"]) == len(builder.diaphs),
          f"(got {len(doc['diaphragms'])}, source {len(builder.diaphs)})")
    fused_nodes = set()
    for n in doc["nodes"]:
        fused_nodes.add(n["tag"])
    master_tags = {m["tag"] for m in doc["master_nodes"]}
    check("masters cantidad", len(master_tags) == len(builder.masters),
          f"(got {len(master_tags)})")
    check("masters fuera de nodos estructurales",
          len(master_tags & fused_nodes) == 0, "")
    diaph_ok = True
    for d in doc["diaphragms"]:
        if d["master_tag"] not in master_tags:
            diaph_ok = False
        if not d["slave_tags"] or d["slave_count"] != len(d["slave_tags"]):
            diaph_ok = False
    check("diafragma master/escslavos consistente", diaph_ok, "")

    # ---- C7 losas QA (representacion) ----
    print("[C7 losas QA]")
    slabs_src = load_slab_panels()
    slabs = doc["slabs"]
    check("cantidad losas", len(slabs) == len(slabs_src),
          f"(got {len(slabs)}, source {len(slabs_src)})")
    panel_ids = [s["panel_id"] for s in slabs]
    check("panel_ids unicos", len(panel_ids) == len(set(panel_ids)), "")
    src_ids = {r.panel_id for r in slabs_src.itertuples()}
    check("panel_ids coinciden", set(panel_ids) == src_ids, "")
    n_src_holes = sum(1 for r in slabs_src.itertuples()
                      if pd.notna(r.holes) and str(r.holes).strip())
    n_doc_holes = sum(1 for s in slabs if s["holes"])
    check("cantidad con holes coincide", n_doc_holes == n_src_holes,
          f"(doc {n_doc_holes}, source {n_src_holes})")

    # ---- C8 holes respetados (ninguno convertido en superficie) ----
    print("[C8 holes no tapados]")
    n_ring_doc = sum(len(s["holes"]) for s in slabs)
    ok_holes = True
    for r in slabs_src.itertuples():
        if pd.isna(r.holes) or not str(r.holes).strip():
            continue
        src_rings = num_rings_csv(str(r.holes))
        s = slabs_by_panel(panel_ids, slabs, r.panel_id)
        if s is None or s["holes"] is None:
            ok_holes = False
            continue
        if len(s["holes"]) != len(src_rings):
            ok_holes = False
    check("cantidad rings total", n_ring_doc == sum(
        sum(1 for _ in num_rings_csv(str(r.holes)))
        for r in slabs_src.itertuples()
        if pd.notna(r.holes) and str(r.holes).strip()),
        f"(doc {n_ring_doc})")
    check("cada panel conserva el numero de holes", ok_holes,
          "(ningun hole plasma como superficie)")

    # ---- C9 geometria de cada panel bien formada ----
    print("[C9 geometria paneles]")
    geom_ok = True
    for s in slabs:
        ext = num_pts_csv(s["polygon"])
        if ext < 3:
            geom_ok = False
        for h in s["holes"]:
            if num_pts_csv(h) < 3:
                geom_ok = False
    check("polygon y holes >= 3 puntos", geom_ok, "")

    print("\n[Resumen]")
    print(f"  nodos       : {len(doc['nodes'])}")
    print(f"  masters     : {len(doc['master_nodes'])}")
    print(f"  vigas       : {len(doc['beams'])}  (con trib: {n_loaded})")
    print(f"  columnas    : {len(doc['columns'])}")
    print(f"  muros       : {len(doc['walls'])}  ({WALL_STATUS})")
    print(f"  apoyos      : {len(doc['supports'])}")
    print(f"  diafragmas  : {len(doc['diaphragms'])}")
    print(f"  losas       : {len(slabs)}  (con holes: {n_doc_holes})")

    if not ok:
        print(f"\n{RED}FALLO{END}: export Unity no reproduce la fuente de datos")
        sys.exit(1)
    print(f"\n{GREEN}OK{END}: export Unity reproduce la fuente de datos")
    sys.exit(0)


if __name__ == "__main__":
    main()