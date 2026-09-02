"""Entorno LT2 en la instancia combinada.

Reutiliza `build_opensees_model.ModelBuilder` SIN modificar el archivo.
`ModelBuilder.__init__` solo lee CSVs (sin efectos sobre `ops`).
La construccion real de nodos/elementos ocurre en los metodos privados
(no llaman a ops.wipe()); solo `ModelBuilder.run()` llama a ops.wipe(), y
deliberadamente NO se invoca aqui.

Se construye LT2 en el orden exacto de `run()` (minus wipe/model), y se
OMITE la creacion de diafragmas LT2 en este paso (el orquestador creara los
diafragmas combinados). Los masters y apoyos de LT2 se conservan intactos.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops  # noqa: E402
from build_opensees_model import ModelBuilder  # noqa: E402


class LT2Model:
    """Builder LT2 reutilizado sin wipe; expone lo que necesita el combinado."""

    def __init__(self):
        self.builder = ModelBuilder()   # solo lectura CSVs
        self.beam_tags = None
        self.col_tags = None
        self.support_tags = None
        self.master_tags = None
        self.master_by_level = {}
        self.diaph_skipped = False

    def build(self, skip_diaphragms=True):
        b = self.builder
        b._build_nodes()                 # nodos estructurales 1..272
        b._build_supports()              # apoyos (fix) en B1
        b._build_masters()               # masters 1001..1005
        ops.constraints("Transformation")
        b._build_transf()                # transforms LT2 1,2,3
        if not skip_diaphragms:
            b._build_diaphragms()        # diafragmas LT2 (no usados en combinado)
        # materializacion de vigas/columnas (muros pendientes en LT2)
        mats, blockers = b._load_materials()
        if mats is None or blockers:
            raise RuntimeError(
                "LT2: no se pudieron cargar materiales elasticos (" +
                "; ".join(blockers) + ")")
        e = float(mats["E_kN_m2"].iloc[0])
        nu = float(mats["nu"].iloc[0])
        b._materialize(mats, e, nu)
        self.beam_tags = [t for t in ops.getEleTags() if t >= 2001 and t < 3001]
        self.col_tags = [t for t in ops.getEleTags() if t >= 3001]
        self.support_tags = sorted([t for t in b._expectations["support_tags"]]
                                   if getattr(b, "_expectations", None)
                                   else b.node_key_to_tag.values())
        # support tags reales: recogidos en _build_supports no almacenados;
        # se derivan de los apoyos ya aplicados via b._build_supports (fix B1)
        base_z = float(b.levels.loc[b.levels["name"] == "B1", "z_m"].iloc[0])
        self.support_tags = sorted(
            t for t in b.node_key_to_tag.values()
            if abs(b.tag_to_key[t][2] - base_z) < 1e-6)
        self.master_tags = b.master_tags
        self.master_by_level = {
            r.master_id: b.master_tag_by_id[r.master_id]
            for r in b.masters.itertuples()}
        self.master_tag_by_id = dict(b.master_tag_by_id)
        self.level_tags = b.level_tags
        self.tag_to_key = b.tag_to_key
        self.node_key_to_tag = b.node_key_to_tag
        self.diaph_skipped = skip_diaphragms
        return self

    def node_tag_at(self, x, y, z):
        from build_opensees_model import _key
        return self.builder.node_key_to_tag.get(_key(x, y, z))