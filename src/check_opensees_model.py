"""Chequeo del modelo OpenSees LT2 (solo lectura).

Construye el modelo con build_opensees_model.ModelBuilder y verifica que
OpenSees reproduzca la fuente de datos (CSVs de LT2):

  - conteo de nodos estructurales, masters y totales;
  - apoyos (22 empotrados en B1) y su mapeo a nodos;
  - vigas, columnas, muros y total de elementos (esperado vs materializado);
  - duplicados de tags y de nodos;
  - elementos de longitud nula;
  - elementos con nodos inexistentes;
  - nodos aislados (estructurales y masters intencionalmente aislados);
  - diafragmas: cantidad, master y esclavos por nivel;
  - orientacion de transformaciones geometricas.

Exit code 0 solo si OpenSees reproduce la fuente de datos sin bloqueadores;
si falta material (u otro dato) no se inventan valores y el chequeo falla
reportando exactamente que falta.
"""

import sys
from pathlib import Path
import openseespy.opensees as ops

from build_opensees_model import (
    ModelBuilder, TRANS_COL, TRANS_B_X, TRANS_B_Y, TOL_LEN, TOL_NODE,
    GEOM, SECT,
)
import pandas as pd

RED = "\033[91m"
GREEN = "\033[92m"
END = "\033[0m"


