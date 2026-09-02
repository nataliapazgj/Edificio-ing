"""Constructor LT1 adaptado para el modelo combinado (copia encapsulada).

Reimplementa fielmente `ops_model.build_ops_model` SIN tocar el archivo
original `src/ops_model.py`. Cambios SOLO aditivos y coordinados con el
modelo combinado:

  1. `with_init`: si False, NO ejecuta `ops.wipe()` / `ops.model()` (la
     instancia unica ya existe y LT2 esta construido).
  2. Transformación geométrica confirmada (config.transform_lt1).
  3. Offsets de tags (NODE_BASE_LT1 / ELEM_BASE_LT1).
  4. Interfaz: los 12 nodos de interfaz se mapean al tag LT2 (NODO COMPARTIDO,
     no se crea duplicado).
  5. geomTransf LT1 con tags propios 3001/3002/3003 (correctos tras reflexión Y).
  6. Se descartan las 9 columnas LT1 que duplican a LT2 (P003/P007/P010).
  7. El purge de nodos y el union-find se limitan a los nodos LT1 (no tocan LT2).

El `summary` devuelto tiene la MISMA forma que el de `ops_model.build_ops_model`
(a efectos de compute_tributary / gravity LT1), con tags ya offset.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops  # noqa: E402
from ops_model import load_aligned  # noqa: E402  (puro, no wipe)

from . import config as C

DY_CORRECTION = -20.52
CORRECT_LEVELS = ("P3", "P4")
MERGE_TOL = 0.15
DIST_ANCHOR = 8.0
STRUCT_TOL = 0.5
NODE_SNAP_TOL = 0.50
COLUMN_MATCH_TOL = 0.50

# Tags geomTransf LT1 (config) -> descripción
TRANS_COL_LT1, TRANS_BX_LT1, TRANS_BY_LT1 = C.TRANS_LT1

# Líneas de interfaz LT1 -> tag LT2  (clave (level, y a 3 decimales))
IFACE_LOC = {
    ("P1", -0.25): 114, ("P1", -9.15): 117, ("P1", -16.40): 118,
    ("P2", -0.25): 162, ("P2", -9.15): 165, ("P2", -16.40): 166,
    ("P3", -0.25): 210, ("P3", -9.15): 213, ("P3", -16.40): 214,
    ("P4", -0.25): 268, ("P4", -9.15): 271, ("P4", -16.40): 272,
}
IFACE_TAGS = set(IFACE_LOC.values())


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def seg_intersection(s, t):
    (x1, y1, x2, y2) = s
    (x3, y3, x4, y4) = t
    dxs, dys = x2 - x1, y2 - y1
    dxt, dyt = x4 - x3, y4 - y3
    denom = dxs * dyt - dys * dxt
    if abs(denom) < 1e-12:
        return None
    tdx, tdy = x3 - x1, y3 - y1
    ts = (tdx * dyt - tdy * dxt) / denom
    tt = (tdx * dys - tdy * dxs) / denom
    if -1e-9 <= ts <= 1 + 1e-9 and -1e-9 <= tt <= 1 + 1e-9:
        return (ts, tt)
    return None


def split_segments(segs, min_len=0.05):
    subs = []
    for i, s in enumerate(segs):
        ts = [0.0, 1.0]
        for j, t in enumerate(segs):
            if i == j:
                continue
            hit = seg_intersection(s, t)
            if hit:
                ts.append(hit[0])
        ts = sorted(set(round(v, 6) for v in ts))
        keep = [ts[0]]
        for v in ts[1:]:
            if v - keep[-1] > min_len:
                keep.append(v)
        for a, b in zip(keep[:-1], keep[1:]):
            subs.append((
                s[0] + a * (s[2] - s[0]), s[1] + a * (s[3] - s[1]),
                s[0] + b * (s[2] - s[0]), s[1] + b * (s[3] - s[1]),
                i,
            ))
    return subs


def build_ops_model_combined(data, frame_levels=("P1", "P2", "P3", "P4"),
                             with_init=False,
                             node_base=C.NODE_BASE_LT1,
                             elem_base=C.ELEM_BASE_LT1,
                             apply_transform=True):
    """Igual esqueleto que ops_model.build_ops_model pero combinado."""
    if with_init:
        ops.wipe()
        ops.model("basic", "-ndm", 3, "-ndf", 6)

    nodes_data = data["nodes"]
    hb = [b for b in data["beams"] if b["status"] == "high-confidence"]
    hw = [w for w in data["walls"] if w["status"] == "high-confidence"]
    lv_meta = {l["id"]: l for l in data["levels"]}

    level_grid = {}
    for n in nodes_data:
        if n["level"] in frame_levels:
            level_grid.setdefault(n["level"], []).append((n["x"], n["y"]))

    levels_in_order = sorted(
        [lv_meta[k] for k in frame_levels if k in lv_meta],
        key=lambda l: l["elevation"])

    # transforms LT1 (tags propios)
    ops.geomTransf("Linear", TRANS_COL_LT1, 0, 1, 0)
    ops.geomTransf("Linear", TRANS_BX_LT1, 0, 0, 1)
    ops.geomTransf("Linear", TRANS_BY_LT1, 0, 0, 1)

    # stacks verticales por coincidencia de rejilla
    stack_defs = []
    for i, lvl in enumerate(levels_in_order[:-1]):
        nxt = levels_in_order[i + 1]
        gA, gB = level_grid.get(lvl["id"], []), level_grid.get(nxt["id"], [])
        for pa in gA:
            best, bd = None, COLUMN_MATCH_TOL
            for pb in gB:
                d = d2(pa, pb)
                if d < bd:
                    bd, best = d, pb
            if best is not None:
                stack_defs.append((pa, best, lvl["id"], nxt["id"]))

    node_tag = 1
    joint = {}
    pillar_nodes = {}
    col_tags_level = {}
    col_xy_level = {}
    self_lt1_nodes = set()
    node_raw = {}   # tag -> (x, y) en frame raw de LT1 (consistencia near_supported)

    def new_node(x, y, z):
        nonlocal node_tag
        # Se crea el nodo en coords GLOBALES (transformadas) si apply_transform,
        # pero se guarda en `node_raw` la coord RAW de LT1: toda la logica de
        # construccion (chain_segments, near_supported, snap_to_col) evalua en
        # frame raw, y el propio OpenSees guarda la posicion global real.
        if apply_transform:
            X, Y, Z = C.transform_lt1(x, y, z)
        else:
            X, Y, Z = x, y, z
        tag = node_base + node_tag
        ops.node(tag, X, Y, Z)
        self_lt1_nodes.add(tag)
        node_raw[tag] = (x, y)
        node_tag += 1
        return tag

    def resolve_level_node(lvl, x, y):
        """Devuelve tag efectivo: interfaz->LT2, nodo normal->LT1 offset.

        Para los nodos de interfaz se reutiliza el tag LT2 (NODO COMPARTIDO;
        NO se crea un duplicado en la misma coordenada). El mapeo queda
        registrado en `joint` para mantener la misma topologia KeyError-free.
        """
        k = (lvl, round(x, 3), round(y, 3))
        if k in joint:
            return joint[k]
        key3 = round(y, 3)
        lt2 = IFACE_LOC.get((lvl, key3))
        if lt2 is not None and apply_transform and abs(x) < 1e-6:
            joint[k] = lt2
            node_raw[lt2] = (x, key3)   # coords raw del punto de interfaz
            return lt2
        joint[k] = new_node(x, y, lv_meta[lvl]["elevation"])
        return joint[k]

    for lvl in frame_levels:
        col_tags_level[lvl] = []
        col_xy_level[lvl] = []
        for xy in level_grid.get(lvl, []):
            t = resolve_level_node(lvl, xy[0], xy[1])
            pillar_nodes.setdefault(lvl, set()).add(t)
            col_tags_level[lvl].append(t)
            col_xy_level[lvl].append(xy)

    elem_tag = 1
    col_elements = []
    supported_xy = {}
    acc = None
    for lvl in levels_in_order:
        g = set((round(x, 3), round(y, 3)) for x, y in
                level_grid.get(lvl["id"], []))
        acc = g if acc is None else (acc & g)
        supported_xy[lvl["id"]] = set(acc)
    supported_col_tag = {lvl: set() for lvl in frame_levels}
    for (pa, pb, li, lj) in stack_defs:
        if (round(pa[0], 3), round(pa[1], 3)) in supported_xy[li]:
            supported_col_tag[li].add(
                joint[(li, round(pa[0], 3), round(pa[1], 3))])
        if (round(pb[0], 3), round(pb[1], 3)) in supported_xy[lj]:
            supported_col_tag[lj].add(
                joint[(lj, round(pb[0], 3), round(pb[1], 3))])

    for (pa, pb, li, lj) in stack_defs:
        ia = joint[(li, round(pa[0], 3), round(pa[1], 3))]
        ib = joint[(lj, round(pb[0], 3), round(pb[1], 3))]
        if ia not in supported_col_tag[li]:
            continue
        # DESCARTA columnas LT1 de la interfaz (duplican LT2 P003/P007/P010)
        if {ia, ib} <= IFACE_TAGS:
            continue
        x1, y1, z1 = ops.nodeCoord(ia)
        x2, y2, z2 = ops.nodeCoord(ib)
        L = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
        etag = elem_base + elem_tag
        ops.element("elasticBeamColumn", etag, ia, ib,
                    C.COL["A"], C.E_KN_M2, C.G_KN_M2,
                    C.COL["J"], C.COL["IY"], C.COL["IZ"], TRANS_COL_LT1)
        col_elements.append({"tag": etag, "ni": ia, "nj": ib,
                             "level_i": li, "level_j": lj, "length": L,
                             "supported": True})
        elem_tag += 1

    for lvl in frame_levels:
        sup = set()
        for c in col_elements:
            if c["level_i"] == lvl:
                sup.add(c["ni"])
            if c["level_j"] == lvl:
                sup.add(c["nj"])
        supported_col_tag[lvl] = sup if sup else supported_col_tag[lvl]
        # La interfaz aporta columnas a traves de LT2 (P003/P007/P010 continuas
        # B1..ROOF). Sus nodos compartidos cuentan como SOPORTE para las
        # vigas/muros de LT1 que anclan en el borde, aunque las columnas LT1
        # duplicadas se descarten.
        supported_col_tag[lvl] |= C.INTERFACE_LT2_PER_LEVEL.get(lvl, set())

    beam_elements = []
    wall_elements = []
    included_beams = {}
    included_walls = {}
    physical_beam_map = {}

    def snap_to_col(x, y, col_xy, col_list):
        best, bd = None, NODE_SNAP_TOL
        for c, ctag in zip(col_xy, col_list):
            dd = math.hypot(x - c[0], y - c[1])
            if dd < bd:
                bd, best = dd, ctag
        return best

    def near_supported(x, y, col_xy, col_list, sup_set):
        for c, ctag in zip(col_xy, col_list):
            if ctag not in sup_set:
                continue
            if math.hypot(x - c[0], y - c[1]) <= DIST_ANCHOR:
                return True
        return False

    def make_resolver(lvl, col_xy, col_list):
        nd_map = {}
        for c, tag in zip(col_xy, col_list):
            nd_map[(round(c[0], 3), round(c[1], 3))] = tag
        def resolve(x, y):
            t = snap_to_col(x, y, col_xy, col_list)
            if t is not None:
                return t
            for k, v in nd_map.items():
                if math.hypot(x - k[0], y - k[1]) < MERGE_TOL:
                    return v
            t = new_node(x, y, lv_meta[lvl]["elevation"])
            nd_map[(round(x, 3), round(y, 3))] = t
            return t
        return resolve

    def chain_segments(lvl, x1, y1, x2, y2, src, is_wall, col_xy, col_list,
                       sup_set, struct_pts, pt_used, resolve):
        nonlocal elem_tag
        Ltot = math.hypot(x2 - x1, y2 - y1)
        if Ltot < 1e-9:
            return []
        eps = max(1e-4, Ltot * 1e-9)
        pts = [(0.0, (x1, y1)), (1.0, (x2, y2))]
        for (px, py) in struct_pts:
            dx, dy = x2 - x1, y2 - y1
            t = ((px - x1) * dx + (py - y1) * dy) / (Ltot * Ltot)
            if t <= -eps or t >= 1 + eps:
                continue
            cx, cy = x1 + t * dx, y1 + t * dy
            if math.hypot(px - cx, py - cy) <= STRUCT_TOL:
                pts.append((t, (px, py)))
        uniq = []
        for t, p in sorted(pts):
            if uniq and abs(t - uniq[-1][0]) < 1e-6:
                continue
            uniq.append((t, p))
        tags = []
        for (t0, (ux0, uy0)), (t1, (ux1, uy1)) in zip(uniq[:-1], uniq[1:]):
            if t1 - t0 <= 1e-6:
                continue
            ca = resolve(ux0, uy0)
            cb = resolve(ux1, uy1)
            if ca == cb:
                continue
            xa, ya = node_raw[ca]
            xb, yb = node_raw[cb]
            if not (near_supported(xa, ya, col_xy, col_list, sup_set)
                    and near_supported(xb, yb, col_xy, col_list, sup_set)):
                continue
            L = math.hypot(xb - xa, yb - ya)
            if L < 1e-6:
                DEBUG_REJ["zero"] += 1
                continue
            transf = TRANS_BX_LT1 if abs(xb - xa) >= abs(yb - ya) else TRANS_BY_LT1
            if is_wall:
                A8 = C.WALL["t"] * C.WALL["h"]
                IY = C.WALL["t"] * C.WALL["h"] ** 3 / 12.0
                IZ = C.WALL["t"] ** 3 * C.WALL["h"] / 12.0
                Jv = IY + IZ
            else:
                A8, IY, IZ, Jv = (C.BEAM["A"], C.BEAM["IY"],
                                  C.BEAM["IZ"], C.BEAM["J"])
            etag = elem_base + elem_tag
            ops.element("elasticBeamColumn", etag, ca, cb,
                        A8, C.E_KN_M2, C.G_KN_M2, Jv, IY, IZ, transf)
            rec = {"tag": etag, "ni": ca, "nj": cb, "level": lvl,
                   "length": L, "orig": src,
                   "kind": "wall" if is_wall else "beam"}
            (wall_elements if is_wall else beam_elements).append(rec)
            (included_walls if is_wall else included_beams).setdefault(
                (lvl, src), []).append(etag)
            tags.append(etag)
            pt_used.add(ca); pt_used.add(cb)
            elem_tag += 1
        return tags

    for lvl in frame_levels:
        beams_lvl = [b for b in hb if b["level"] == lvl]
        walls_lvl = [w for w in hw if w["level"] == lvl]
        col_xy = list(level_grid.get(lvl, []))
        col_list = list(col_tags_level[lvl])
        sup_set = supported_col_tag.get(lvl, set())
        struct_pts = set((round(c[0], 3), round(c[1], 3)) for c in col_xy)
        for b in beams_lvl:
            struct_pts.add((round(b["x1"], 3), round(b["y1"], 3)))
            struct_pts.add((round(b["x2"], 3), round(b["y2"], 3)))
        for w in walls_lvl:
            struct_pts.add((round(w["x1"], 3), round(w["y1"], 3)))
            struct_pts.add((round(w["x2"], 3), round(w["y2"], 3)))
        struct_pts = sorted(struct_pts)
        pt_used = set()
        resolve = make_resolver(lvl, col_xy, col_list)
        for i, b in enumerate(beams_lvl):
            el = chain_segments(lvl, b["x1"], b["y1"], b["x2"], b["y2"],
                                i, False, col_xy, col_list, sup_set,
                                struct_pts, pt_used, resolve)
            physical_beam_map[(lvl, i)] = {
                "kind": "beam", "x1": b["x1"], "y1": b["y1"],
                "x2": b["x2"], "y2": b["y2"],
                "length_m": math.hypot(b["x2"] - b["x1"], b["y2"] - b["y1"]),
                "source_ids": [i], "elements": el,
            }
        for j, w in enumerate(walls_lvl):
            el = chain_segments(lvl, w["x1"], w["y1"], w["x2"], w["y2"],
                                len(beams_lvl) + j, True, col_xy, col_list,
                                sup_set, struct_pts, pt_used, resolve)
            physical_beam_map[(lvl, len(beams_lvl) + j)] = {
                "kind": "wall", "x1": w["x1"], "y1": w["y1"],
                "x2": w["x2"], "y2": w["y2"],
                "length_m": math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"]),
                "source_ids": [j], "elements": el,
            }

    # union-find solo sobre nodos LT1 (+ interfaz)
    parent = {t: t for t in (self_lt1_nodes | IFACE_TAGS)}

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    for e in col_elements + beam_elements + wall_elements:
        _union(e["ni"], e["nj"])
    col_roots = set()
    for e in col_elements:
        col_roots.add(_find(e["ni"]))
        col_roots.add(_find(e["nj"]))
    # Los nodos de interfaz compartidos son columnas LT2 continuas: constituyen
    # raices de soporte para cualquier viga/muro de LT1 que ancle en ellos, por
    # lo que NO se purgan como islas.
    for t in IFACE_TAGS:
        col_roots.add(_find(t))

    load_only_tags = set()
    for e in beam_elements + wall_elements:
        if _find(e["ni"]) not in col_roots and _find(e["nj"]) not in col_roots:
            load_only_tags.add(e["tag"])
    if load_only_tags:
        for e in beam_elements + wall_elements:
            if e["tag"] in load_only_tags:
                try:
                    ops.remove("element", e["tag"])
                except Exception:
                    pass
        wall_elements = [e for e in wall_elements
                         if e["tag"] not in load_only_tags]
        beam_elements = [e for e in beam_elements
                         if e["tag"] not in load_only_tags]
        for k, tags in list(included_beams.items()):
            included_beams[k] = [t for t in tags if t not in load_only_tags]
        for k, tags in list(included_walls.items()):
            included_walls[k] = [t for t in tags if t not in load_only_tags]
    load_only_members = {}
    for k, info in physical_beam_map.items():
        tags = info.get("elements") or []
        if tags and all(t in load_only_tags for t in tags):
            info["elements"] = []
            info["load_only"] = True
            load_only_members[k] = {
                "kind": info["kind"], "x1": info["x1"], "y1": info["y1"],
                "x2": info["x2"], "y2": info["y2"],
                "length_m": info["length_m"], "level": k[0],
            }

    # purge de nodos LT1 (solo self_lt1_nodes, NO toca LT2)
    used_nodes = set()
    for e in col_elements + beam_elements + wall_elements:
        used_nodes.add(e["ni"])
        used_nodes.add(e["nj"])
    for nid in sorted(self_lt1_nodes):
        if nid not in used_nodes:
            try:
                ops.remove("node", nid)
                self_lt1_nodes.discard(nid)
            except Exception:
                pass

    # diafragma LT1 POR NIVEL (para conservar shape de summary); el diafragma
    # combinado se construye luego en el orquestador. Aqui solo se registra el
    # conteo/master candidato de LT1 (no se crea rigidDiaphragm propio).
    diaphragms = {}
    level_joint_tags = {}
    for lvl in frame_levels:
        zlvl = lv_meta[lvl]["elevation"]
        tags = sorted(t for t in (used_nodes | set(IFACE_LOC.values()))
                      if abs(ops.nodeCoord(t)[2] - zlvl) < 1e-9)
        sup_here = sorted(t for t in tags
                          if t in supported_col_tag.get(lvl, set()))
        # No creamos rigidDiaphragm LT1: el diafragma combinado lo hara el
        # orquestador (master LT2). Solo guardamos la info de trazabilidad.
        diaphragms[lvl] = {"master": (sup_here[0] if sup_here else None),
                           "defer_to_orchestrator": True, "n": len(tags)}
        level_joint_tags[lvl] = tags

    # apoyos: fijar P1 (base provisional) de LT1
    base_fixed = []
    base = frame_levels[0]
    for (a, b, c) in joint.keys():
        if a == base and joint[(a, b, c)] in used_nodes:
            t = joint[(a, b, c)]
            ops.fix(t, 1, 1, 1, 1, 1, 1)
            base_fixed.append(t)

    summary = {
        "n_nodes_lt1": len(self_lt1_nodes),
        "n_nodes": len(self_lt1_nodes) + len(IFACE_TAGS),
        "n_elements": len(ops.getEleTags()),   # incluye LT2; no usar para LT1
        "n_columns": len(col_elements),
        "n_beams": len(beam_elements),
        "n_walls": len(wall_elements),
        "n_walls_load_only": sum(1 for v in load_only_members.values()
                                 if v["kind"] == "wall"),
        "n_beams_load_only": sum(1 for v in load_only_members.values()
                                 if v["kind"] == "beam"),
        "n_diaphragms_lt1": 0,
        "n_base_fixed": len(base_fixed),
        "col_elements": col_elements,
        "beam_elements": beam_elements,
        "wall_elements": wall_elements,
        "diaphragms": diaphragms,
        "base_fixed_tags": base_fixed,
        "level_joint_tags": level_joint_tags,
        "included_beams": included_beams,
        "included_walls": included_walls,
        "n_hi_beams": {l: len([b for b in hb if b["level"] == l])
                       for l in frame_levels},
        "n_hi_walls": {l: len([w for w in hw if w["level"] == l])
                       for l in frame_levels},
        "col_stacks": stack_defs,
        "anchored_nodes": {},
        "physical_beam_map": physical_beam_map,
        "load_only_members": load_only_members,
        "self_lt1_nodes": self_lt1_nodes,
        "interface_lt2_tags": sorted(IFACE_TAGS),
    }
    return summary


def lt1_level_z_map(data):
    return {l["id"]: float(l["elevation"]) for l in data["levels"]}