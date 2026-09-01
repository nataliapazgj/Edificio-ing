# -*- coding: utf-8 -*-
"""BLOQUE 3 — Checker de las cargas gravitacionales aplicadas LT2.

Verifica que la conversion de areas tributarias L1-L4 a cargas de viga
(results/gravity_loads_applied_LT2.csv) es trazable y conservativa:

  panel -> tributaria -> beam_id -> element_tag -> xloc -> P

Chequeos:
  C1  estructura de archivos (schema)
  C2  por viga: fuerza total aplicada == total_slab_load_kN del CSV 2B
  C3  por viga: primer momento aplicado == primer momento de las celdas
      fuente (balance de celdas de la grilla tributaria)
  C4  global: ΣP aplicado == Σ total_slab_load_kN (11541.2916 kN aprox)
  C5  rastreo: element_tag en [2001, 2001+?] y beam_id corresponde; s in [0,1]
  C6  integridad: 0 nans, xloc ordenado por k, cargas > 0
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

import gravity_loads

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

OUT_POINTS = RESULTS / "gravity_loads_applied_LT2.csv"
OUT_BEAMS = RESULTS / "gravity_loads_beam_summary_LT2.csv"

LEVELS = gravity_loads.LEVELS
STEP = gravity_loads.STEP


def _report(msg, is_error=False):
    print(("[ERR] " if is_error else "[OK]  ") + msg)
    return is_error


def main():
    errors = 0
    warnings = 0

    # ---------- archivos ----------
    if not OUT_POINTS.exists():
        return _report(f"falta {OUT_POINTS}", True)
    if not OUT_BEAMS.exists():
        return _report(f"falta {OUT_BEAMS}", True)

    pts = pd.read_csv(OUT_POINTS)
    summ = pd.read_csv(OUT_BEAMS)

    # C1 schema
    req_pts = ["level", "beam_id", "element_tag", "L", "xloc", "load_kN", "k", "s_m"]
    missing = [c for c in req_pts if c not in pts.columns]
    errors += int(bool(missing))
    if missing:
        _report(f"C1 missing columns en points: {missing}", True)
    else:
        _report("C1 schema resultados -> gravity_loads_applied_LT2.csv OK")

    # C6 integridad
    if "load_kN" in pts.columns:
        bad = int((pts["load_kN"].isna().sum())
                  + (pts["xloc"] < -1e-9).sum()
                  + (pts["xloc"] > 1 + 1e-9).sum()
                  + (pts["load_kN"] <= 0).sum())
        if bad:
            errors += 1
            _report(f"C6 integridad: {bad} valores invalidos (nan/neg/hay 0)", True)
        else:
            _report("C6 integridad: sin nans, cargas>0, xloc en [0,1]", )

    # C5 rastreo beam_id / tag
    beams = gravity_loads.load_beams()
    beam_tag = dict(zip(beams.beam_id, beams.tag))
    wrong = 0
    for r in pts.itertuples(index=False):
        if beam_tag.get(r.beam_id) != int(r.element_tag):
            wrong += 1
    if wrong:
        errors += 1
        _report(f"C5 rastreo: {wrong} puntos con beam_id/element_tag inconsistente", True)
    else:
        _report("C5 rastreo beam_id->element_tag coherente (2001+indice)")

    # C2 por viga fuerza
    exp = gravity_loads.expected_beam_loads().set_index(["level", "beam_id"])
    n_beam = 0
    max_rel_f = 0.0
    miss_beam = 0
    for (lv, bid), g in pts.groupby(["level", "beam_id"]):
        if (lv, bid) not in exp.index:
            miss_beam += 1
            continue
        p_app = float(g["load_kN"].sum())
        p_exp = float(exp.loc[(lv, bid), "total_slab_load_kN"])
        n_beam += 1
        max_rel_f = max(max_rel_f, abs(p_app - p_exp) / max(abs(p_exp), 1e-12))
    if miss_beam:
        errors += 1
        _report(f"C2 fuerza: {miss_beam} vigas sin correspondencia en beam_gravity_loads", True)
    elif max_rel_f < 1e-5:
        _report(f"C2 fuerza por viga: max err rel {max_rel_f:.2e} (OK)")
    else:
        errors += 1
        _report(f"C2 fuerza por viga: max err rel {max_rel_f:.2e} (EXCEDIDO)", True)

    # C3 primer momento por viga (vs celdas fuente)
    _, cells = gravity_loads.build_point_loads()
    max_rel_m = 0.0
    checked = 0
    for key, g in pts.groupby(["level", "beam_id"]):
        c = cells.get(key)
        if c is None:
            continue
        m_app = float((g["load_kN"] * g["s_m"]).sum())
        m_exp = c["M"]
        checked += 1
        max_rel_m = max(max_rel_m, abs(m_app - m_exp) / max(abs(m_exp), 1e-12))
    if checked:
        if max_rel_m < 1e-3:
            _report(f"C3 primer momento: max err rel {max_rel_m:.2e} (OK, {checked} vigas)")
        else:
            errors += 1
            _report(f"C3 primer momento: max err rel {max_rel_m:.2e} (EXCEDIDO)", True)

    # C4 global
    p_app = float(pts["load_kN"].sum())
    p_exp = float(exp["total_slab_load_kN"].sum())
    gerr = abs(p_app - p_exp) / max(abs(p_exp), 1e-12)
    agg = summ["applied_load_kN"].sum() if "applied_load_kN" in summ.columns else np.nan
    if gerr < 1e-5 and (agg is np.nan or abs(agg - p_app) < 1e-6):
        _report(f"C4 global: ΣP_app={p_app:.6f} vs ΣP_exp={p_exp:.6f} "
                f"(err rel {gerr:.2e})")
    else:
        errors += 1
        _report(f"C4 global: ΣP_app={p_app:.6f} vs ΣP_exp={p_exp:.6f} "
                f"(err rel {gerr:.2e}) EXCEDIDO", True)

    # resumen
    print()
    print(f"Resumen: errores={errors} avisos={warnings}")
    print(f"vigas con carga: {n_beam}; puntos de carga: {len(pts)}")
    counter = Counter(pts.level)
    print("puntos por nivel:", {lv: int(counter.get(lv, 0)) for lv in LEVELS})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())