def main():
    ok = True
    builder = ModelBuilder()
    report = builder.run()

    def check(name, cond, detail):
        nonlocal ok
        if cond:
            print(f"  [OK] {name} {detail}")
        else:
            ok = False
            print(f"  [{RED}FAIL{END}] {name} {detail}")

    print("=== OPENSEES MODEL CHECK ===")
    exp = report["expected"]
    act = report["actual"]

    print("[Counts]")
    for k in ("structural_nodes", "total_nodes", "masters", "supports",
              "diaphragms"):
        check(f"{k}", act[k] == exp[k],
              f"(got {act[k]}, expected {exp[k]})")
    for k in ("beams", "columns", "walls"):
        check(f"{k}", act[k] == exp[k],
              f"(got {act[k]}, expected {exp[k]})")
    tot_exp = exp["beams"] + exp["columns"] + exp["walls"]
    tot_act = act["beams"] + act["columns"] + act["walls"]
    check("total_elements", tot_act == tot_exp,
          f"(got {tot_act}, expected {tot_exp})")

    print("[Master nodes]")
    masters_csv = pd.read_csv(GEOM / "master_nodes_LT2.csv")
    for r in masters_csv.itertuples():
        tag = builder.master_tag_by_id[r.master_id]
        x, y, z = ops.nodeCoord(tag)
        check(f"master {r.master_id} coords",
              (abs(x - r.x_m) < TOL_NODE and abs(y - r.y_m) < TOL_NODE
               and abs(z - r.z_m) < TOL_NODE),
              f"(tag {tag})")

    print("[Tags/nodos]")
    tags = builder.structural_tags + builder.master_tags
    check("tags unicos/duplicados", len(set(tags)) == len(tags), "")
    check("nodos no duplicados",
          len(builder.node_key_to_tag) == len(builder.structural_tags), "")
    check("nodos aislados estructurales",
          len(_isolated(builder)) == 0,
          f"(isolados: {sorted(_isolated(builder))})")
    mast_in_elems = set(builder.master_tags) & _all_element_tags(builder)
    check("masters sin elementos (intencional)", len(mast_in_elems) == 0,
          f"(masters en elementos: {sorted(mast_in_elems)})")

    print("[Element topologia]")
    for kind in ("beams", "columns"):
        nz = [e["id"] for e in builder.elems[kind]
              if e["length"] <= TOL_LEN]
        check(f"longitud nula en {kind}", len(nz) == 0, f"(ids: {nz})")
        bad = [e["id"] for e in builder.elems[kind]
               if e["n1"] not in ops.getNodeTags()
               or e["n2"] not in ops.getNodeTags()]
        check(f"nodos inexistentes en {kind}", len(bad) == 0, f"(ids: {bad})")
    bad = []
    nullf = []
    warped = []
    for e in builder.elems["walls"]:
        nodes = {e["n00"], e["n10"], e["n01"], e["n11"]}
        if not nodes.issubset(set(ops.getNodeTags())):
            bad.append(e["id"])
        if e["footprint"] <= TOL_LEN or e["height"] <= TOL_LEN:
            nullf.append(e["id"])
        k00 = builder.tag_to_key[e["n00"]]
        k10 = builder.tag_to_key[e["n10"]]
        k01 = builder.tag_to_key[e["n01"]]
        k11 = builder.tag_to_key[e["n11"]]
        if k00[0] != k01[0] or k00[1] != k01[1] \
                or k10[0] != k11[0] or k10[1] != k11[1]:
            warped.append(e["id"])
    check("nodos inexistentes en walls", len(bad) == 0, f"(ids: {bad})")
    check("area nula en walls", len(nullf) == 0, f"(ids: {nullf})")
    check("huella congruente en walls", len(warped) == 0, f"(ids: {warped})")

    print("[Orientacion geomTransf]")
    refs = {TRANS_COL: (0, 1, 0), TRANS_B_X: (0, 0, 1),
            TRANS_B_Y: (0, 0, 1)}
    for kind, expected_axes in (("beams", ((1, 0, 0), (0, 1, 0))),
                                ("columns", ((0, 0, 1),))):
        ok_orient = True
        for e in builder.elems[kind]:
            transf = builder._orient(e)
            if transf is None:
                ok_orient = False
                print(f"    [FAIL] {kind} {e['id']} no clasificable")
                continue
            vx = refs[transf]
            k1 = builder.tag_to_key[e["n1"]]
            k2 = builder.tag_to_key[e["n2"]]
            axis = (k2[0] - k1[0], k2[1] - k1[1], k2[2] - k1[2])
            norm = (axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2) ** 0.5
            if norm <= TOL_NODE:
                ok_orient = False
                continue
            dot = (vx[0] * axis[0] + vx[1] * axis[1] + vx[2] * axis[2]) / norm
            ok_axis = any(
                all(abs(axis[i] / norm - a) < 1e-6
                    for i, a in enumerate(aa))
                for aa in expected_axes)
            if abs(dot) > 1e-6 or not ok_axis:
                ok_orient = False
                print(f"    [FAIL] {kind} {e['id']} transf {transf}")
        check(f"orientacion {kind}", ok_orient, f"(transf {kind})")

    print("[Diafragmas]")
    diaphs_csv = pd.read_csv(GEOM / "diaphragms_LT2.csv")
    for r in diaphs_csv.itertuples():
        got = builder.diaph_slaves[r.level]
        check(f"slaves {r.level}",
              got == int(r.slave_count),
              f"(got {got}, expected {r.slave_count})")

    print("[Material / datos faltantes]")
    for b in report["blockers"]:
        print(f"  [BLOCK] {b}")

    print("[Conteos por nivel]")
    for k, v in report["level_node_counts"].items():
        print(f"  nivel {k}: {v} nodos estructurales")

    print("[Resumen]")
    print(f"  vigas materializadas      : {act['beams']}/{exp['beams']}")
    print(f"  columnas materializadas   : {act['columns']}/{exp['columns']}")
    print(f"  muros materializados      : {act['walls']}/{exp['walls']}")
    print(f"  nodos max tag             : {max(ops.getNodeTags())}")

    if not ok:
        print(f"{RED}FALLO: OpenSees no reproduce la fuente de datos{END}")
        sys.exit(1)
    print(f"{GREEN}OK{END}: OpenSees reproduce la fuente de datos")
    sys.exit(0)


def _all_element_tags(builder):
    out = set()
    for e in builder.elems["beams"]:
        out.update((e["n1"], e["n2"]))
    for e in builder.elems["columns"]:
        out.update((e["n1"], e["n2"]))
    for e in builder.elems["walls"]:
        out.update((e["n00"], e["n10"], e["n01"], e["n11"]))
    return out


def _isolated(builder):
    used = _all_element_tags(builder)
    return sorted(set(builder.structural_tags) - used)


if __name__ == "__main__":
    main()