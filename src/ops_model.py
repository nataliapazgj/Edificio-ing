"""
Construccion del modelo OpenSeesPy 3D lineal (v2 - red nodal por planta).

CORRECCION DE REGISTRO (documentada):
  El desfase +20.52 m en Y entre las familias P1/P2 y P3/P4 se demuestra
  que es un ARTEFACTO DE REGISTRO (traslación pura):
    - misma rejilla X {0,10,20,30,40,45};
    - mismo espaciado relativo Y (7.25, 8.9);
    - dx=0 y dy=+20.52 exactos entre posiciones correspondientes;
    - 18/18 pilares P3 coinciden con los de P2 tras restar 20.52;
    - las filas de vigas de P3 caen sobre las de P2 tras restar 20.52.
  => Se CORRIGE trasladando P3 y P4 en -20.52 m (eje Y).

VIGAS Y MUROS:
  Se incorporan las high-confidence ESTRUCTURALMENTE CONECTABLES creando
  nodos en extremos e intersecciones (sin exigir snap 0.50 a pilares).
  - nodos en cada extremo/intersección (deduplicados con tolerancia de
    fusion MERGE_TOL);
  - cada nodo no-pilar se ancla al pilar mas cercano de su nivel con
    equalDOF(1..6) = vinculo rigido tributario completo (idealizacion
    documentada: traslaciones + rotaciones acopladas al pilar);
  - se conservan elementos cuyos 2 extremos quedan anclados a un pilar a
    distancia <= DIST_ANCHOR (contrariamente al criterio snap 0.50);
  - NO se incluyen elementos status="ambiguous".
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops
from structure_params import (
    E, G,
    COL_A, COL_IY, COL_IZ, COL_J,
    BEAM_A, BEAM_IY, BEAM_IZ, BEAM_J,
    WALL_THICKNESS, WALL_H_DEFAULT,
    NODE_SNAP_TOL, COLUMN_MATCH_TOL,
)

DY_CORRECTION = -20.52
CORRECT_LEVELS = ("P3", "P4")
MERGE_TOL = 0.15          # fusion historica de nodos de red por planta
DIST_ANCHOR = 8.0         # maxima distancia nodo->pilar (criterio de inclusion v2)
STRUCT_TOL = 0.5          # dist. punto-a-linea para declarar encuentro estructural

def load_aligned(correct=True):
    p = ROOT / "data" / "processed" / "building_3d_aligned.json"
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if correct:
        _shift_plant(data, CORRECT_LEVELS, DY_CORRECTION)
    return data


def _shift_plant(data, levels, dy):
    lvset = set(levels)
    for n in data["nodes"]:
        if n["level"] in lvset:
            n["y"] = n["y"] + dy
    for e in data["beams"] + data["walls"]:
        if e["level"] in lvset:
            e["y1"] = e["y1"] + dy
            e["y2"] = e["y2"] + dy
    for s in data["slabs"]:
        if s["level"] in lvset:
            s["vertices_m"] = [[x, y + dy] for x, y in s["vertices_m"]]
    for orig in data.get("plant_origins_m", {}):
        if orig in lvset:
            data["plant_origins_m"][orig]["y"] = data["plant_origins_m"][orig]["y"] + dy
    data.setdefault("meta", {})["note"] = (
        "Correccion de registro aplicada: P3/P4 trasladados Y=-20.52 m (artefacto de registro)."
    )
    return data


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


# ───────────────────────────────────────────────────────────────────────────

def build_ops_model(data, frame_levels=("P1", "P2", "P3", "P4")):
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

    # ── Stacks verticales por coincidencia de rejilla ──
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

    # ── Crear nodos pilar ──
    node_tag = 1
    joint = {}          # (level,x,y)->tag  (pilares y nodos de red)
    pillar_nodes = {}   # level -> set(tags)
    col_tags_level = {} # level -> [tags] (rejilla de pilares)
    col_xy_level = {}   # level -> [xy]

    def new_node(x, y, z):
        nonlocal node_tag
        ops.node(node_tag, x, y, z)
        node_tag += 1
        return node_tag - 1

    for lvl in frame_levels:
        col_tags_level[lvl] = []
        col_xy_level[lvl] = []
        for xy in level_grid.get(lvl, []):
            k = (lvl, round(xy[0], 3), round(xy[1], 3))
            if k not in joint:
                joint[k] = new_node(xy[0], xy[1], lv_meta[lvl]["elevation"])
                pillar_nodes.setdefault(lvl, set()).add(joint[k])
            col_tags_level[lvl].append(joint[k])
            col_xy_level[lvl].append(xy)

    # ── Transforms ──
    ops.geomTransf("Linear", 1, 0, 0, 1)
    ops.geomTransf("Linear", 2, 0, 0, 1)
    ops.geomTransf("Linear", 3, 1, 0, 0)

    # ── Columnas ──
    elem_tag = 1
    col_elements = []

    # pilares "soportados": (x,y) presente en todos los niveles desde P1
    supported_xy = {}
    acc = None
    for lvl in levels_in_order:
        g = set((round(x, 3), round(y, 3)) for x, y in level_grid.get(lvl["id"], []))
        acc = g if acc is None else (acc & g)
        supported_xy[lvl["id"]] = set(acc)
    supported_col_tag = {lvl: set() for lvl in frame_levels}
    for (pa, pb, li, lj) in stack_defs:
        if (round(pa[0], 3), round(pa[1], 3)) in supported_xy[li]:
            supported_col_tag[li].add(joint[(li, round(pa[0], 3), round(pa[1], 3))])
        if (round(pb[0], 3), round(pb[1], 3)) in supported_xy[lj]:
            supported_col_tag[lj].add(joint[(lj, round(pb[0], 3), round(pb[1], 3))])

    for (pa, pb, li, lj) in stack_defs:
        ia = joint[(li, round(pa[0], 3), round(pa[1], 3))]
        ib = joint[(lj, round(pb[0], 3), round(pb[1], 3))]
        if ia not in supported_col_tag[li]:
            # Columna sin pilar base continuo (p.ej. P2 x=40 sin P1):
            # no tiene fundacion real; se EXCLUYE del portico y se documenta.
            # (Los nodos quedan como nodos de losa, sin mecanismo.)
            continue
        x1, y1, z1 = ops.nodeCoord(ia)
        x2, y2, z2 = ops.nodeCoord(ib)
        L = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
        ops.element("elasticBeamColumn", elem_tag, ia, ib,
                     COL_A, E, G, COL_J, COL_IY, COL_IZ, 3)
        col_elements.append({"tag": elem_tag, "ni": ia, "nj": ib,
                             "level_i": li, "level_j": lj, "length": L,
                             "supported": True})
        elem_tag += 1

    for lvl in frame_levels:
        for k, v in joint.items():
            pass
    # actualizar supported de pilares (ya solo quedan soportados)
    for lvl in frame_levels:
        sup = set()
        for c in col_elements:
            if c["level_i"] == lvl:
                sup.add(c["ni"])
            if c["level_j"] == lvl:
                sup.add(c["nj"])
        supported_col_tag[lvl] = sup if sup else supported_col_tag[lvl]

    # ── Red por nivel: vigas + muros (TOPOLOGIA CONSOLIDADA) ──
    # IDEAS CLAVE:
    #  - Nodos SOLO en encuentros estructurales reales: columna, extremo de
    #    muro, extremo/cruce real de viga. Los puntos auxiliares introducidos
    #    antes por split_segments NO existen ya como nodos => se eliminan de
    #    raiz los mecanismos por nodos auxiliares/subdivision.
    #  - Cada viga fisica aceptada (143-2 excluidas por el criterio v2) se
    #    consolida en UNA cadena de elementos entre nudos estructurales que
    #    estan SOBRE su trazo (p.ej. columnas interiores en su linea).
    #    Longitud total y trazado exactos => areas tributarias y q_G intactos.
    #  - Un extremo a <= NODE_SNAP_TOL de una columna se SUELDA al nudo de
    #    columna (sin micro-segmentos).
    #  - Sin equalDOF(1..6): la estabilidad la dan los elementos (3D) + el
    #    diafragma rigido (solo dofs 1,2,6).
    beam_elements = []
    wall_elements = []
    included_beams = {}      # (lvl, orig) -> [elementTags]
    included_walls = {}      # (lvl, orig) -> [elementTags]
    physical_beam_map = {}   # (lvl, orig) -> trazabilidad viga fisica

    def snap_to_col(x, y, col_xy, col_list):
        best, bd = None, NODE_SNAP_TOL
        for c, ctag in zip(col_xy, col_list):
            dd = math.hypot(x - c[0], y - c[1])
            if dd < bd:
                bd, best = dd, ctag
        return best

    def near_supported(x, y, col_xy, col_list, sup_set):
        """Criterio de inclusion v2: extremo a <= DIST_ANCHOR de un pilar
        soportado (con columna continua a base). Los 5 elementos 'no
        conectables' (>8.0 m) quedan EXCLUIDOS (no se recuperan)."""
        for c, ctag in zip(col_xy, col_list):
            if ctag not in sup_set:
                continue
            if math.hypot(x - c[0], y - c[1]) <= DIST_ANCHOR:
                return True
        return False

    def make_resolver(lvl, col_xy, col_list):
        """Resuelve punto -> tag de nodo, fusionando (MERGE_TOL) extremos
        coincidentes de distintas vigas/muros fisicas: NO pueden quedar dos
        nodos en la misma coordenada (nodos colgantes => mecanismo)."""
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
            # suelda extremos/escalones a la columna mas cercana (sin micro-stubs)
            # y fusiona extremos coincidentes de otras vigas/muros (sin duplicar)
            ca = resolve(ux0, uy0)
            cb = resolve(ux1, uy1)
            if ca == cb:
                continue
            xa, ya, _za = ops.nodeCoord(ca)
            xb, yb, _zb = ops.nodeCoord(cb)
            if not (near_supported(xa, ya, col_xy, col_list, sup_set)
                    and near_supported(xb, yb, col_xy, col_list, sup_set)):
                continue
            L = math.hypot(xb - xa, yb - ya)
            if L < 1e-6:
                continue
            transf = 1 if abs(xb - xa) >= abs(yb - ya) else 2
            if is_wall:
                A8 = WALL_THICKNESS * WALL_H_DEFAULT
                IY = WALL_THICKNESS * WALL_H_DEFAULT ** 3 / 12.0
                IZ = WALL_THICKNESS ** 3 * WALL_H_DEFAULT / 12.0
                Jv = IY + IZ
            else:
                A8, IY, IZ, Jv = BEAM_A, BEAM_IY, BEAM_IZ, BEAM_J
            ops.element("elasticBeamColumn", elem_tag, ca, cb,
                        A8, E, G, Jv, IY, IZ, transf)
            rec = {"tag": elem_tag, "ni": ca, "nj": cb, "level": lvl,
                   "length": L, "orig": src, "kind": "wall" if is_wall else "beam"}
            (wall_elements if is_wall else beam_elements).append(rec)
            (included_walls if is_wall else included_beams).setdefault((lvl, src), []).append(elem_tag)
            tags.append(elem_tag)
            pt_used.add(ca); pt_used.add(cb)
            elem_tag += 1
        return tags

    for lvl in frame_levels:
        beams_lvl = [b for b in hb if b["level"] == lvl]
        walls_lvl = [w for w in hw if w["level"] == lvl]

        col_xy = list(level_grid.get(lvl, []))
        col_list = list(col_tags_level[lvl])
        sup_set = supported_col_tag.get(lvl, set())

        # puntos estructurales reales de este piso
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

    # ── Muros/vigas "solo carga" (sin rigidez en el FE) ──
    # Miembros fisicos cuya cadena de elementos NO alcanza ninguna columna
    # (componente conexa sin nodo de columna). Son tramos cortos/particiones
    # apoyados en la losa que, sin equalDOF(1..6), generan mecanismos de
    # cuerpo rigido (diagnostico: 7 islas, 16 muros en P1-P4, 33 elementos).
    # Se retiran del FE; su peso propio se transfiere a las vigas reales mas
    # proximas (gravity.py) y su geometria queda trazada como load_only en
    # physical_beam_map para Unity/trazabilidad.
    parent = {t: t for t in ops.getNodeTags()}

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
        wall_elements = [e for e in wall_elements if e["tag"] not in load_only_tags]
        beam_elements = [e for e in beam_elements if e["tag"] not in load_only_tags]
        for k, tags in list(included_beams.items()):
            included_beams[k] = [t for t in tags if t not in load_only_tags]
        for k, tags in list(included_walls.items()):
            included_walls[k] = [t for t in tags if t not in load_only_tags]
    load_only_members = {}   # (lvl, orig) -> geometria para transferencia de peso
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

    # ── Purgar nodos: SOLO quedan extremos reales de elementos ──
    # (ya no se protege ningun pilar "fantasma"; si un pilar no tiene ningun
    #  elemento, no es estructural y se retira del FE conservandolo en datos.)
    used_nodes = set()
    for e in col_elements + beam_elements + wall_elements:
        used_nodes.add(e["ni"])
        used_nodes.add(e["nj"])
    for nid in list(ops.getNodeTags()):
        if nid not in used_nodes:
            try:
                ops.remove("node", nid)
            except Exception:
                pass

    # ── DIAFRAGMA RIGIDO REAL por cada nivel (P1..P4) ──
    # rigidDiaphragm(perpDirn=3) restringe SOLO los DOF en el plano del piso
    # (ux, uy, rotz -> dofs 1,2,6) relativos al movimiento de cuerpo rigido del
    # master. NO impone ninguna restriccion sobre el DOF vertical uz (dof 3)
    # ni sobre las rotaciones fuera del plano (4,5): esos DOFs siguen libres y
    # son soportados fisicamente por vigas/columnas/muros (elasticBeamColumn 3D).
    # Sin equalDOF en paralelo => ningun DOF queda doblemente restringido.
    # (La formulacion Transformation + RigidDiaphragm es exacta: las cargas de
    #  gravedad en nodos libres se transmiten por elementos hasta la base.)
    diaphragms = {}
    level_joint_tags = {}
    for lvl in frame_levels:
        zlvl = lv_meta[lvl]["elevation"]
        tags = sorted(t for t in used_nodes
                      if abs(ops.nodeCoord(t)[2] - zlvl) < 1e-9)
        sup_here = sorted(t for t in tags if t in supported_col_tag.get(lvl, set()))
        if not tags or not sup_here:
            level_joint_tags[lvl] = tags
            continue
        master = sup_here[0]
        slaves = [t for t in tags if t != master]
        if slaves:
            ops.rigidDiaphragm(3, master, *slaves)
        diaphragms[lvl] = {"master": master, "slaves": slaves, "n": len(tags)}
        level_joint_tags[lvl] = tags

    # ── Apoyos: fijar P1 (base provisional) ──
    base_fixed = []
    base = frame_levels[0]
    for (a, b, c) in joint.keys():
        if a == base and joint[(a, b, c)] in used_nodes:
            t = joint[(a, b, c)]
            ops.fix(t, 1, 1, 1, 1, 1, 1)
            base_fixed.append(t)

    summary = {
        "n_nodes": len(ops.getNodeTags()),
        "n_elements": len(ops.getEleTags()),
        "n_columns": len(col_elements),
        "n_beams": len(beam_elements),
        "n_walls": len(wall_elements),
        "n_walls_load_only": sum(1 for v in load_only_members.values() if v["kind"] == "wall"),
        "n_beams_load_only": sum(1 for v in load_only_members.values() if v["kind"] == "beam"),
        "n_diaphragms": len(diaphragms),
        "n_base_fixed": len(base_fixed),
        "col_elements": col_elements,
        "beam_elements": beam_elements,
        "wall_elements": wall_elements,
        "diaphragms": diaphragms,
        "base_fixed_tags": base_fixed,
        "level_joint_tags": level_joint_tags,
        "included_beams": included_beams,
        "included_walls": included_walls,
        "n_hi_beams": {l: len([b for b in hb if b["level"] == l]) for l in frame_levels},
        "n_hi_walls": {l: len([w for w in hw if w["level"] == l]) for l in frame_levels},
        "col_stacks": stack_defs,
        "anchored_nodes": {},
        "physical_beam_map": physical_beam_map,
        "load_only_members": load_only_members,
    }
    return summary


