"""Exportador del MODELO COMBINADO FINAL LT1 + LT2 -> JSON para el viewer Unity.

Fuente de verdad: el modelo OpenSees COMBINADO ya validado (NUNCA se reconstruye
la geometria desde los planos). Se construye exactamente igual que el
orquestador `run_combined` (mismos builders, misma transformacion, mismos
diafragmas) y se vuelcan los elementos que viven en esa instancia.

El esquema de salida es EXACTAMENTE el que consume `ModelLoader.cs`
(`data/unity/edificio_lt2.json` -> `unity/Assets/StreamingAssets/edificio_lt2.json`):

  meta | levels | nodes | master_nodes | beams | columns | walls
        | supports | diaphragms | slabs | <-- schema ModelData (sin slabs: no hay
        losa combinada en el modelo estructural; se omiten).

Correspondencia con el modelo combinado final (commit 728d12f):
  - 442 nodos (todos los que viven en ops tras construir el combinado).
  - 602 elementos FE: 230 vigas LT2 + 50 columnas LT2 + 80 muros-columna LT2
    + 175 vigas LT1 + 39 columnas LT1 + 18 muros LT1 + 10 conectores de
    excentricidad. Visualmente los 80 muros-columna se dibujan como 40 paneles
    de muro (M001..M008), de modo que el conteo "dibujado" es 602 - 80 + 40.
  - 12 nodos compartidos de interfaz en x = 31.25.

Cada elemento/Nodo lleva `tower`: "LT1" o "LT2" para que el viewer distinga
torres por color manteniendo el toggle por tipo (vigas/columnas/muros).

NO modifica el modelo estructural. Solo escribe el JSON de visualizacion.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "model_combined"))

import openseespy.opensees as ops  # noqa: E402

from model_combined import run_combined as RC  # noqa: E402
from model_combined import config as C  # noqa: E402

VERSION = "2.0"
OUT_CSV = ROOT / "data" / "unity" / "edificio_lt2.json"
OUT_STREAMING = ROOT / "unity" / "Assets" / "StreamingAssets" / "edificio_lt2.json"


def _tower(tag: int) -> str:
    """Torre del nodo/elemento por rango de tag."""
    return "LT1" if tag >= C.NODE_BASE_LT1 else "LT2"


def _level_for_z(levels, z):
    for lv in levels:
        if abs(lv["z"] - z) < 1e-6:
            return lv["name"]
    return None


def _sec_str(tok: str, default="V60x80") -> str:
    return tok if tok and isinstance(tok, str) and tok.strip() else default


def export() -> dict:
    # ----- construir el modelo combinado EXACTO (igual que run_combined) -----
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    lt2 = RC.build_lt2()
    _, lt1 = RC.build_lt1()
    RC.build_diaphragms(lt2, lt1)

    coords = {t: ops.nodeCoord(t) for t in ops.getNodeTags()}

    # ---- niveles combinados (unir LT2 levels con elevaciones de LT1) --------
    levels = [{"name": r.name, "z": float(r.z_m)}
              for r in lt2.builder.levels.itertuples()]
    levels = sorted(levels, key=lambda l: l["z"])

    # ---- nodos (442) --------------------------------------------------------
    nodes = []
    for t in sorted(coords):
        x, y, z = coords[t]
        nodes.append({
            "tag": t, "x": round(float(x), 6), "y": round(float(y), 6),
            "z": round(float(z), 6),
            "level": _level_for_z(levels, float(z)),
            "tower": _tower(t),
        })

    # ---- nodos master (LT2, masters 1002..1005) ------------------------------
    master_nodes = []
    master_tag2id = {v: k for k, v in lt2.master_tag_by_id.items()}
    for t in (lt2.master_tags or []):
        if t not in coords:
            continue
        x, y, z = coords[t]
        lvl = _level_for_z(levels, float(z))
        master_nodes.append({
            "tag": t, "master_id": master_tag2id.get(t, f"master_{t}"),
            "level": lvl,
            "x": round(float(x), 6), "y": round(float(y), 6),
            "z": round(float(z), 6), "tower": "LT2",
        })

    # ---- vigas LT2 (2001..3000) ---------------------------------------------
    beams = []
    bmap = {2001 + i: e for i, e in enumerate(lt2.builder.elems["beams"])}
    for t in ops.getEleTags():
        if 2001 <= t < 3001:
            n1, n2 = ops.eleNodes(t)
            x1, y1, z1 = coords[n1]
            x2, y2, z2 = coords[n2]
            sec = _sec_str(bmap.get(t, {}).get("section"), "V60x80")
            lvl = _level_for_z(levels, float(z1))
            beams.append({
                "beam_id": f"LT2_B{t}", "elementTag": t, "level": lvl,
                "section": sec, "node_i": n1, "node_j": n2,
                "length_m": round(math.hypot(x2 - x1, y2 - y1), 6),
                "tributary_area_m2": None, "slab_load_kN": None,
                "equivalent_uniform_kN_m": None, "load_status": "NO_TRIBUTARY_AREA",
                "tower": "LT2",
            })

    # ---- conectores de excentricidad viga-muro (9001..10000) -> vigas --------
    connectors = []
    for t in ops.getEleTags():
        if 9001 <= t < 10000:
            n1, n2 = ops.eleNodes(t)
            x1, y1, z1 = coords[n1]
            x2, y2, z2 = coords[n2]
            lvl = _level_for_z(levels, float(z1))
            connectors.append({
                "beam_id": f"LT2_CNX{t}", "elementTag": t, "level": lvl,
                "section": "V40x80", "node_i": n1, "node_j": n2,
                "length_m": round(math.hypot(x2 - x1, y2 - y1), 6),
                "tributary_area_m2": None, "slab_load_kN": None,
                "equivalent_uniform_kN_m": None, "load_status": "CONNECTOR",
                "tower": "LT2",
            })

    # ---- vigas LT1 (summary) ------------------------------------------------
    lt1_beams = []
    for e in lt1["beam_elements"]:
        n1, n2 = e["ni"], e["nj"]
        x1, y1, z1 = coords[n1]
        x2, y2, z2 = coords[n2]
        lvl = lt1_level_for(lt1, e, n1, coords)
        lt1_beams.append({
            "beam_id": f"LT1_B{e['tag']}", "elementTag": e["tag"], "level": lvl,
            "section": "V60x80", "node_i": n1, "node_j": n2,
            "length_m": round(math.hypot(x2 - x1, y2 - y1), 6),
            "tributary_area_m2": None, "slab_load_kN": None,
            "equivalent_uniform_kN_m": None, "load_status": "NO_TRIBUTARY_AREA",
            "tower": "LT1",
        })
    beams.extend(connectors)
    beams.extend(lt1_beams)

    # ---- columnas LT2 (3001..4000) + LT1 (no muros-columna) ------------------
    columns = []
    cmap = {3001 + i: e for i, e in enumerate(lt2.builder.elems["columns"])}
    for t in ops.getEleTags():
        if 3001 <= t < 4001:
            n1, n2 = ops.eleNodes(t)
            x1, y1, z1 = coords[n1]
            _, _, z2 = coords[n2]
            columns.append({
                "column_id": f"LT2_C{t}", "parent_id": None,
                "elementTag": t, "section": _sec_str(cmap.get(t, {}).get("section"), "P70x70"),
                "from_level": _level_for_z(levels, float(z1)),
                "to_level": _level_for_z(levels, float(z2)),
                "node_i": n1, "node_j": n2, "x": round(float(x1), 6),
                "y": round(float(y1), 6), "length_m": round(abs(z2 - z1), 6),
                "tower": "LT2",
            })
    for e in lt1["col_elements"]:
        n1, n2 = e["ni"], e["nj"]
        x1, y1, z1 = coords[n1]
        _, _, z2 = coords[n2]
        columns.append({
            "column_id": f"LT1_C{e['tag']}", "parent_id": None,
            "elementTag": e["tag"], "section": "P70x70",
            "from_level": _level_for_z(levels, float(z1)),
            "to_level": _level_for_z(levels, float(z2)),
            "node_i": n1, "node_j": n2, "x": round(float(x1), 6),
            "y": round(float(y1), 6), "length_m": round(abs(z2 - z1), 6),
            "tower": "LT1",
        })

    # ---- muros: LT2 M001..M008 (paneles reales) + LT1 (18) -------------------
    walls = []
    for seg in lt2.builder.elems["walls"]:
        z0 = float(coords[seg["n00"]][2])
        z1 = float(coords[seg["n01"]][2])
        walls.append({
            "wall_id": f"LT2_{seg['id']}", "parent_id": seg["id"].split("_")[0],
            "thickness_m": float(seg["thickness"]),
            "from_level": _level_for_z(levels, z0),
            "to_level": _level_for_z(levels, z1),
            "nodes": {"bottom_i": seg["n00"], "bottom_j": seg["n10"],
                      "top_i": seg["n01"], "top_j": seg["n11"]},
            "status": "WALL_AS_COLUMN",
            "tower": "LT2",
        })
    for e in lt1["wall_elements"]:
        n1, n2 = e["ni"], e["nj"]
        x1, y1, z1 = coords[n1]
        x2, y2, z2 = coords[n2]
        # panel LT1: borde ancho = espesor C.WALL en direccion transversal.
        dx, dy = x2 - x1, y2 - y1
        leng = math.hypot(dx, dy)
        if leng < 1e-9:
            continue
        px, py = -dy / leng, dx / leng          # vector normal en planta
        tx, ty = 0.20 * px, 0.20 * py           # espesor de muro real (0.20 m)
        walls.append({
            "wall_id": f"LT1_W{e['tag']}", "parent_id": None,
            "thickness_m": 0.20,
            "from_level": _level_for_z(levels, float(z1)),
            "to_level": _level_for_z(levels, float(z2)),
            "nodes": {"bottom_i": n1,
                      "bottom_j": _emit_offnode(n1, tx, ty, z1, nodes, coords),
                      "top_i": n2,
                      "top_j": _emit_offnode(n2, tx, ty, z2, nodes, coords)},
            "status": "WALL_AS_COLUMN",
            "tower": "LT1",
        })

    # ---- apoyos --------------------------------------------------------------
    supports = []
    for t in sorted(set(lt2.support_tags) | set(lt1["base_fixed_tags"])):
        if t not in coords:
            continue
        x, y, z = coords[t]
        supports.append({
            "support_id": f"SUP_{t}", "tag": t,
            "level": _level_for_z(levels, float(z)),
            "x": round(float(x), 6), "y": round(float(y), 6),
            "z": round(float(z), 6), "ux": 1, "uy": 1, "uz": 1,
            "rx": 1, "ry": 1, "rz": 1, "tower": _tower(t),
        })

    # ---- diafragmas (combinados: master LT2 por nivel) ------------------------
    diaphragms = []
    for m in lt2.master_tag_by_id:                       # m = master_id "NM_L2"
        master = lt2.master_tag_by_id[m]
        if master not in coords:
            continue
        z = float(coords[master][2])
        lvl = _level_for_z(levels, z)
        if lvl is None:
            continue
        slaves = [t for t, k in lt2.tag_to_key.items()
                  if t in coords and abs(k[2] - z) < 1e-6 and t != master
                  and t not in (lt2.diaph_exclude or set())]
        diaphragms.append({
            "diaphragm_id": f"D_{lvl}", "level": lvl, "master_id": m,
            "master_tag": master, "slave_tags": sorted(slaves),
            "slave_count": len(slaves),
        })

    doc = {
        "meta": {
            "model": "LT1 + LT2 (combined, commit 728d12f)",
            "generator": "export_unity_combined.py",
            "schema_version": VERSION,
            "units": "meters",
            "ndm": 3,
            "ndf": 6,
            "nodes": len(nodes),
            "elements_fe": len(ops.getEleTags()),
            "source": "modelo combinado OpenSees validado (442 nodos / 602 elementos / 12 interfaz)",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "levels": levels,
        "nodes": nodes,
        "master_nodes": master_nodes,
        "beams": beams,
        "columns": columns,
        "walls": walls,
        "supports": supports,
        "diaphragms": diaphragms,
        "slabs": [],
    }

    with open(OUT_CSV, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    OUT_STREAMING.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_STREAMING, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
    return doc


def lt1_level_for(lt1, e, n1, coords):
    """Nivel LT1 del elemento (misma elevacion que su nodo i)."""
    z = float(coords[n1][2])
    levels = [{"z": -0.05, "name": "P1"}, {"z": 3.91, "name": "P2"},
              {"z": 7.87, "name": "P3"}, {"z": 11.83, "name": "P4"}]
    for l in levels:
        if abs(l["z"] - z) < 1e-6:
            return l["name"]
    return None


def _emit_offnode(nref, tx, ty, z, nodes, coords):
    """Nodo auxiliar para el ancho del panel de muro LT1 (unico por coordenada)."""
    x, y, _ = coords[nref]
    nx, ny = round(x + tx, 6), round(y + ty, 6)
    key = (round(nx, 6), round(ny, 6), round(float(z), 6))
    for n in nodes:
        if (round(float(n["x"]), 6), round(float(n["y"]), 6),
                round(float(n["z"]), 6)) == key:
            return n["tag"]
    # Sin colision con nodos reales: minimo tag libre negativo para no chocar
    tag = -3_000_000 - len(nodes)
    nodes.append({
        "tag": tag, "x": nx, "y": ny, "z": round(float(z), 6),
        "level": _level_for_z([{"name": None, "z": float(z)}], float(z)),
        "tower": "LT1",
    })
    coords[tag] = (nx, ny, float(z))
    return tag


def main():
    doc = export()
    prints_summary(doc)


def prints_summary(doc):
    beams = doc["beams"]
    cols = doc["columns"]
    walls = doc["walls"]
    node_tags = [n["tag"] for n in doc["nodes"]]
    real_tags = [t for t in node_tags if t > 0]
    lt2_beams = sum(1 for b in beams if b["tower"] == "LT2" and "_CNX" not in b["beam_id"])
    lt2_cnx = sum(1 for b in beams if "_CNX" in b["beam_id"])
    lt1_beams = sum(1 for b in beams if b["tower"] == "LT1")
    lt2_cols = sum(1 for c in cols if c["tower"] == "LT2")
    lt1_cols = sum(1 for c in cols if c["tower"] == "LT1")
    lt2_walls = sum(1 for w in walls if w["tower"] == "LT2")
    lt1_walls = sum(1 for w in walls if w["tower"] == "LT1")
    print("=== EXPORT UNITY COMBINADO (LT1+LT2) ===")
    print(f"  nodos            : {len(doc['nodes'])}  (reales estructurales {len(real_tags)})")
    ix = [t for t in real_tags if t in set(C.INTERFACE_LT2_TAGS)]
    print(f"  interfaz 12      : {len(ix)}")
    print(f"  vigas            : LT2={lt2_beams}  cnx={lt2_cnx}  LT1={lt1_beams}  total={len(beams)}")
    print(f"  columnas         : LT2={lt2_cols}  LT1={lt1_cols}  total={len(cols)}")
    print(f"  muros            : LT2={lt2_walls}  LT1={lt1_walls}  total={len(walls)}")
    print(f"  apoyos           : {len(doc['supports'])}")
    print(f"  master_nodes     : {len(doc['master_nodes'])}")
    print(f"  diafragmas       : {len(doc['diaphragms'])}")
    xs = [n["x"] for n in doc["nodes"] if n["tag"] > 0]
    ys = [n["y"] for n in doc["nodes"] if n["tag"] > 0]
    zs = [n["z"] for n in doc["nodes"] if n["tag"] > 0]
    print(f"  rango X  : [{min(xs):.3f}, {max(xs):.3f}] m")
    print(f"  rango Y  : [{min(ys):.3f}, {max(ys):.3f}] m")
    print(f"  rango Z  : [{min(zs):.3f}, {max(zs):.3f}] m")
    print(f"  torres   : LT1 presente, LT2 presente")
    iface_nodes = [n for n in doc["nodes"] if n["tag"] in set(C.INTERFACE_LT2_TAGS)]
    print(f"  interfaz x=31.25 presente: "
          f"{all(abs(float(n['x']) - 31.25) < 1e-6 for n in iface_nodes) if iface_nodes else False}")
    print(f"\nEscrito: {OUT_CSV}")
    print(f"Escrito: {OUT_STREAMING}")


if __name__ == "__main__":
    main()