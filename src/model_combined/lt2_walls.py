"""Materializacion de los muros M.H.A. de LT2 (M001-M008) como COLUMNAS.

Convencion del profesor:
    "Los muros se modelan COMO COLUMNAS en OpenSees."

Cada muro se digitalizo en 40 tramos verticales (wall_segments_LT2.csv), cada
tramo es un panel entre dos niveles consecutivos con 4 esquinas:
    n00, n10  (inferiores) ; n01, n11  (superiores)      [tags LT2]

Representacion elegida (usa SOLO datos reales del proyecto):
  - Cada tramo de muro se modela con DOS elementos verticales
    `elasticBeamColumn` en sus dos bordes verticales: (n00->n01) y (n10->n11).
    Es el unico modo de conectar las 4 esquinas del panel (dos elementos
    colineares verticales) y deja conectados todos los nodos de espesor.
  - El tramo (piso) del muro no es colineal en planta (tiene una huella
    horizontal length L = footprint), por lo que NO existe un single eje
    vertical que una ambas esquinas; se modela como par de bordes verticales.
  - Seccion equivalente del muro: rectangulo real  (t espesor) x (L huella):
        A  = t * L
        Iy = t * L**3 / 12      (rigidez fuerte, eje en el plano del muro)
        Iz = L * t**3 / 12
        J  = _jrect(t, L)       (misma formula de torsion que el proyecto)
  - Material real: CONC_G25, E = 23.5 GPa (materials_LT2.csv)
        E = 23_500_000 kN/m2 , nu = 0.20
        G = E / (2 * (1 + nu)) = 9_791_666.67 kN/m2
  - Cada elemento usa el mismo geomTransf de columnas de LT2 (TRANS_COL = 1,
    vector (0,1,0)), porque el eje del elemento es vertical.

Las secciones se crean como `ops.section("Elastic", ...)` con la MISMA
convencion/orden de argumentos que usa `build_opensees_model._materialize`
para vigas/columnas de LT2. Los tags de seccion (base WALL_SECTION_BASE) y de
elemento (base WALL_ELEM_BASE) NO colisionan con los de LT2 (vigas 2001+,
columnas 3001+, secciones 5001+) ni con LT1 (>= 1_000_000).

NO se anade peso propio de los muros como carga: el modelo LT2 (benchmark) solo
aplica cargas de losa (areas tributarias) via eleLoad, y los elementos de
vigas/columnas tampoco llevan self-weight explicito. Los muros aportan
RIGIDEZ (como columnas), no carga nueva.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

import openseespy.opensees as ops  # noqa: E402

from build_opensees_model import rect_props, _jrect, TRANS_COL  # noqa: E402

WALL_ELEM_BASE = 4001          # tags de los elementos muro-columna LT2
WALL_SECTION_BASE = 8001       # tags de las secciones de los muros-columna

# Material CONC_G25 (data/materials_LT2.csv)
E_KN_M2 = 23_500_000.0
NU = 0.20
G_KN_M2 = E_KN_M2 / (2.0 * (1.0 + NU))


@dataclass
class WallColumn:
    wall_id: str
    segment_id: str
    tag: int
    ni: int
    nj: int
    thickness: float
    footprint: float
    height: float
    section_tag: int
    level_i: str
    level_j: str


def _level_of_z(lt2, z):
    """Nombre de nivel LT2 al que pertenece un z (tol 1e-6)."""
    for _, r in lt2.builder.levels.iterrows():
        if abs(float(r["z_m"]) - z) < 1e-6:
            return str(r["name"])
    return None


def _section_for(t, L, existing):
    """Devuelve tag de seccion para (espesor, huella), creandola si falta."""
    key = (round(float(t), 6), round(float(L), 6))
    if key in existing:
        return existing[key]
    a, iy, iz = rect_props(t, L)
    j = _jrect(min(t, L), max(t, L))
    tag = WALL_SECTION_BASE + len(existing)
    # mismo orden de argumentos que _materialize: (tag, E, A, Iz, Iy, G, J)
    ops.section("Elastic", tag, E_KN_M2, a, iz, iy, G_KN_M2, j)
    existing[key] = tag
    return tag


def materialize_lt2_walls(lt2):
    """Crea los muros-columna LT2 en la instancia actual.

    `lt2` = LT2Model ya construido (transform 1 = TRANS_COL disponible).
    Devuelve dict con conjuntos/contadores para reporte y verificacion.
    """
    walls = lt2.builder.elems["walls"]
    sections = {}
    elements = []
    for seg in walls:
        t = float(seg["thickness"])
        L = float(seg["footprint"])
        h = float(seg["height"])
        st = _section_for(t, L, sections)
        n00, n10, n01, n11 = seg["n00"], seg["n10"], seg["n01"], seg["n11"]
        # dos bordes verticales
        for (ni, nj) in ((n00, n01), (n10, n11)):
            tag = WALL_ELEM_BASE + len(elements)
            ops.element("elasticBeamColumn", tag, ni, nj, st, TRANS_COL)
            z_i = lt2.tag_to_key[ni][2]
            z_j = lt2.tag_to_key[nj][2]
            elements.append(WallColumn(
                wall_id=seg["id"].split("_")[0],
                segment_id=seg["id"],
                tag=tag, ni=ni, nj=nj,
                thickness=t, footprint=L, height=h,
                section_tag=st,
                level_i=_level_of_z(lt2, z_i),
                level_j=_level_of_z(lt2, z_j)))

    # agrupar por muro
    by_wall = {}
    for e in elements:
        by_wall.setdefault(e.wall_id, []).append(e)

    # nodos que eran huerfanos (0 elementos) antes y ahora conectados
    conn_before = {t: 0 for t in lt2.builder.structural_tags}
    for e_ in lt2.builder.elems["beams"]:
        conn_before[e_["n1"]] = conn_before.get(e_["n1"], 0) + 1
        conn_before[e_["n2"]] = conn_before.get(e_["n2"], 0) + 1
    for e_ in lt2.builder.elems["columns"]:
        conn_before[e_["n1"]] = conn_before.get(e_["n1"], 0) + 1
        conn_before[e_["n2"]] = conn_before.get(e_["n2"], 0) + 1
    orphan_before = [t for t, c in conn_before.items() if c == 0]

    n_connected = 0
    for e in elements:
        if conn_before.get(e.ni, 0) == 0:
            n_connected += 1
        if conn_before.get(e.nj, 0) == 0:
            n_connected += 1

    return {
        "elements": elements,
        "by_wall": by_wall,
        "n_elements": len(elements),          # = 80
        "n_segments": len(walls),             # = 40 (8 muros x 5 tramos)
        "n_walls": len(by_wall),              # = 8
        "n_sections": len(sections),
        "sections": {k: v for k, v in sections.items()},
        "orphans_before": len(orphan_before),
        "orphan_nodes_now_connected": n_connected,
        "wall_ids": sorted(by_wall.keys()),
    }


def wall_stats_for_report(lt2, mat):
    """Tabla M001..M008: orientacion, L, t, niveles, tramos, seccion."""
    by_wall = mat["by_wall"]
    rows = []
    for wid in mat["wall_ids"]:
        elems = by_wall[wid]
        seg = elems[0]
        # niveles del primer y ultimo elemento del muro
        segs = [e for e in lt2.builder.elems["walls"] if e["id"].startswith(wid)]
        z_bot = lt2.tag_to_key[segs[0]["n00"]][2]
        z_top = lt2.tag_to_key[segs[-1]["n01"]][2]
        rows.append({
            "wall_id": wid,
            "n_segments": len(segs),
            "thickness_m": seg.thickness,
            "footprint_m": seg.footprint,
            "height_seg_m": seg.height,
            "n_elements": len(elems),
            "levels_from": _level_of_z(lt2, z_bot),
            "levels_to": _level_of_z(lt2, z_top),
            "section_tag": seg.section_tag,
            "A_m2": round(rect_props(seg.thickness, seg.footprint)[0], 6),
            "Iy_m4": round(rect_props(seg.thickness, seg.footprint)[1], 8),
            "Iz_m4": round(rect_props(seg.thickness, seg.footprint)[2], 8),
            "J_m4": round(_jrect(min(seg.thickness, seg.footprint),
                                 max(seg.thickness, seg.footprint)), 8),
            "orientation": "vertical (bordes VERTICALES: ndices ejes)",
        })
    return rows