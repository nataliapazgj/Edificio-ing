"""Diafragmas combinados: un unico rigidDiaphragm por nivel comun.

Reglas (aprobadas):
  - NO se conservan dos rigidDiaphragm independientes por nivel comun.
  - Master = master LT2 (L2->1002, L3->1003, L4->1004, ROOF->1005).
  - Slaves = todos los nodos de ese z de LT2 + todos los nodos de ese z de LT1
    (offset / compartidos), excluyendo el master y sin duplicados.
  - Se preserva tambien el diafragma LT2 del nivel L1 (z=-4.01) para no
    desestabilizar LT2 en su piso no compartido.
  - Cada nodo aparece como slave una sola vez; el master no entra en slaves.
"""

from __future__ import annotations

import openseespy.opensees as ops

from . import config as C
from .lt2_builder_wrapper import LT2Model
from .lt1_builder_combined import build_ops_model_combined


def _floor_nodes_at_z(lt2: LT2Model, lt1_summary, z, tol=1e-6):
    """Nodos de LT2 y LT1 en el plano z (fusionados, sin duplicados)."""
    out = set()
    # LT2: usar tag_to_key (solo nodos que siguen existiendo)
    existing = set(ops.getNodeTags())
    exclude = set(getattr(lt2, "diaph_exclude", set()) or set())
    lt2_tags = []
    for t, (x, y, zz) in lt2.tag_to_key.items():
        if t not in existing or t in exclude:
            continue
        if abs(zz - z) < tol:
            lt2_tags.append(t)
    out.update(lt2_tags)
    # LT1: nivel_joint_tags -> tags offset (+ interfaz LT2 tags)
    for lvl, tags in lt1_summary["level_joint_tags"].items():
        # encontrar z de ese nivel
        keys = lt1_summary["level_joint_tags"][lvl]
        if keys:
            zz = ops.nodeCoord(tags[0])[2]
            if abs(zz - z) < tol:
                out.update(tags)
    return out


def build_diaphragms(lt2: LT2Model, lt1_summary):
    """Crea los rigidDiaphragm combinados. Devuelve dict nivel->info."""
    created = {}
    # Niveles LT2 a preservar (L1..ROOF)
    for lvl in C.LT2_LEVELS:
        master = None
        # master LT2 por nivel
        for mid, tag in lt2.master_by_level.items():
            lvl_name = mid.replace("NM_", "")
            if lvl_name == lvl:
                master = tag
                break
        if master is None:
            continue
        z = C.COMMON_LEVELS[lvl]["z"] if lvl in C.COMMON_LEVELS else \
            float(lt2.builder.levels.loc[
                lt2.builder.levels["name"] == lvl, "z_m"].iloc[0])
        slaves = _floor_nodes_at_z(lt2, lt1_summary, z)
        slaves.discard(master)
        slave_list = sorted(slaves)
        if slave_list:
            ops.rigidDiaphragm(3, master, *slave_list)
        created[lvl] = {"master": master, "z": z, "n_slaves": len(slave_list),
                        "combined": lvl in C.COMMON_LEVELS}
    return created