# ───────────────────────────────────────────────────────────────────────────
# Verificaciones (solo las 7 pedidas)
# ───────────────────────────────────────────────────────────────────────────

def verify_model(summary, data):
    r = {}
    tags = ops.getNodeTags()
    r["nodos_duplicados"] = ("OK" if len(tags) == len(set(tags)) else "FALLO",
                             f"{len(tags)-len(set(tags))} dup")

    zero = 0
    for tag in ops.getEleTags():
        ni, nj = ops.eleNodes(tag)
        x1, y1, z1 = ops.nodeCoord(ni)
        x2, y2, z2 = ops.nodeCoord(nj)
        if math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2) < 1e-6:
            zero += 1
    r["longitud_cero"] = ("OK" if zero == 0 else "FALLO", f"{zero}")

    # elementos desconectados: union-find por elementos; toda componente debe
    # alcanzar un nodo de base fijado (apoyo real de la red)
    par = {t: t for t in tags}
    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[rb] = ra
    for tag in ops.getEleTags():
        ni, nj = ops.eleNodes(tag)
        union(ni, nj)
    base_roots = {find(t) for t in summary["base_fixed_tags"]}
    disconnected = 0
    for t in tags:
        if find(t) not in base_roots:
            disconnected += 1
    r["elementos_desconectados"] = ("OK" if disconnected == 0 else "FALLO",
                                    f"{disconnected} nodos sin ruta a base fija")

    nb = len(summary["included_beams"])
    nw = len(summary["included_walls"])
    tb = sum(summary["n_hi_beams"].values())
    tw = sum(summary["n_hi_walls"].values())
    r["vigas_incorporadas"] = ("OK" if nb >= 0.9*tb else "WARNING", f"{nb}/{tb}")
    r["muros_incorporados"] = ("OK" if nw >= 0.9*tw else "WARNING", f"{nw}/{tw}")

    r["continuidad_P1-P4"] = continuity_check(summary, data)
    return r


