"""Generador del modelo OpenSees LT2 (topologia).

Construye, en openseespy, la topologia del modelo desde los CSVs de LT2:
nodos estructurales, nodos master, apoyos, transformaciones geometricas y
diafragmas rfgidos. Solo lectura de data/; no define cargas, masas ni
analisis (fuera de alcance actual).

La geometria de vigas/columnas/muros (nodos, longitudes, orientaciones) se
valida siempre. La materializacion de elementos requiere propiedades
elasticas del hormigon definidas en data/materials_LT2.csv (columna E y
nu o G, en unidades consistentes con metros). Si el archivo no existe o le
faltan columnas, NO se inventan valores: se detiene la creacion de
elementos y el reporte indica exactamente el parametro faltante.

Ademas, los muros equivalentes de wall_segments_LT2.csv no tienen todavia
una idealizacion a elemento OpenSees decidida en el proyecto; se reporta
ese dato como pendiente.

Tags (enteros, reproducibles):
  nodos estructurales   1 .. N        (ordenados por z, x, y)
  nodos master          1001 .. 1005  (NM_L1..NM_ROOF)
  vigas                 2001 ..        (orden de beam_id)
  columnas              3001 ..        (orden de segment_id)
  transformaciones      1, 2, 3        (columnas, vigas X, vigas Y)
"""

from pathlib import Path
import pandas as pd
import openseespy.opensees as ops

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"
SECT = ROOT / "data" / "sections"
DEFAULT_MATERIALS = ROOT / "data" / "materials_LT2.csv"

NDM = 3
NDF = 6
TOL_NODE = 1e-6
TOL_LEN = 1e-6

TAG_MASTER_BASE = 1001
TAG_BEAM_BASE = 2001
TAG_COL_BASE = 3001
TAG_WALL_BASE = 4001
TAG_SECTION_BASE = 5001

TRANS_COL = 1
TRANS_B_X = 2
TRANS_B_Y = 3


def _key(x, y, z):
    return (round(x, 6), round(y, 6), round(z, 6))


def _zname(levels, name):
    return float(levels.loc[levels["name"] == name, "z_m"].iloc[0])


def rect_props(b, h):
    a = b * h
    iy = b * h ** 3 / 12.0
    iz = h * b ** 3 / 12.0
    return a, iy, iz


