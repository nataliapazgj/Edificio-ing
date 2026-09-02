"""
Cargas de gravedad y analisis estatico lineal (modelo v2).

Componentes (sin duplicar losa):
  A. peso propio de vigas
  B. peso propio de columnas
  C. peso propio de muros equivalentes
  D. q_G de losa transferido a las vigas receptoras (areas tributarias con
     poligono explicito; la losa NO se modela FE).

Cada carga de elemento se aplica como media carga puntual en cada extremo.
El peso propio de la losa NO se modela como masa de elemento: entra solo via D.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops
from structure_params import (
    GAMMA_CONCRETE,
    COL_A, BEAM_A, WALL_THICKNESS, WALL_H_DEFAULT,
    SYSTEM, NUMBERER, CONSTRAINTS, ALGORITHM, INTEGRATOR_STEP, NUM_STEPS,
)
from ops_model import load_aligned, build_ops_model
from tributary import compute_tributary


def self_weight_elements(summary):
    """Peso propio (kN) por elemento: columnas, vigas, muros."""
    parts = {"columns": {}, "beams": {}, "walls": {}}
    totals = {"columns": 0.0, "beams": 0.0, "walls": 0.0}
    for c in summary["col_elements"]:
        V = COL_A * c["length"]
        totals["columns"] += V * GAMMA_CONCRETE
    for b in summary["beam_elements"]:
        V = BEAM_A * b["length"]
        totals["beams"] += V * GAMMA_CONCRETE
    for m in summary["wall_elements"]:
        V = WALL_THICKNESS * WALL_H_DEFAULT * m["length"]
        totals["walls"] += V * GAMMA_CONCRETE
    return parts, totals


def apply_gravity(summary, trib_out):
    """
    Aplica cargas puntuales -Z:
      - mitad del peso propio de cada elemento en cada extremo (A+B+C);
      - q_G * area tributaria por viga receptora, mitad en cada extremo (D).
    Devuelve (nodal_load, totales) con totales desglosados.
    """
    nodal = {}
    totals = {"self": 0.0, "slab": 0.0, "total": 0.0,
              "self_cols": 0.0, "self_beams": 0.0, "self_walls": 0.0}

    def add(tag, p):
        nodal[tag] = nodal.get(tag, 0.0) + p

    # A+B+C self weight
    for e in summary["col_elements"]:
        p = COL_A * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_cols"] += 2 * p
    for e in summary["beam_elements"]:
        p = BEAM_A * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_beams"] += 2 * p
    for e in summary["wall_elements"]:
        p = WALL_THICKNESS * WALL_H_DEFAULT * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_walls"] += 2 * p

    # C-ter: muros/vigas "solo carga" (sin elementos FE). Su peso propio se
    # transfiere a las VIGAS REALES mas proximas del mismo nivel (3 puntos:
    # extremo inicial, centro, extremo final). La geometria queda trazada en
    # summary["load_only_members"] (Unity/trazabilidad) y el total de peso
    # propio del conjunto no varia respecto al modelo completo de miembros.
    beam_level_nodes = {}
    for e in summary["beam_elements"]:
        beam_level_nodes.setdefault(e["level"], []).append(e)
    for _k, m in summary.get("load_only_members", {}).items():
        A_ref = (WALL_H_DEFAULT * WALL_THICKNESS) if m["kind"] == "wall" else BEAM_A
        W = A_ref * m["length_m"] * GAMMA_CONCRETE
        beams_lvl = beam_level_nodes.get(m["level"], [])
        if not beams_lvl:
            continue
        q = W / 3.0
        pts = [(m["x1"], m["y1"]),
               (0.5 * (m["x1"] + m["x2"]), 0.5 * (m["y1"] + m["y2"])),
               (m["x2"], m["y2"])]
        for px, py in pts:
            best, bd = None, 1e30
            for e in beams_lvl:
                for nid in (e["ni"], e["nj"]):
                    nx, ny, _ = ops.nodeCoord(nid)
                    d = math.hypot(px - nx, py - ny)
                    if d < bd:
                        bd, best = d, nid
            if best is not None:
                add(best, q)
                totals["self"] += q
                if m["kind"] == "wall":
                    totals["self_walls"] += q
                else:
                    totals["self_beams"] += q

    # D slab q_G -> beams
    tag2ele = {e["tag"]: e for e in summary["beam_elements"]}
    for tag, p in trib_out["beam_load"].items():
        e = tag2ele.get(tag)
        if e is None:
            continue
        add(e["ni"], p / 2.0); add(e["nj"], p / 2.0)
        totals["slab"] += p

    # D-ter: carga de LOSA de las vigas "solo carga" (sus elementos no existen
    # en el FE, por lo que su area tributaria quedaba sin vehiculo). Se
    # transfiere a las vigas reales mas proximas del mismo nivel, igual que su
    # peso propio. (Las areas y A_trib de tributary.py no se alteran.)
    if summary.get("load_only_members"):
        rec_by_orig = {(lvl, r["orig"]): r for lvl, recs in trib_out["receivers"].items()
                       for r in recs}
        for k, m in summary["load_only_members"].items():
            if m["kind"] != "beam":
                continue
            rec = rec_by_orig.get((m["level"], k[1]))
            if rec is None or rec["slab_load_kN"] <= 0:
                continue
            beams_lvl = beam_level_nodes.get(m["level"], [])
            if not beams_lvl:
                continue
            q = rec["slab_load_kN"] / 3.0
            pts = [(m["x1"], m["y1"]),
                   (0.5 * (m["x1"] + m["x2"]), 0.5 * (m["y1"] + m["y2"])),
                   (m["x2"], m["y2"])]
            for px, py in pts:
                best, bd = None, 1e30
                for e in beams_lvl:
                    for nid in (e["ni"], e["nj"]):
                        nx, ny, _ = ops.nodeCoord(nid)
                        d = math.hypot(px - nx, py - ny)
                        if d < bd:
                            bd, best = d, nid
                if best is not None:
                    add(best, q)
                    totals["slab"] += q

    totals["total"] = totals["self"] + totals["slab"]

    # Cargas aplicadas en los NODOS REALES de extremo (sin reubicacion):
    # con la formulacion Transformation + rigidDiaphragm (plano 1,2,6) cada
    # nodo soporta su uz/rotaciones por elementos; no hay nodos esclavos de
    # anclaje y no hay restricciones redundantes => equilibrio exacto.
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    for tag, p in nodal.items():
        ops.load(tag, 0.0, 0.0, -p, 0.0, 0.0, 0.0)
    return nodal, totals


def run_analysis():
    ops.system(SYSTEM)
    ops.numberer(NUMBERER)
    ops.constraints(CONSTRAINTS)
    ops.algorithm(ALGORITHM)
    ops.integrator("LoadControl", INTEGRATOR_STEP)
    ops.analysis("Static")
    return ops.analyze(NUM_STEPS)


def extract_reactions(summary):
    try:
        ops.reactions()
    except Exception:
        pass
    rxn = {"fx": 0.0, "fy": 0.0, "fz": 0.0, "mx": 0.0, "my": 0.0, "mz": 0.0}
    n = 0
    for tag in summary["base_fixed_tags"]:
        try:
            r = ops.nodeReaction(tag)
            for k in ("fx", "fy", "fz", "mx", "my", "mz"):
                rxn[k] += r[tuple("fx fy fz mx my mz".split()).index(k)]
            n += 1
        except Exception:
            continue
    return rxn, n


def max_displacement(summary):
    disp = {1: 0.0, 2: 0.0, 3: 0.0}
    for tag in ops.getNodeTags():
        try:
            u = ops.nodeDisp(tag)
            for dof in (1, 2, 3):
                disp[dof] = max(disp[dof], abs(u[dof - 1]))
        except Exception:
            continue
    return disp


def verify_gravity(ok, totals, rxn, trib_out, tol=0.001):
    r = {}
    r["convergencia"] = ("OK" if ok == 0 else "FALLO", f"analyze retcode={ok}")
    r["peso_propio"] = (
        "OK",
        f"columnas={totals['self_cols']:.1f} vigas={totals['self_beams']:.1f} "
        f"muros={totals['self_walls']:.1f} total={totals['self']:.1f} kN"
    )
    r["carga_losa"] = ("OK" if totals["slab"] > 0 else "WARNING",
                       f"total trasferido a vigas={totals['slab']:.1f} kN")
    r["carga_gravitacional_total"] = ("OK", f"{totals['total']:.1f} kN")
    denom = totals["total"]
    err = abs(rxn["fz"] - denom) / denom if denom > 0 else 0.0
    r["equilibrio_vertical"] = ("OK" if err < tol else "FALLO",
                                f"reacciones Fz={rxn['fz']:.1f} vs aplicada={denom:.1f} "
                                f"err={err*100:.3f}%")
    r["equilibrio_horizontal"] = ("OK" if abs(rxn["fx"]) < 1e-5 and abs(rxn["fy"]) < 1e-5 else "FALLO",
                                  f"fx={rxn['fx']:.6f} fy={rxn['fy']:.6f}")

    # Verificacion por piso (area y carga) - reporte informativo
    r["por_piso"] = {}
    for lvl, v in trib_out["per_level"].items():
        r["por_piso"][lvl] = {
            "A_losa_m2": v["A_losa"],
            "A_trib_m2": v["A_trib"],
            "error_area_%": None if v["error_area"] is None else round(v["error_area"] * 100, 3),
            "carga_esperada_kN": v["carga_esperada"],
            "carga_transferida_kN": v["carga_transferida"],
            "error_carga_%": None if v["error_carga"] is None else round(v["error_carga"] * 100, 3),
        }
    return r


def compute_reactions_to_table(summary, rxn, n_rx):
    rows = []
    for tag in summary["base_fixed_tags"]:
        try:
            r = ops.nodeReaction(tag)
            rows.append({"node": tag, "fx": r[0], "fy": r[1], "fz": r[2],
                         "mx": r[3], "my": r[4], "mz": r[5]})
        except Exception:
            rows.append({"node": tag, "fx": 0, "fy": 0, "fz": 0,
                         "mx": 0, "my": 0, "mz": 0})
    return rows