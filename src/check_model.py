"""
Check rapido del modelo v2: construye, verifica (7 controles) y corre un
analisis de gravedad (peso propio) solo para reportar convergencia.

Uso: python src/check_model.py
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops
from ops_model import load_aligned, build_ops_model, verify_model
from structure_params import (
    E, GAMMA_CONCRETE,
    COL_A, BEAM_A, WALL_THICKNESS, WALL_H_DEFAULT,
    SYSTEM, NUMBERER, CONSTRAINTS, ALGORITHM, INTEGRATOR_STEP, NUM_STEPS,
)


def main():
    data = load_aligned()
    summary = build_ops_model(data)
    checks = verify_model(summary, data)

    # Carga minima para convergencia: peso propio (half en cada extremo)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    nodal = {}
    for e in summary["col_elements"]:
        p = COL_A * e["length"] * GAMMA_CONCRETE / 2.0
        nodal[e["ni"]] = nodal.get(e["ni"], 0.0) + p
        nodal[e["nj"]] = nodal.get(e["nj"], 0.0) + p
    for e in summary["beam_elements"]:
        p = BEAM_A * e["length"] * GAMMA_CONCRETE / 2.0
        nodal[e["ni"]] = nodal.get(e["ni"], 0.0) + p
        nodal[e["nj"]] = nodal.get(e["nj"], 0.0) + p
    for e in summary["wall_elements"]:
        p = WALL_THICKNESS * WALL_H_DEFAULT * e["length"] * GAMMA_CONCRETE / 2.0
        nodal[e["ni"]] = nodal.get(e["ni"], 0.0) + p
        nodal[e["nj"]] = nodal.get(e["nj"], 0.0) + p
    for tag, p in nodal.items():
        ops.load(tag, 0, 0, -p, 0, 0, 0)

    ops.system(SYSTEM)
    ops.numberer(NUMBERER)
    ops.constraints(CONSTRAINTS)
    ops.algorithm(ALGORITHM)
    ops.integrator("LoadControl", INTEGRATOR_STEP)
    ops.analysis("Static")
    ok = ops.analyze(NUM_STEPS)
    checks["convergencia"] = ("OK" if ok == 0 else "FALLO", f"analyze retcode={ok}")

    # Full denominators (including levels fuera de pórtico)
    hb_all = [b for b in data["beams"] if b["status"] == "high-confidence"]
    hw_all = [w for w in data["walls"] if w["status"] == "high-confidence"]
    frame_set = ("P1", "P2", "P3", "P4")
    in_frame_b = sum(v for k, v in summary["n_hi_beams"].items())
    in_frame_w = sum(v for k, v in summary["n_hi_walls"].items())
    nb = len(summary["included_beams"])
    nw = len(summary["included_walls"])
    s1fdn_b = len([b for b in hb_all if b["level"] not in frame_set])
    s1fdn_w = len([w for w in hw_all if w["level"] not in frame_set])

    print("=" * 60)
    print("MODELO v2 - resumen")
    print("=" * 60)
    print(f"nodos={summary['n_nodes']} elementos={summary['n_elements']} "
          f"columnas={summary['n_columns']} vigas={summary['n_beams']} "
          f"muros={summary['n_walls']}")
    print(f"alta confianza: vigas={nb}/{in_frame_b} en PT; muros={nw}/{in_frame_w} en PT")
    print(f"  (totales hi: vigas={len(hb_all)}/184, muros={len(hw_all)}/58; "
          f"S1+FDN sin columnas: vigas={s1fdn_b}, muros={s1fdn_w})")

    # Listar elementos excluidos (>DIST_ANCHOR de todo pilar soportado)
    ex_b = [(b["level"], i) for b in hb_all for i in range(len([x for x in hb_all if x["level"]==b["level"]]))
            if b["level"] in frame_set and (b["level"], i) not in summary["included_beams"]]
    # re-count properly
    excl_b = []
    excl_w = []
    solo_carga_b = []
    solo_carga_w = []
    for lvl in frame_set:
        bl = [b for b in hb_all if b["level"] == lvl]
        for i, b in enumerate(bl):
            if (lvl, i) not in summary["included_beams"]:
                excl_b.append(b)
            elif not summary["included_beams"].get((lvl, i)):
                solo_carga_b.append(b)
        wl = [w for w in hw_all if w["level"] == lvl]
        w_off = len(bl)            # claves de muro: (lvl, n_beams + j)
        for j, w in enumerate(wl):
            if (lvl, w_off + j) not in summary["included_walls"]:
                excl_w.append(w)
            elif not summary["included_walls"].get((lvl, w_off + j)):
                solo_carga_w.append(w)
    if excl_b or excl_w:
        print("  Excluidos (>8.0 m de pilar soportado, no conectables):")
        for b in excl_b:
            print(f"    viga  {b['level']}  ({b['x1']:.1f},{b['y1']:.1f})-({b['x2']:.1f},{b['y2']:.1f})  L={b['length_m']:.2f} m")
        for w in excl_w:
            print(f"    muro  {w['level']}  ({w['x1']:.1f},{w['y1']:.1f})-({w['x2']:.1f},{w['y2']:.1f})  L={w['length_m']:.2f} m")
    if solo_carga_b or solo_carga_w:
        print(f"  Solo carga (sin rigidez FE, peso a vigas reales proximas): "
              f"{len(solo_carga_b)} vigas, {len(solo_carga_w)} muros")
    verdicts = {"OK": 0, "WARNING": 0, "FALLO": 0}
    for k, (st, dt) in checks.items():
        verdicts[st] = verdicts.get(st, 0) + 1
        print(f"  [{st}] {k}: {dt}")
    overall = ("PASS" if verdicts.get("FALLO", 0) == 0 and verdicts.get("WARNING", 0) == 0
               else "WARNING" if verdicts.get("FALLO", 0) == 0
               else "FAIL")
    print(f"VEREDICTO GLOBAL: {overall}")
    return overall


if __name__ == "__main__":
    sys.exit(0 if main() != "FAIL" else 1)