class ModelBuilder:
    def __init__(self, materials_path=DEFAULT_MATERIALS):
        self.levels = pd.read_csv(GEOM / "levels.csv")
        self.sections = pd.read_csv(SECT / "sections_LT2.csv")
        self.beams = pd.read_csv(GEOM / "beams_LT2.csv")
        self.columns = pd.read_csv(GEOM / "column_segments_LT2.csv")
        self.walls = pd.read_csv(GEOM / "wall_segments_LT2.csv")
        self.supports = pd.read_csv(GEOM / "supports_LT2.csv")
        self.masters = pd.read_csv(GEOM / "master_nodes_LT2.csv")
        self.diaphs = pd.read_csv(GEOM / "diaphragms_LT2.csv")
        self.materials_path = Path(materials_path)
        self._collect_nodes()
        self._collect_elements()
        self._expectations = None

    def _collect_nodes(self):
        keys = set()
        for r in self.beams.itertuples():
            z = _zname(self.levels, r.level)
            keys.add(_key(r.x1_m, r.y1_m, z))
            keys.add(_key(r.x2_m, r.y2_m, z))
        for r in self.columns.itertuples():
            z0 = _zname(self.levels, r.from_level)
            z1 = _zname(self.levels, r.to_level)
            keys.add(_key(r.x_m, r.y_m, z0))
            keys.add(_key(r.x_m, r.y_m, z1))
        for r in self.walls.itertuples():
            z0 = _zname(self.levels, r.from_level)
            z1 = _zname(self.levels, r.to_level)
            keys.add(_key(r.x1_m, r.y1_m, z0))
            keys.add(_key(r.x2_m, r.y2_m, z0))
            keys.add(_key(r.x1_m, r.y1_m, z1))
            keys.add(_key(r.x2_m, r.y2_m, z1))
        ordered = sorted(keys, key=lambda k: (k[2], k[0], k[1]))
        self.node_key_to_tag = {k: i + 1 for i, k in enumerate(ordered)}
        self.tag_to_key = {v: k for k, v in self.node_key_to_tag.items()}
        self.level_tags = {}
        for name in self.levels["name"]:
            z = round(_zname(self.levels, name), 6)
            self.level_tags[name] = [
                t for k, t in self.node_key_to_tag.items()
                if round(k[2], 6) == z
            ]
        self.structural_tags = sorted(self.node_key_to_tag.values())

    def _collect_elements(self):
        self.elems = {"beams": [], "columns": [], "walls": []}
        zl = _zname(self.levels, "B1")
        for r in self.beams.itertuples():
            z = _zname(self.levels, r.level)
            n1 = self.node_key_to_tag[_key(r.x1_m, r.y1_m, z)]
            n2 = self.node_key_to_tag[_key(r.x2_m, r.y2_m, z)]
            self.elems["beams"].append(dict(id=r.beam_id, n1=n1, n2=n2,
                                            level=r.level, section=r.section,
                                            length=((r.x2_m - r.x1_m) ** 2
                                                    + (r.y2_m - r.y1_m) ** 2) ** 0.5))
        for r in self.columns.itertuples():
            z0 = _zname(self.levels, r.from_level)
            z1 = _zname(self.levels, r.to_level)
            n1 = self.node_key_to_tag[_key(r.x_m, r.y_m, z0)]
            n2 = self.node_key_to_tag[_key(r.x_m, r.y_m, z1)]
            self.elems["columns"].append(dict(id=r.segment_id, n1=n1, n2=n2,
                                              section=r.section,
                                              length=abs(z1 - z0)))
        for r in self.walls.itertuples():
            z0 = _zname(self.levels, r.from_level)
            z1 = _zname(self.levels, r.to_level)
            n00 = self.node_key_to_tag[_key(r.x1_m, r.y1_m, z0)]
            n10 = self.node_key_to_tag[_key(r.x2_m, r.y2_m, z0)]
            n01 = self.node_key_to_tag[_key(r.x1_m, r.y1_m, z1)]
            n11 = self.node_key_to_tag[_key(r.x2_m, r.y2_m, z1)]
            self.elems["walls"].append(dict(
                id=r.segment_id, n00=n00, n10=n10, n01=n01, n11=n11,
                thickness=r.thickness_m,
                footprint=((r.x2_m - r.x1_m) ** 2
                           + (r.y2_m - r.y1_m) ** 2) ** 0.5,
                height=abs(z1 - z0)))

    def _load_materials(self):
        blockers = []
        mat = None
        if not self.materials_path.exists():
            blockers.append(
                "falta data/materials_LT2.csv con el modulo elastico (E) "
                "del hormigon; parametro necesario para materializar "
                "vigas/columnas elasticas")
            return None, blockers
        mat = pd.read_csv(self.materials_path)
        cols = set(mat.columns)
        missing = [c for c in ("E", "nu") if c not in cols]
        if missing:
            blockers.append(
                "data/materials_LT2.csv incompleto: faltan columnas "
                + ", ".join(missing))
            return None, blockers
        return mat, blockers

    def run(self):
        ops.wipe()
        ops.model("basic", "-ndm", NDM, "-ndf", NDF)
        self._build_nodes()
        support_tags = self._build_supports()
        self._build_masters()
        ops.constraints("Transformation")
        self._build_transf()
        self._build_diaphragms()
        blockers = []
        materials, mat_blockers = self._load_materials()
        blockers += mat_blockers
        mat_beams = 0
        mat_cols = 0
        mat_walls = 0
        if materials is not None and not mat_blockers:
            e = float(materials["E"].iloc[0])
            nu = float(materials["nu"].iloc[0])
            self._materialize(materials, e, nu)
            mat_beams = int(self.n_materialized.get("beams", 0))
            mat_cols = int(self.n_materialized.get("columns", 0))
            mat_walls = int(self.n_materialized.get("walls", 0))
        blockers.append(
            "muros: falta decidir la idealizacion del muro equivalente "
            "(wall_segments_LT2.csv -> elemento/section OpenSees)")
        report = self._report(support_tags, mat_beams, mat_cols, mat_walls,
                              blockers)
        self._expectations = report
        return report

    def _build_nodes(self):
        for tag in self.structural_tags:
            x, y, z = self.tag_to_key[tag]
            ops.node(tag, x, y, z)

    def _build_supports(self):
        z = _zname(self.levels, "B1")
        tags = []
        for r in self.supports.itertuples():
            tag = self.node_key_to_tag[_key(r.x_m, r.y_m, z)]
            ops.fix(tag, int(r.ux), int(r.uy), int(r.uz),
                    int(r.rx), int(r.ry), int(r.rz))
            tags.append(tag)
        return sorted(set(tags))

    def _build_masters(self):
        self.master_tag_by_id = {}
        self.master_tags = []
        for i, r in enumerate(self.masters.itertuples()):
            tag = TAG_MASTER_BASE + i
            ops.node(tag, r.x_m, r.y_m, r.z_m)
            ops.fix(tag, 0, 0, 1, 1, 1, 0)
            self.master_tag_by_id[r.master_id] = tag
            self.master_tags.append(tag)

    def _build_transf(self):
        ops.geomTransf("Linear", TRANS_COL, 0, 1, 0)
        ops.geomTransf("Linear", TRANS_B_X, 0, 0, 1)
        ops.geomTransf("Linear", TRANS_B_Y, 0, 0, 1)

    def _build_diaphragms(self):
        self.diaph_slaves = {}
        self.diaph_masters = {}
        for r in self.diaphs.itertuples():
            master = self.master_tag_by_id[r.master_id]
            slaves = [t for t in self.level_tags[r.level]
                      if t != master]
            ops.rigidDiaphragm(3, master, *slaves)
            self.diaph_slaves[r.level] = len(slaves)
            self.diaph_masters[r.level] = master

    def _orient(self, e):
        k1, k2 = self.tag_to_key[e["n1"]], self.tag_to_key[e["n2"]]
        dx = k2[0] - k1[0]
        dy = k2[1] - k1[1]
        dz = k2[2] - k1[2]
        if abs(dz) > TOL_NODE and abs(dx) <= TOL_NODE and abs(dy) <= TOL_NODE:
            return TRANS_COL
        if abs(dy) <= TOL_NODE and abs(dx) > TOL_NODE and abs(dz) <= TOL_NODE:
            return TRANS_B_X
        if abs(dx) <= TOL_NODE and abs(dy) > TOL_NODE and abs(dz) <= TOL_NODE:
            return TRANS_B_Y
        return None

    def _materialize(self, materials, e, nu):
        self.n_materialized = {"beams": 0, "columns": 0, "walls": 0}
        g = e / (2.0 * (1.0 + nu))
        section_tag = {}
        for _, s in self.sections.iterrows():
            b = float(s["b_m"])
            h = float(s["h_m"])
            a, iy, iz = rect_props(b, h)
            j = _jrect(min(b, h), max(b, h))
            tag = TAG_SECTION_BASE + len(section_tag)
            ops.section("Elastic", tag, e, a, iz, iy, g, j)
            section_tag[str(s["section_id"])] = tag
        for i, e_ in enumerate(self.elems["beams"]):
            transf = self._orient(e_)
            if transf is None:
                continue
            ops.element("elasticBeamColumn", TAG_BEAM_BASE + i, e_["n1"],
                        e_["n2"], section_tag[e_["section"]], transf)
            self.n_materialized["beams"] += 1
        for i, e_ in enumerate(self.elems["columns"]):
            ops.element("elasticBeamColumn", TAG_COL_BASE + i, e_["n1"],
                        e_["n2"], section_tag[e_["section"]], TRANS_COL)
            self.n_materialized["columns"] += 1

    def _report(self, support_tags, mat_beams, mat_cols, mat_walls, blockers):
        expected = {
            "beams": len(self.elems["beams"]),
            "columns": len(self.elems["columns"]),
            "walls": len(self.elems["walls"]),
            "supports": len(self.supports),
            "masters": len(self.masters),
            "diaphragms": len(self.diaphs),
            "structural_nodes": len(self.structural_tags),
            "total_nodes": len(self.structural_tags) + len(self.masters),
        }
        actual = {
            "beams": mat_beams,
            "columns": mat_cols,
            "walls": mat_walls,
            "supports": len(support_tags),
            "masters": len(self.master_tags),
            "diaphragms": len(self.diaph_slaves),
            "structural_nodes": len(ops.getNodeTags()) - len(self.master_tags),
            "total_nodes": len(ops.getNodeTags()),
        }
        return {
            "expected": expected,
            "actual": actual,
            "blockers": blockers,
            "slaves_per_level": self.diaph_slaves,
            "level_node_counts": {k: len(v) for k, v in self.level_tags.items()},
            "support_tags": support_tags,
            "materialized": {"beams": mat_beams, "columns": mat_cols,
                             "walls": mat_walls},
        }


def _jrect(b, h):
    if b > h:
        b, h = h, b
    return h * b ** 3 / 3.0 * (1 - 0.63 * (b / h) + 0.052 * (b / h) ** 5)