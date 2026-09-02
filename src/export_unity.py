"""
Exportacion Unity: data/processed/unity_model.json + results/unity_export_check.txt.

SOLO LEE los datos aceptados (Semana 2) y los vuelca al esquema del viewer.
NO recalcula estructura, NO modifica ningun archivo OpenSees.
Construye el modelo en memoria (build_ops_model) para obtener los
elementTag/nodeTag EXACTOS del FE; despues lo descarta.

Salidas:
  data/processed/unity_model.json   (modelo para el viewer)
  results/unity_export_check.txt    (QA PASS/WARNING/FAIL)
  unity/StructuralViewer/Data/unity_model.json  (copia local del proyecto)
"""

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops
from ops_model import load_aligned, build_ops_model

FE_COL_SECTION = "P.70x70"
FE_BEAM_SECTION = "V.60/80"
FE_WALL_SECTION = "M.H.A. e=0.20 h=3.00"
MATERIAL = "HORMIGON G35_10 (fc'=35MPa)"

LEVEL_Z = {}
HEIGHT = {}


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    l = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / l for c in v)


def local_axes(x1, y1, z1, x2, y2, z2):
    """Ejes locales de visualizacion a partir de los extremos."""
    ax = _norm((x2 - x1, y2 - y1, z2 - z1))
    ref = (0.0, 0.0, 1.0) if abs(ax[2]) < 0.999 else (1.0, 0.0, 0.0)
    ay = _norm(_cross(ref, ax))
    az = _cross(ax, ay)
    return [list(ax), list(ay), list(az)]


def node_level(z, levels):
    best, bd = None, 1e30
    for lvl in levels:
        d = abs(z - LEVEL_Z[lvl])
        if d < bd:
            bd, best = d, lvl
    return best


def poly_to_xy(poly):
    return [{"x": float(p[0]), "y": float(p[1])} for p in poly]


