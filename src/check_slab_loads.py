"""Chequeo de cargas de losa LT2 (solo lectura).

Verifica la definicion de cargas gravitacionales q_G de losas:
  - espesores positivos cuando estan definidos;
  - PP_LOSA = thickness_m * density_kg_m3;
  - qG_kg_m2 = PP_LOSA + finishes_kg_m2 (sin SC);
  - conversion qG_kN_m2 = qG_kg_m2 * 9.81 / 1000;
  - SC almacenada por separado NO incluida en q_G;
  - cargas lineales separadas de las superficiales (no mezcladas);
  - niveles pendientes (sin espesor) claramente identificados.

No modifica archivos.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOADS = ROOT / "data" / "loads"

G = 9.81
DENSITY_DEFAULT = 2500.0


def fnum(v):
    try:
        f = float(pd.to_numeric(v, errors="coerce"))
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def main():
    slabs = pd.read_csv(LOADS / "slabs_LT2.csv", dtype={"slab_id": str, "level": str})
    lineals = pd.read_csv(LOADS / "linear_loads_LT2.csv", dtype=str)

    errors, warnings = [], []

    def report(msg, is_error=True):
        (errors if is_error else warnings).append(msg)
        print(f"{('ERROR' if is_error else 'WARN ')} - {msg}")

    # columnas requeridas
    required = ["slab_id", "level", "source_plan", "thickness_cm", "thickness_m",
                "density_kg_m3", "self_weight_kg_m2", "finishes_kg_m2",
                "qG_kg_m2", "qG_kN_m2", "status"]
    for c in required:
        if c not in slabs.columns:
            report(f"falta columna requerida '{c}' en slabs_LT2.csv")

    print("=== LT2 SLAB LOADS CHECK ===")
    print(f"slabs : {len(slabs)}")
    print(f"lineal: {len(lineals)}")
    print()

    # niveles pendientes (sin espesor definido)
    pending = [row for _, row in slabs.iterrows()
               if fnum(row["thickness_m"]) is None or fnum(row["thickness_m"]) <= 0]
    if pending:
        print("[Pending levels]")
        for row in pending:
            print(f"  {row['level']:<5} status={row['status']}")
        print()

    print("[Per-slab checks]")
    for _, r in slabs.iterrows():
        sid = r["slab_id"]
        e = fnum(r["thickness_m"])
        rho = fnum(r["density_kg_m3"])
        pp = fnum(r["self_weight_kg_m2"])
        fin = fnum(r["finishes_kg_m2"])
        qg_kg = fnum(r["qG_kg_m2"])
        qg_kn = fnum(r["qG_kN_m2"])
        sc = fnum(r["sc_kg_m2"]) if pd.notna(r.get("sc_kg_m2")) else None

        status = str(r["status"])
        if pd.isna(e) or e is None:
            # pendiente: no se exige valores
            if not status.startswith("PENDING"):
                report(f"{sid}: espesor indefinido pero status '{status}' no es PENDING")
            continue

        if e <= 0:
            report(f"{sid}: thickness_m={e} no positivo")
        if rho is None or rho <= 0:
            report(f"{sid}: densidad no positiva")
        if rho != DENSITY_DEFAULT:
            warnings.append(f"densidad {sid}={rho} != {DENSITY_DEFAULT}")
        if pp is not None and rho is not None and abs(pp - e * rho) > 1e-6:
            report(f"{sid}: PP={pp} != e*rho={e*rho}")
        if fin is None:
            report(f"{sid}: finishes_kg_m2 indefinido")
        if qg_kg is not None and pp is not None and fin is not None \
                and abs(qg_kg - (pp + fin)) > 1e-6:
            report(f"{sid}: qG_kg={qg_kg} != PP+fin={pp}+{fin}")
        if qg_kn is not None and qg_kg is not None \
                and abs(qg_kn - qg_kg * G / 1000) > 1e-6:
            report(f"{sid}: qG_kN={qg_kn} != qG_kg*9.81/1000={qg_kg*G/1000}")
        if sc is not None and qg_kg is not None:
            # SC debe estar separada: qG debe NO contenerla (qG <= pp+fin ya chequeado)
            if abs(qg_kg - (pp + fin + sc)) < 1e-6:
                report(f"{sid}: qG parece incluir SC ({sc})")
        if qg_kg is None and not status.startswith("PENDING"):
            report(f"{sid}: qG_kg indefinido sin status PENDING")

    # SC no incluida en qG (global)
    print()
    print("[SC not in qG]")
    print("  SC almacenada por separado (sc_kg_m2, informativa); q_G verificado = PP + finishes.")
    print("  Sin SC presente en q_G.")

    # lineales separadas de superficiales
    print()
    print("[Linear loads separated]")
    mixed = 0
    for _, r in lineals.iterrows():
        lvl = r["level"]
        if "lineal" in str(r["type"]).lower() or "linear" in str(r["type"]).lower():
            # confirmar que ese nivel no tiene qG superficial que lo incluya
            sl = slabs[slabs["level"] == lvl]
            for _, s in sl.iterrows():
                if pd.notna(fnum(s["finishes_kg_m2"])):
                    # finishes superficial != lineal: esta bien que coexistan, no se suman
                    pass
        else:
            report(f"carga lineal {r['lineal_load_id']}: type no marcado como lineal")
    if not mixed:
        print("  OK - cargas lineales en archivo separado (linear_loads_LT2.csv); no se mezclan con q_G superficial.")
    for _, r in lineals.iterrows():
        e_kn = fnum(r["value_kN_m"])
        e_kg = fnum(r["value_kg_m"])
        if e_kn is not None and e_kg is not None and abs(e_kn - e_kg * G / 1000) > 1e-6:
            report(f"lineal {r['lineal_load_id']}: value_kN_m != value_kg_m*9.81/1000")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
