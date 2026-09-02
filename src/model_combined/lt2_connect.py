"""Conexion de vigas LT2 flotantes a su apoyo estructural (muros-columna).

Diagnostico (LT2, tras materializar M001-M008 como columnas):
  - 9 componentes conectados sin camino al apoyo (mecanismos de cuerpo
    rigido vertical) por VIGAS flotantes.
  - Se clasifican en dos familias por su funcion y carga real:

   (A) CABEZEROS V40 en x = 0.40 (cara este de M001/M003, espesor 0.60,
       centro en x = 0.10 -> caras en -0.20/+0.40), en L1..L4 y ROOF.
       Son PORTANTES (16 de 16 con carga de losa segun
       beam_gravity_loads_LT2.csv) y framan contra el muro: sus nodos
       EXTREMOS estan a 0.30 m de los nodos de los muros-columna M001/M003.
       Se CONECTAN al muro-columna mas cercano del mismo nivel con
       equalDOF(1,2,3): el nudo del cabezaero comparte UX/UY/UZ con el nudo
       del muro-columna que lo sostiene. No modifica geometria de elemento
       ni crea rigidez artificial en el muro; es la conexion viga-apoyo.
   (B) MALLA/parapeto de ROOF (2231-2234, 2236-2237): NO portantes (no
       aparecen en beam_gravity_loads_LT2.csv; la carga ROOF fue excluida
       del benchmark LT2) y SIN apoyo dentro de COLUMN_MATCH_TOL en ningun
       nivel. Se RETIRAN del FE como elementos "solo carga cero": al no
       llevar carga, retirarlos no altera el equilibrio ni el balance de
       reacciones (convencion identica a "load_only" de LT1 para miembros
       que no llegan a ninguna columna). Se documentan como
       ESTRUCTURA_NO_SOPORTADA_NO_PORTANTE.

Tras conectar/retirar, los nodos huerfanos (0 elementos) se ELIMINAN para no
dejar grados de libertad libres. Los nodos maestro de diafragma (1001..1005)
ya estan fijados en uz/rx/ry por `_build_masters` y se estabilizan en plano
por el rigidDiaphragm: se excluyen del analisis de mecanismos.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

import openseespy.opensees as ops  # noqa: E402

from build_opensees_model import (  # noqa: E402
    TOL_NODE, TAG_SECTION_BASE, TAG_BEAM_BASE, TRANS_COL, TRANS_B_X, TRANS_B_Y,
)

COLUMN_MATCH_TOL = 0.50   # misma tolerancia de empalme columnas que usa LT1

TAG_COL_BASE = 3001       # columnas LT2
TAG_WALL_BASE = 4001      # muros-columna LT2 (creados por lt2_walls)

# Cabezeros V40 en x=0.40: se conectan al muro (portantes).
# Malla/parapeto ROOF sin carga: se retira (solo carga cero).
REMOVE_LOAD_FREE_FLOATING = True


class _UnionFind:
    def __init__(self, nodes):
        self.parent = {n: n for n in nodes}

    def find(self, a):
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _elem_node_map():
    """tag elemento -> (n1, n2) de todos los elementos vigentes."""
    out = {}
    for t in ops.getEleTags():
        try:
            out[t] = tuple(ops.eleNodes(t))
        except Exception:
            continue
    return out


def _wall_candidates(lt2):
    """Nodos de los muros-columna LT2 (extremos de elementos >= TAG_WALL_BASE)."""
    cand: Set[int] = set()
    master = set(lt2.master_tags or [])
    for t, (n1, n2) in _elem_node_map().items():
        if t >= TAG_WALL_BASE:
            if n1 not in master:
                cand.add(n1)
            if n2 not in master:
                cand.add(n2)
    return cand


def _floating_roots(lt2, extra_links=None):
    """Raices (union-find) de componentes SIN nodo de apoyo; excluye masters.

    `extra_links` = lista de pares (a, b) ya conectados por igualdad de DOF
    (equalDOF) que deben unirse topologicamente (el union-find de elementos
    no conoce las constraints).
    """
    nodes = [t for t in ops.getNodeTags()]
    uf = _UnionFind(nodes)
    master = set(lt2.master_tags or [])
    for (n1, n2) in _elem_node_map().values():
        uf.union(n1, n2)
    for (a, b) in (extra_links or []):
        if a in uf.parent and b in uf.parent:
            uf.union(a, b)
    supports = set(lt2.support_tags or [])
    comp: Dict[int, List[int]] = {}
    for n in nodes:
        if n in master:
            continue
        comp.setdefault(uf.find(n), []).append(n)
    return {r for r, ns in comp.items()
            if not any(c in supports for c in ns) and len(ns) > 0}, uf


def _floating_members(lt2, extra_links=None):
    """Por componente flotante, sus nodos y sus elementos de tipo viga."""
    roots, uf = _floating_roots(lt2, extra_links)
    elems = _elem_node_map()
    members = []
    for t, (n1, n2) in elems.items():
        if TAG_COL_BASE <= t < TAG_WALL_BASE:
            continue  # columnas/materializadas no flotan por definicion
        if uf.find(n1) in roots or uf.find(n2) in roots:
            members.append(t)
    return roots, members


def _transf_h(n, sup, coords):
    """Transform axial si el conector (n->sup) es horizontal-X (dy=dz=0)."""
    kn, ks = coords[n], coords[sup]
    dx = ks[0] - kn[0]
    dy = ks[1] - kn[1]
    dz = ks[2] - kn[2]
    if abs(dy) <= TOL_NODE and abs(dz) <= TOL_NODE and abs(dx) > TOL_NODE:
        return TRANS_B_X
    return None


def _beam_section_for_node(lt2, elem_tag, sect_map):
    """Seccion (tag) de la viga `elem_tag` de LT2, o None."""
    i = elem_tag - TAG_BEAM_BASE
    if 0 <= i < len(lt2.builder.elems["beams"]):
        e_ = lt2.builder.elems["beams"][i]
        return sect_map.get(e_["section"])
    return None


def _beam_section_map(lt2):
    """Replica _materialize: section_id -> tag (5001 + ordinal 'ready')."""
    b = lt2.builder
    section_tag: Dict[str, int] = {}
    for _, s in b.sections.iterrows():
        status = b._section_analysis_status(s)
        if status != "ready":
            continue
        section_tag[str(s["section_id"])] = TAG_SECTION_BASE + len(section_tag)
    return section_tag


def _load_carrying_beams(lt2):
    """Tags de viga que SI cargan losa (element_tag en beam_gravity_loads_LT2)."""
    import pandas as pd
    from pathlib import Path
    data_dir = Path(__file__).resolve().parents[2] / "data" / "loads"
    path = data_dir / "beam_gravity_loads_LT2.csv"
    ld = pd.read_csv(path)
    tags = ld["element_tag"].dropna()
    return {int(r) for r in tags.tolist()}


def connect_floating_beams(lt2):
    """Conecta/retira el soporte de las vigas LT2 flotantes.

    Devuelve dict con estadisticas para reporte. NO construye diafragmas
    (llamar justo antes de construirlos).
    """
    coords = {t: tuple(ops.nodeCoord(t)) for t in ops.getNodeTags()}
    master = set(lt2.master_tags or [])
    supports = set(lt2.support_tags or [])
    wall_cand = _wall_candidates(lt2)
    load_carrying = _load_carrying_beams(lt2)
    sect_map = _beam_section_map(lt2)
    links: List[Tuple[int, int]] = list(getattr(lt2, "link_pairs", []) or [])

    # --- (A) conectar cabezero flotante PORTANTE al muro-columna ---
    # Se une cada nodo extremo del cabezero al nodo del muro-columna con un
    # tramo corto de viga REAL (elasticBeamColumn horizontal-X, misma seccion
    # del cabezero). No es rigidLink ni equalDOF: es un elemento normal, evita
    # el conflicto de constraints (Transformation) y modela la conexion
    # viga-muro salvando la excentricidad de 0.3 m (cara vs eje del muro).
    roots, floating = _floating_members(lt2)
    base = 9001
    linked = []
    added = []
    for t in floating:
        n1, n2 = _elem_node_map()[t]
        for n in (n1, n2):
            if n in supports or n in master:
                continue
            sup = _nearest(n, wall_cand, coords)
            if sup is None:
                continue
            # comprobar que el conector es un tramo viga horizontal-X valido
            tr = _transf_h(n, sup, coords)
            if tr is None:
                continue
            sec = _beam_section_for_node(lt2, t, sect_map)
            if sec is None:
                continue
            try:
                ops.element("elasticBeamColumn", base, n, sup, sec, tr)
                added.append(base)
                linked.append((t, n, sup))
                links.append((n, sup))
                base += 1
            except Exception:
                pass
    lt2.diaph_exclude = set()  # los conectores son elementos, no constraints
    lt2.link_pairs = links

    # --- (B) retirar vigas ROOF sin carga y sin apoyo propio ---
    removed_elem = []
    if REMOVE_LOAD_FREE_FLOATING:
        roots, floating = _floating_members(lt2, links)
        for t in list(floating):
            if t not in load_carrying:
                try:
                    ops.remove("element", t)
                    removed_elem.append(t)
                except Exception:
                    pass

    # eliminar nodos huerfanos (0 elementos) que quedaron libres
    removed_nodes = _remove_orphans(lt2, master, supports)

    roots, _ = _floating_roots(lt2, links)
    result = {
        "girder_wall_connectors": linked,
        "n_connectors": len(linked),
        "connector_elem_tags": added,
        "load_free_roof_removed": sorted(removed_elem),
        "n_removed_roof": len(removed_elem),
        "orphans_removed": removed_nodes,
        "floating_components_remaining": len(roots),
    }
    if roots:
        uf = _UnionFind([t for t in ops.getNodeTags()])
        for (n1, n2) in _elem_node_map().values():
            uf.union(n1, n2)
        for (a, b) in links:
            uf.union(a, b)
        comp: Dict[int, List[int]] = {}
        for n in ops.getNodeTags():
            if n in master:
                continue
            comp.setdefault(uf.find(n), []).append(n)
        result["remaining_roots"] = {
            r: sorted(ns) for r, ns in comp.items()
            if ns and not any(c in supports for c in ns)}
    return result


def _girder_level(t):
    """Etiqueta de nivel aproximada para agrupar cabezeros (solo reporte)."""
    if 2097 <= t <= 2112:
        return "L1" if t <= 2100 else ("L2" if t <= 2104 else
                                       ("L3" if t <= 2108 else "L4"))
    if 2209 <= t <= 2212:
        return "ROOF"
    return "other"


def _nearest(n, cand, coords):
    x, y, z = coords[n]
    best, bd = None, COLUMN_MATCH_TOL
    for s in cand:
        if s == n:
            continue
        sx, sy, sz = coords[s]
        if abs(sz - z) > 1e-6:
            continue
        d = ((sx - x) ** 2 + (sy - y) ** 2) ** 0.5
        if d <= bd:
            bd, best = d, s
    return best


def _remove_orphans(lt2, master, supports):
    """Elimina nodos (no apoyo, no master, no esclavo de equalDOF) con 0 elementos."""
    used: Set[int] = set()
    for (n1, n2) in _elem_node_map().values():
        used.add(n1)
        used.add(n2)
    removed = 0
    for n in list(ops.getNodeTags()):
        if n in used or n in master or n in supports:
            continue
        try:
            ops.remove("node", n)
            removed += 1
        except Exception:
            pass
    return removed