def main():
    # ── Firmas de los datos aceptados (QA: no modificados por la exportacion)
    signed = {}
    for rel in ("data/processed/structure_results.json",
                "data/processed/slabs.json",
                "data/processed/tributary_areas.json",
                "data/processed/building_3d_aligned.json"):
        p = ROOT / rel
        signed[rel] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

    data = load_aligned()
    for lv in data["levels"]:
        if lv.get("elevation") is not None:
            LEVEL_Z[lv["id"]] = lv["elevation"]
    levels = sorted(LEVEL_Z, key=LEVEL_Z.get)

    summary = build_ops_model(data)

    # ── NODES ────────────────────────────────────────────────────────────
    nodes = []
    for t in sorted(ops.getNodeTags()):
        x, y, z = ops.nodeCoord(t)
        nodes.append({
            "nodeTag": t, "x": x, "y": y, "z": z,
            "level": node_level(z, levels),
        })
    node_tags = {n["nodeTag"] for n in nodes}
    coord = {n["nodeTag"]: (n["x"], n["y"], n["z"]) for n in nodes}

    # ── ELEMENTS (FE) ────────────────────────────────────────────────────
    elements = []
    for c in summary["col_elements"]:
        (x1, y1, z1), (x2, y2, z2) = coord[c["ni"]], coord[c["nj"]]
        axes = local_axes(x1, y1, z1, x2, y2, z2)
        elements.append({
            "elementTag": c["tag"], "physical_id": -1, "type": "column",
            "node_i": c["ni"], "node_j": c["nj"],
            "coordinates": {"i": [x1, y1, z1], "j": [x2, y2, z2]},
            "level": c["level_i"], "section": FE_COL_SECTION, "material": MATERIAL,
            "local_axis_x": axes[0], "local_axis_y": axes[1], "local_axis_z": axes[2],
            "source_dxf": None, "source_id": None, "analysis_status": "FE",
        })
    for e in summary["beam_elements"] + summary["wall_elements"]:
        (x1, y1, z1), (x2, y2, z2) = coord[e["ni"]], coord[e["nj"]]
        axes = local_axes(x1, y1, z1, x2, y2, z2)
        kind = "beam" if e["kind"] == "beam" else "wall"
        section = FE_BEAM_SECTION if kind == "beam" else FE_WALL_SECTION
        physical = e.get("orig", -1)
        src = data["beams"] if kind == "beam" else data["walls"]
        src_meta = None
        for m in src:
            if m.get("level") == e["level"] and m.get("idx") == physical:
                src_meta = m
                break
        elements.append({
            "elementTag": e["tag"], "physical_id": physical, "type": kind,
            "node_i": e["ni"], "node_j": e["nj"],
            "coordinates": {"i": [x1, y1, z1], "j": [x2, y2, z2]},
            "level": e["level"], "section": section, "material": MATERIAL,
            "local_axis_x": axes[0], "local_axis_y": axes[1], "local_axis_z": axes[2],
            "source_dxf": (src_meta.get("source_layer") if src_meta else None),
            "source_id": (src_meta.get("dxf") if src_meta is not None else None),
            "analysis_status": "FE",
        })

    # ── LOAD_ONLY members (visualizacion/trazabilidad) ───────────────────
    lo_count = 0
    for k, m in sorted(summary.get("load_only_members", {}).items()):
        lo_count += 1
        kind = m["kind"]
        x1, y1 = m["x1"], m["y1"]
        x2, y2 = m["x2"], m["y2"]
        z = LEVEL_Z.get(m["level"], 0.0)
        axes = local_axes(x1, y1, z, x2, y2, z)
        section = FE_BEAM_SECTION if kind == "beam" else FE_WALL_SECTION
        src = data["beams"] if kind == "beam" else data["walls"]
        src_meta = None
        for mm in src:
            if mm.get("level") == m["level"] and (
                    (mm["x1"] == x1 and mm["y1"] == y1 and mm["x2"] == x2 and mm["y2"] == y2)
                    or (mm["x2"] == x1 and mm["y2"] == y1 and mm["x1"] == x2 and mm["y1"] == y2)):
                src_meta = mm
                break
        elements.append({
            "elementTag": -1, "physical_id": k[1], "type": kind,
            "node_i": -1, "node_j": -1,
            "coordinates": {"i": [x1, y1, z], "j": [x2, y2, z]},
            "level": m["level"], "section": section, "material": MATERIAL,
            "local_axis_x": axes[0], "local_axis_y": axes[1], "local_axis_z": axes[2],
            "source_dxf": (src_meta.get("source_layer") if src_meta else None),
            "source_id": (src_meta.get("dxf") if src_meta is not None else None),
            "analysis_status": "LOAD_ONLY",
        })

    # ── SUPPORTS ─────────────────────────────────────────────────────────
    supports = [{"nodeTag": t, "restrained_DOFs": [1, 2, 3, 4, 5, 6]}
                for t in sorted(summary["base_fixed_tags"])]

    # ── SLABS / DIAPHRAGMS ───────────────────────────────────────────────
    slabs_in = json.loads((ROOT / "data/processed/slabs.json").read_text(encoding="utf-8"))
    slabs = []
    slab_by_level = {}
    for s in slabs_in:
        slabs.append({
            "slab_id": s["slab_id"], "level": s["level"],
            "polygon": poly_to_xy(s["polygon"]),
            "area_m2": s["area_m2"], "q_G_kN_m2": s["q_G_kN_m2"],
            "status": s["status"],
        })
        slab_by_level[s["level"]] = s

    diaphragms = []
    for lvl, cfg in sorted(summary["diaphragms"].items()):
        poly = slab_by_level.get(lvl, {}).get("polygon", [])
        diaphragms.append({
            "level": lvl, "master_node": cfg["master"],
            "slave_nodes": sorted(cfg["slaves"]),
            "polygon": poly_to_xy(poly),
        })

    # ── TRIBUTARY AREAS ──────────────────────────────────────────────────
    trib_in = json.loads((ROOT / "data/processed/tributary_areas.json").read_text(encoding="utf-8"))
    tributary_areas = []
    tid = 1
    tag2level = {}
    sanitized_degenerate = 0
    for e in summary["beam_elements"]:
        tag2level[e["tag"]] = e["level"]
    for tag_str, det in sorted(trib_in["per_beam_elementTag"].items(),
                               key=lambda kv: int(kv[0])):
        tag = int(tag_str)
        lvl = tag2level.get(tag) or det.get("level")
        slab_id = next((s["slab_id"] for s in slabs_in if s["level"] == lvl), None)
        q = next((s["q_G_kN_m2"] for s in slabs_in if s["level"] == lvl), 0.0)
        poly = det.get("polygon") or []
        if poly and len(poly) < 3:
            # Poligono degenerado (<3 puntos) heredado de la fuente aceptada
            # (region tributaria de una sola fila de celdas). Se expone vacio
            # al viewer (=> "Sin area tributaria asignada") sin alterar la
            # fuente; el area/load aceptados quedan intactos en el export.
            sanitized_degenerate += 1
            poly = []
        tributary_areas.append({
            "tributary_id": tid,
            "slab_id": slab_id,
            "beam_elementTag": tag,
            "polygon": poly_to_xy(poly),
            "area_m2": det.get("tributary_area_m2", 0.0),
            "q_G_kN_m2": q,
            "load_kN": det.get("slab_load_kN", 0.0),
            "equivalent_line_load_kN_m": det.get("equivalent_line_load_kN_m", 0.0),
        })
        tid += 1

    model = {
        "nodes": nodes,
        "elements": elements,
        "supports": supports,
        "diaphragms": diaphragms,
        "slabs": slabs,
        "tributary_areas": tributary_areas,
    }
    out = ROOT / "data/processed/unity_model.json"
    out.write_text(json.dumps(model, indent=1), encoding="utf-8")

    # Copia local para apertura rapida del proyecto Unity
    local = ROOT / "unity" / "StructuralViewer" / "Data" / "unity_model.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(model, indent=1), encoding="utf-8")

    # ── QA ───────────────────────────────────────────────────────────────
    issues = []
    warnings = []

    elem_tags = [e["elementTag"] for e in elements if e["analysis_status"] == "FE"]
    dup = len(elem_tags) - len(set(elem_tags))
    issues.append(("FAIL" if dup else "PASS",
                   f"elementTag unicos: {dup} duplicados" if dup else
                   f"elementTag unicos: {len(elem_tags)} FE"))

    missing_nodes = [e for e in elements
                     if e["analysis_status"] == "FE" and
                     (e["node_i"] not in node_tags or e["node_j"] not in node_tags)]
    issues.append(("FAIL" if missing_nodes else "PASS",
                   f"nodos referenciados por elementos: "
                   f"{len(missing_nodes)} invalidos"))

    bad_supports = [s for s in supports if s["nodeTag"] not in node_tags]
    issues.append(("FAIL" if bad_supports else "PASS",
                   f"apoyos -> nodos existentes: {len(bad_supports)} invalidos"))

    issues.append(("PASS" if len(diaphragms) == 4 else "FAIL",
                   f"diafragmas exportados: {len(diaphragms)}/4 (P1/P2/P3/P4)"))

    bad_diaph = []
    for d in diaphragms:
        if d["master_node"] not in node_tags:
            bad_diaph.append(d["level"])
        for s in d["slave_nodes"]:
            if s not in node_tags:
                bad_diaph.append(d["level"])
    issues.append(("FAIL" if bad_diaph else "PASS",
                   f"diafragmas master/slaves validos: {bad_diaph or 'ok'}"))

    fe_tags = {e["elementTag"] for e in elements if e["analysis_status"] == "FE"}
    bad_trib = [t["beam_elementTag"] for t in tributary_areas
                if t["beam_elementTag"] not in fe_tags]
    issues.append(("FAIL" if bad_trib else "PASS",
                   f"tributary beam_elementTag existe: {bad_trib or 'ok'}"))

    def poly_ok(t):
        p = t["polygon"]
        return 3 <= len(p) <= 1000
    bad_poly_t = [t["tributary_id"] for t in tributary_areas
                  if t["polygon"] and not poly_ok(t)]
    n_poly = sum(1 for t in tributary_areas if t["polygon"])
    issues.append(("FAIL" if bad_poly_t else "PASS",
                   f"polygons tributarios validos: {n_poly}/{len(tributary_areas)} "
                   f"con polygon (invalido: {bad_poly_t or 'ninguno'})"
                   + (f"; {sanitized_degenerate} degenerado(s) heredado(s) "
                      f"expuesto(s) como vacio, area intacta" if sanitized_degenerate else "")))

    bad_slab = [s["slab_id"] for s in slabs if len(s["polygon"]) < 4]
    issues.append(("FAIL" if bad_slab else "PASS",
                   f"polygons de losa validos: {bad_slab or 'ok'}"))

    lo = [e for e in elements if e["analysis_status"] == "LOAD_ONLY"]
    issues.append(("PASS" if lo else "WARNING",
                   f"miembros LOAD_ONLY presentes para visualizacion: {len(lo)}"))

    unchanged = [rel for rel, h in signed.items()
                 if h is not None and hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != h]
    issues.append(("FAIL" if unchanged else "PASS",
                   f"datos OpenSees NO modificados: {unchanged or 'ok'}"))

    lines = ["UNITY EXPORT QA - results/unity_export_check.txt",
             f"modelo: nodes={len(nodes)} elements={len(elements)} "
             f"(FE={len(fe_tags)} LOAD_ONLY={len(lo)}) supports={len(supports)} "
             f"diaphragms={len(diaphragms)} slabs={len(slabs)} "
             f"tributary_areas={len(tributary_areas)}",
             "=" * 62]
    status = 0
    for st, msg in issues:
        lines.append(f"[{st}] {msg}")
        if st == "FAIL":
            status = 1
        elif st == "WARNING" and status == 0:
            status = 2
    overall = "PASS" if status == 0 else ("WARNING" if status == 2 else "FAIL")
    lines.append("=" * 62)
    lines.append(f"VEREDICTO: {overall}")
    qa = ROOT / "results/unity_export_check.txt"
    qa.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()