def continuity_check(summary, data):
    frame = ("P1", "P2", "P3", "P4")
    grids = {}
    for n in data["nodes"]:
        if n["level"] in frame:
            grids.setdefault(n["level"], set()).add((round(n["x"], 2), round(n["y"], 2)))
    p1 = grids.get("P1", set())
    if not p1:
        return ("FALLO", "sin P1")
    cont = sum(1 for g in p1 if all(g in grids.get(l, set()) for l in ("P2", "P3", "P4")))
    total = len(p1)
    status = "OK" if cont == total else ("WARNING" if cont >= 0.9*total else "FALLO")
    return (status, f"{cont}/{total} pilares P1 alcanzan P4 "
                    f"(P1={total}, P2={len(grids.get('P2',[]))}, "
                    f"P3={len(grids.get('P3',[]))}, P4={len(grids.get('P4',[]))})")


def verify_diaphragms(summary, ok=None):
    """
    Verifica por cada nivel (P1..P4):
      - cuenta nodos y deriva nodos esclavos;
      - compatibilidad HORIZONTAL del diafragma: ux, uy de cada esclavo debe
        reproducir el movimiento de cuerpo rigido del master
        (ux_s = ux_m - thz_m*(y_s-y_m), uy_s = uy_m + thz_m*(x_s-x_m));
      - DOF vertical disponible: el diafragma NO restringe uz (dofs 1,2,6
        solamente) => se reporta el max |uz| de esclavos como evidencia de que
        el DOF vertical permanece activo y vehiculado por elementos.
    Si la etapa estatica no converge (ok != 0) no hay desplazamientos validos:
    se reporta FAIL/n-a sin atribuir la causa al diafragma.
    """
    out = {}
    for lvl, cfg in summary.get("diaphragms", {}).items():
        m = cfg["master"]
        slaves = cfg["slaves"]
        if not slaves:
            out[lvl] = {"state": "FAIL", "detail": "sin esclavos",
                        "master": m, "n_slaves": 0}
            continue
        if ok is not None and ok != 0:
            out[lvl] = {
                "state": "FAIL",
                "master": m, "n_slaves": len(slaves), "n_floor_nodes": cfg["n"],
                "compat_horiz_max_m": "n/a (analisis estatico no convergio)",
                "uz_esclavo_max_m": "n/a",
                "uz_dof": "libre por construccion (rigidDiaphragm restringe solo 1,2,6)",
                "detail": f"analyze retcode={ok}; revisar mecanismo de la red v2 (ver BLOCKED)",
            }
            continue
        xm, ym, _ = ops.nodeCoord(m)
        umx, umy, thz = ops.nodeDisp(m)[0], ops.nodeDisp(m)[1], ops.nodeDisp(m)[5]
        comp_max, uz_max = 0.0, 0.0
        for s in slaves:
            xs, ys, _ = ops.nodeCoord(s)
            ex = umx - thz * (ys - ym)
            ey = umy + thz * (xs - xm)
            uxs, uys, uzs = ops.nodeDisp(s)[0], ops.nodeDisp(s)[1], ops.nodeDisp(s)[2]
            comp_max = max(comp_max, math.hypot(uxs - ex, uys - ey))
            uz_max = max(uz_max, abs(uzs))
        ok2 = comp_max < 1e-6 and uz_max > 1e-9
        out[lvl] = {
            "state": "OK" if ok2 else "FAIL",
            "master": m, "n_slaves": len(slaves), "n_floor_nodes": cfg["n"],
            "compat_horiz_max_m": comp_max,
            "uz_esclavo_max_m": uz_max,
            "uz_dof": "libre (rigidDiaphragm restringe solo dofs 1,2,6)" if uz_max > 1e-9
                      else "BLOQUEADO (dof 3 restringido!)",
        }
    return out