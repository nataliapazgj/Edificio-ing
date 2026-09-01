"""Exportador Python -> data/unity/edificio_lt2.json para el viewer Unity.

Fuente de verdad: Python/OpenSees (ModelBuilder en build_opensees_model.py).
Unity NO reconstruye ni reinterpreta la geometria: consume este JSON.

El exportador vuelve a derivar tags/nodos exactamente igual que
build_opensees_model.ModelBuilder (mismo algoritmo de recoleccion y orden de
nodos/elementos) para garantizar que los IDs exportados coincidan con el
modelo OpenSees (ids reproducibles).

Exporta:
  - niveles (coordenadas z);
  - nodos estructurales (tag, x, y, z, nivel);
  - nodos master de diafragma (tag, master_id, nivel, coords);
  - vigas (beam_id, elementTag=2001+idx, nivel, seccion, node_i, node_j, length,
    y, cuando existe en beam_gravity_loads_LT2, su area tributaria y carga de
    losa -> estara disponible para el Bloque 4B sin cambiar la arquitectura);
  - columnas (segment_id, parent_id, elementTag=3001+idx, seccion,
    from_level, to_level, node_i, node_j, length);
  - muros (segment_id, parent_id, espesor, from_level, to_level, 4 nodos,
    estado PENDING_WALL_CONVENTION porque aun no estan materializados en
    OpenSees, pero se visualizan);
  - apoyos (support_id, tag, nivel, coords, restricciones);
  - diafragmas (diaphragm_id, nivel, master, esclavos por tag, slave_count).

La unidad es el metro (coincide con el modelo). Los muros se marcan como
pendientes de materializar (OpenSees status = PENDING_WALL_CONVENTION).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from build_opensees_model import (
    ModelBuilder,
    _zname,
    TAG_MASTER_BASE,
    TAG_BEAM_BASE,
    TAG_COL_BASE,
)

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"
LOADS = ROOT / "data" / "loads"
OUT = ROOT / "data" / "unity"
OUTFILE = OUT / "edificio_lt2.json"

WALL_STATUS = "PENDING_WALL_CONVENTION"
VERSION = "0.1"


def load_masters():
    return pd.read_csv(GEOM / "master_nodes_LT2.csv")


def load_diaphragms():
    return pd.read_csv(GEOM / "diaphragms_LT2.csv")


def load_beam_loads():
    """Carga beam_gravity_loads_LT2.csv indexado por (level, beam_id).

    Solo interesan las filas receiver_type=BEAM (vigas con area tributaria).
    """
    df = pd.read_csv(LOADS / "beam_gravity_loads_LT2.csv")
    beam = df[df["receiver_type"] == "BEAM"].copy()
    beam["beam_id"] = beam["beam_id"].astype(str)
    beam["element_tag"] = beam["element_tag"].astype(int)
    beam["level"] = beam["level"].astype(str)
    # Indice multi nivel -> diccionario clave (level, beam_id) -> fila.
    # Se usa dict explicito (no DataFrame.get de MultiIndex) para que la
    # busqueda por tupla sea robusta.
    return {
        (row.level, row.beam_id): row
        for row in beam.itertuples()
    }


def _parse_ring(s):
    """Convierte 'x,y;x,y;...' (cadena) en una lista de pares (x, y) float."""
    out = []
    for token in str(s).split(";"):
        token = token.strip()
        if not token:
            continue
        x, y = token.split(",")
        out.append((float(x), float(y)))
    return out


def _serialize_ring(ring):
    """Convierte lista de pares (x, y) en 'x,y;x,y;...'."""
    return ";".join(f"{x:.6f},{y:.6f}" for x, y in ring)


def load_slab_panels():
    """Carga slab_panels_LT2.csv (losas QA por nivel).

    Devuelve el DataFrame crudo; la construccion de rings se hace en export().
    """
    return pd.read_csv(LOADS / "slab_panels_LT2.csv")


def export(out_path: Path = OUTFILE) -> Path:
    builder = ModelBuilder()
    levels_df = builder.levels
    masters_df = load_masters()
    diaphs_df = load_diaphragms()
    beam_loads = load_beam_loads()
    slabs_df = load_slab_panels()

    # ---- nodos estructurales ----
    nodes = []
    by_tag = {}
    for tag, (x, y, z) in builder.tag_to_key.items():
        level = _level_for_z(levels_df, z)
        node = {
            "tag": tag,
            "x": x,
            "y": y,
            "z": z,
            "level": level,
        }
        nodes.append(node)
        by_tag[tag] = node
    nodes.sort(key=lambda n: (n["z"], n["x"], n["y"]))

    # ---- nodos master ----
    master_nodes = []
    for i, r in enumerate(masters_df.itertuples()):
        tag = TAG_MASTER_BASE + i
        master_nodes.append({
            "tag": tag,
            "master_id": r.master_id,
            "level": r.level,
            "x": r.x_m,
            "y": r.y_m,
            "z": r.z_m,
        })

    # ---- vigas ----
    beams = []
    for i, r in enumerate(builder.beams.itertuples()):
        z = _zname(levels_df, r.level)
        n1 = builder.node_key_to_tag[_key(r.x1_m, r.y1_m, z)]
        n2 = builder.node_key_to_tag[_key(r.x2_m, r.y2_m, z)]
        beam_entry = {
            "beam_id": r.beam_id,
            "elementTag": TAG_BEAM_BASE + i,
            "level": r.level,
            "section": r.section,
            "node_i": n1,
            "node_j": n2,
            "length_m": float((r.x2_m - r.x1_m) ** 2
                              + (r.y2_m - r.y1_m) ** 2) ** 0.5,
        }
        load_row = beam_loads.get((r.level, r.beam_id))
        if load_row is not None:
            beam_entry["tributary_area_m2"] = float(
                load_row.tributary_area_m2)
            beam_entry["slab_load_kN"] = float(load_row.total_slab_load_kN)
            beam_entry["equivalent_uniform_kN_m"] = float(
                load_row.equivalent_uniform_load_kN_m)
            beam_entry["load_status"] = str(load_row.status)
        else:
            beam_entry["tributary_area_m2"] = None
            beam_entry["slab_load_kN"] = None
            beam_entry["load_status"] = "NO_TRIBUTARY_AREA"
        beams.append(beam_entry)

    # ---- columnas ----
    columns = []
    for i, r in enumerate(builder.columns.itertuples()):
        z0 = _zname(levels_df, r.from_level)
        z1 = _zname(levels_df, r.to_level)
        n1 = builder.node_key_to_tag[_key(r.x_m, r.y_m, z0)]
        n2 = builder.node_key_to_tag[_key(r.x_m, r.y_m, z1)]
        columns.append({
            "column_id": r.segment_id,
            "parent_id": r.parent_id,
            "elementTag": TAG_COL_BASE + i,
            "section": r.section,
            "from_level": r.from_level,
            "to_level": r.to_level,
            "node_i": n1,
            "node_j": n2,
            "x": r.x_m,
            "y": r.y_m,
            "length_m": float(abs(z1 - z0)),
        })

    # ---- muros (visualizables, pendientes en OpenSees) ----
    walls = []
    for r in builder.walls.itertuples():
        z0 = _zname(levels_df, r.from_level)
        z1 = _zname(levels_df, r.to_level)
        n00 = builder.node_key_to_tag[_key(r.x1_m, r.y1_m, z0)]
        n10 = builder.node_key_to_tag[_key(r.x2_m, r.y2_m, z0)]
        n01 = builder.node_key_to_tag[_key(r.x1_m, r.y1_m, z1)]
        n11 = builder.node_key_to_tag[_key(r.x2_m, r.y2_m, z1)]
        walls.append({
            "wall_id": r.segment_id,
            "parent_id": r.parent_id,
            "thickness_m": r.thickness_m,
            "from_level": r.from_level,
            "to_level": r.to_level,
            "nodes": {"bottom_i": n00, "bottom_j": n10,
                      "top_i": n01, "top_j": n11},
            "status": WALL_STATUS,
        })

    # ---- apoyos ----
    supports = []
    z_b1 = _zname(levels_df, "B1")
    for r in builder.supports.itertuples():
        tag = builder.node_key_to_tag[_key(r.x_m, r.y_m, z_b1)]
        supports.append({
            "support_id": r.support_id,
            "tag": tag,
            "level": "B1",
            "x": r.x_m,
            "y": r.y_m,
            "z": z_b1,
            "ux": int(r.ux), "uy": int(r.uy), "uz": int(r.uz),
            "rx": int(r.rx), "ry": int(r.ry), "rz": int(r.rz),
        })

    # ---- diafragmas (masters + esclavos) ----
    master_tag_by_id = dict(
        zip((r.master_id for r in masters_df.itertuples()),
            (TAG_MASTER_BASE + i for i in range(len(masters_df)))))
    diaphragms = []
    for r in diaphs_df.itertuples():
        master_tag = master_tag_by_id[r.master_id]
        slave_tags = [t for t in builder.level_tags[r.level]
                      if t != master_tag]
        diaphragms.append({
            "diaphragm_id": r.diaphragm_id,
            "level": r.level,
            "master_id": r.master_id,
            "master_tag": master_tag,
            "slave_tags": slave_tags,
            "slave_count": len(slave_tags),
        })

    # ---- losas QA (representacion, NO elementos estructurales) ----
    slabs = []
    z_by_level = {row.name: float(row.z_m) for row in levels_df.itertuples()}
    for r in slabs_df.itertuples():
        exterior = _parse_ring(r.polygon)
        holes = []
        if pd.notna(r.holes) and str(r.holes).strip():
            for ring_str in str(r.holes).split("|"):
                ring = _parse_ring(ring_str)
                if ring:
                    holes.append(ring)
        thickness = None if pd.isna(r.thickness_m) else float(r.thickness_m)
        qg = None if pd.isna(r.qG_kN_m2) else float(r.qG_kN_m2)
        slabs.append({
            "panel_id": r.panel_id,
            "level": r.level,
            "z": z_by_level.get(r.level, 0.0),
            "polygon": _serialize_ring(exterior),
            "holes": [_serialize_ring(h) for h in holes],
            "area_m2": float(r.area_m2),
            "thickness_m": thickness,
            "qG_kN_m2": qg,
            "status": str(r.status),
            "hole_status": None if pd.isna(r.hole_status)
                           else str(r.hole_status),
        })

    doc = {
        "meta": {
            "model": "LT2",
            "generator": "export_unity_model.py",
            "schema_version": VERSION,
            "units": "meters",
            "ndm": 3,
            "ndf": 6,
            "source": "data/geometry/*_LT2.csv + data/loads/beam_gravity_loads_LT2.csv",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "levels": [
            {"name": row.name, "z": float(row.z_m)}
            for row in levels_df.itertuples()
        ],
        "nodes": nodes,
        "master_nodes": master_nodes,
        "beams": beams,
        "columns": columns,
        "walls": walls,
        "supports": supports,
        "diaphragms": diaphragms,
        "slabs": slabs,
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return out_path


def _level_for_z(levels_df, z):
    z = round(float(z), 6)
    for r in levels_df.itertuples():
        if abs(round(float(r.z_m), 6) - z) < 1e-6:
            return r.name
    return None


def _key(x, y, z):
    return (round(float(x), 6), round(float(y), 6), round(float(z), 6))


def main():
    path = export()
    doc = _load(path)
    summary(doc)
    print(f"\nExportado: {path}")


def _load(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def summary(doc):
    beams = doc["beams"]
    cols = doc["columns"]
    walls = doc["walls"]
    slabs = doc["slabs"]
    n_holes = sum(1 for s in slabs if s["holes"])
    n_hole_rings = sum(len(s["holes"]) for s in slabs)
    print("=== EXPORT UNITY LT2 ===")
    print(f"  niveles              : {len(doc['levels'])}")
    print(f"  nodos estructurales  : {len(doc['nodes'])}")
    print(f"  nodos master         : {len(doc['master_nodes'])}")
    print(f"  vigas                : {len(beams)}")
    print(f"  columnas             : {len(cols)}")
    print(f"  muros                : {len(walls)}")
    print(f"  apoyos               : {len(doc['supports'])}")
    print(f"  diafragmas           : {len(doc['diaphragms'])}")
    print(f"  losas (slabs)        : {len(slabs)}")
    print(f"  panos con holes      : {n_holes}  (rings: {n_hole_rings})")
    n_load = sum(1 for b in beams if b["tributary_area_m2"] is not None)
    print(f"  vigas con area trib. : {n_load}")


if __name__ == "__main__":
    main()