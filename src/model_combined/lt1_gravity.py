"""Cargas gravitacionales de LT1 en el combinado (pattern 6000 / serie 5000).

Encapsula la logica de `gravity.py` (ops.load nodales, peso propio A+B+C +
losa D junto con la transferencia de miembros "load_only") pero:
  - pattern LT1 = 6000  (timeSeries Linear 5000)
  - usa el summary adaptado del constructor combinado (tags LT1 offset y
    nodos de interfaz ya remapeados a LT2).
Reutiliza `tributary.compute_tributary` (puro, sin efectos sobre ops) con el
mismo `data` de LT1 y el summary combinado.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops  # noqa: E402
from structure_params import (  # noqa: E402
    GAMMA_CONCRETE, COL_A, BEAM_A, WALL_THICKNESS, WALL_H_DEFAULT,
)
from tributary import compute_tributary  # noqa: E402

from . import config as C


def build_tributary_lt1(data, lt1_summary):
    """Areas tributarias LT1 (misma funcion que gravity/check LT1)."""
    return compute_tributary(data, lt1_summary)


def apply_gravity_lt1(lt1_summary, trib_out, pattern=C.PATTERN_LT1,
                      timeseries=C.TIME_SERIES_LT1):
    """Aplica cargas LT1 via ops.load nodales; devuelve (nodal, totals)."""
    nodal = {}
    totals = {"self": 0.0, "slab": 0.0, "total": 0.0,
              "self_cols": 0.0, "self_beams": 0.0, "self_walls": 0.0}

    def add(tag, p):
        nodal[tag] = nodal.get(tag, 0.0) + p

    # A+B+C peso propio
    for e in lt1_summary["col_elements"]:
        p = COL_A * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_cols"] += 2 * p
    for e in lt1_summary["beam_elements"]:
        p = BEAM_A * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_beams"] += 2 * p
    for e in lt1_summary["wall_elements"]:
        p = WALL_THICKNESS * WALL_H_DEFAULT * e["length"] * GAMMA_CONCRETE / 2.0
        add(e["ni"], p); add(e["nj"], p)
        totals["self"] += 2 * p
        totals["self_walls"] += 2 * p

    # muros/vigas "solo carga"
    beam_level_nodes = {}
    for e in lt1_summary["beam_elements"]:
        beam_level_nodes.setdefault(e["level"], []).append(e)
    for _k, m in lt1_summary.get("load_only_members", {}).items():
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

    # D losa q_G -> vigas
    tag2ele = {e["tag"]: e for e in lt1_summary["beam_elements"]}
    for tag, p in trib_out["beam_load"].items():
        e = tag2ele.get(tag)
        if e is None:
            continue
        add(e["ni"], p / 2.0); add(e["nj"], p / 2.0)
        totals["slab"] += p

    # D-ter losa de vigas "solo carga"
    if lt1_summary.get("load_only_members"):
        rec_by_orig = {(lvl, r["orig"]): r for lvl, recs in
                      trib_out["receivers"].items() for r in recs}
        for k, m in lt1_summary["load_only_members"].items():
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

    ops.timeSeries("Linear", timeseries)
    ops.pattern("Plain", pattern, timeseries)
    for tag, p in nodal.items():
        ops.load(tag, 0.0, 0.0, -p, 0.0, 0.0, 0.0)
    return nodal, totals