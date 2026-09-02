"""
Orquestador v2: modelo -> losas -> areas tributarias explicitas -> gravedad ->
analisis -> verificaciones -> JSON/CSV/figuras.

Uso:
    python src/run_structure.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import openseespy.opensees as ops
from ops_model import load_aligned, build_ops_model, verify_model, verify_diaphragms
from slabs import build_slabs
from tributary import compute_tributary
from gravity import (
    apply_gravity, run_analysis, extract_reactions, max_displacement,
    verify_gravity, compute_reactions_to_table,
)
from structure_params import SLAB_QG_KN_M2, SLAB_FINISHES_KN_M2


def save_json(obj, relpath):
    p = ROOT / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=float)
    return p


def save_csv(rows, relpath):
    p = ROOT / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return p
    cols = list(rows[0].keys())
    with open(p, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")) for c in cols) + "\n")
    return p


def main():
    report = {}
    data = load_aligned()
    report["source"] = "data/processed/building_3d_aligned.json"
    report["q_G"] = {
        "espesor_losa_m": 0.15, "fuente_espesor": "PLANOS/BENCHMARK",
        "gamma_concreto_kN_m3": 25.0, "fuente_gamma": "BENCHMARK",
        "terminaciones_kN_m2": SLAB_FINISHES_KN_M2, "fuente_terminaciones": "INPUT_REQUIRED (sin valor confirmado)",
        "q_G_kN_m2": SLAB_QG_KN_M2, "status": "PROVISIONAL",
    }

    # ── 1) Modelo v2 ──
    summary = build_ops_model(data)
    report["modelo"] = {
        "n_nodes": summary["n_nodes"], "n_elements": summary["n_elements"],
        "n_columns": summary["n_columns"], "n_beams": summary["n_beams"],
        "n_walls": summary["n_walls"], "n_diaphragms": summary["n_diaphragms"],
        "n_base_fixed": summary["n_base_fixed"],
        "muros_solo_carga_sin_rigidez": summary.get("n_walls_load_only", 0),
        "vigas_solo_carga_sin_rigidez": summary.get("n_beams_load_only", 0),
    }
    report["muros_solo_carga"] = {
        "concepto": "muros apoyados en losa sin conexion a reticola: sin rigidez FE, peso transferido a vigas reales proximas, geometria trazada en physical_beam_map",
        "lista": {f"{k[0]}/{k[1]}": v for k, v in summary.get("load_only_members", {}).items()},
    }
    report["verificaciones_modelo"] = {k: {"state": v[0], "detail": v[1]}
                                       for k, v in verify_model(summary, data).items()}

    # ── 2) Losas por piso ──
    slabs, by_level = build_slabs(data)
    report["losas"] = slabs

    # ── 3) Areas tributarias explicitas (losa -> vigas) ──
    trib_out = compute_tributary(data, summary, by_level)
    report["areas_tributarias"] = {
        "method": "malla fina 0.25m; punto->viga mas cercana; poligono ortogonal",
        "per_level": trib_out["per_level"],
        "beam_load_kN": trib_out["beam_load"],
    }

    # ── 4) Gravedad: peso propio (A+B+C) + q_G de losa a vigas (D) ──
    nodal_load, totals = apply_gravity(summary, trib_out)
    report["peso_propio"] = {
        "columnas_kN": totals["self_cols"],
        "vigas_kN": totals["self_beams"],
        "muros_kN": totals["self_walls"],
        "total_kN": totals["self"],
    }
    report["carga_gravitacional"] = {
        "peso_propio_kN": totals["self"],
        "carga_losa_kN": totals["slab"],
        "total_aplicada_kN": totals["total"],
        "q_G_kN_m2": SLAB_QG_KN_M2,
    }

    # ── 5) Analisis ──
    ok = run_analysis()
    report["analisis"] = {"convergio": (ok == 0), "retcode": ok}
    rxn, n_rx = extract_reactions(summary)
    disp = max_displacement(summary)
    report["reacciones"] = {"n_reacciones": n_rx, **rxn}
    report["desplazamiento_maximo"] = {f"u{k}": v for k, v in disp.items()}

    # ── 5b) Compatibilidad del diafragma rigido por piso ──
    report["verificaciones_diafragma"] = verify_diaphragms(summary, ok=ok)

    # ── 6) Verificaciones ──
    grav_verify = verify_gravity(ok, totals, rxn, trib_out)
    report["verificaciones_analisis"] = {
        k: (v if isinstance(v, dict) else {"state": v[0], "detail": v[1]})
        for k, v in grav_verify.items()
    }

    # ── 7) Salidas ──
    save_json(report, "data/processed/structure_results.json")
    save_json(slabs, "data/processed/slabs.json")
    save_json({"method": report["areas_tributarias"]["method"],
               "per_beam_elementTag": {t: {"level": lvl, **det}
                                       for lvl, recs in trib_out["receivers"].items()
                                       for rec in recs for det in rec["elements"]
                                       for t in [det["tag"]]}},
              "data/processed/tributary_areas.json")

    save_csv(summary["col_elements"], "results/columnas.csv")
    save_csv(summary["wall_elements"], "results/muros.csv")
    save_csv(compute_reactions_to_table(summary, rxn, n_rx), "results/reacciones.csv")

    # vigas.csv con columnas tributarias para Unity
    tag2slab = {t: {"level": "?", "tributary_area_m2": 0.0, "slab_load_kN": 0.0,
                    "equivalent_line_load_kN_m": 0.0}
                for t in [det["tag"] for lvl, recs in trib_out["receivers"].items()
                          for rec in recs for det in rec["elements"]]}
    for lvl, recs in trib_out["receivers"].items():
        for rec in recs:
            for det in rec["elements"]:
                tag2slab[det["tag"]] = {"level": lvl,
                                        "tributary_area_m2": det["tributary_area_m2"],
                                        "slab_load_kN": det["slab_load_kN"],
                                        "equivalent_line_load_kN_m": det["equivalent_line_load_kN_m"]}
    viga_rows = []
    for e in summary["beam_elements"]:
        info = tag2slab.get(e["tag"], {})
        viga_rows.append({**e,
                          "tributary_area_m2": round(info.get("tributary_area_m2", 0.0), 4),
                          "slab_load_kN": round(info.get("slab_load_kN", 0.0), 3),
                          "equivalent_line_load_kN_m": round(info.get("equivalent_line_load_kN_m", 0.0), 4),
                          "tributary_level": info.get("level", "")})
    save_csv(viga_rows, "results/vigas.csv")

    # ── 8) Figura QA ──
    try:
        make_figure(trib_out, by_level, summary)
        report["figuras"] = {"tributary_areas": "figures/tributary_areas.png"}
    except Exception as e:
        report["figuras"] = {"tributary_areas": f"no generada: {e}"}

    save_json(report, "data/processed/structure_results.json")
    print_final(report)


def make_figure(trib_out, by_level, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 11))
    for ax, (lvl, slab) in zip([axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]],
                               [("P1", by_level.get("P1")), ("P2", by_level.get("P2")),
                                ("P3", by_level.get("P3")), ("P4", by_level.get("P4"))]):
        if slab is None:
            ax.set_title(lvl)
            continue
        p = slab["polygon"]
        px = [v[0] for v in p] + [p[0][0]]
        py = [v[1] for v in p] + [p[0][1]]
        ax.plot(px, py, color="black", lw=2, label="contorno losa")
        ax.fill(px, py, color="lightgray", alpha=0.3)
        # vigas receptoras (elementos v2 del nivel)
        for e in summary["beam_elements"]:
            if e["level"] != lvl:
                continue
            x1, y1, _ = ops.nodeCoord(e["ni"])
            x2, y2, _ = ops.nodeCoord(e["nj"])
            ax.plot([x1, x2], [y1, y2], color="cornflowerblue", lw=1.0)
        # poligonos tributarios
        for rec in trib_out["receivers"].get(lvl, []):
            poly = rec["polygon"]
            if not poly:
                continue
            bx = [v[0] for v in poly] + [poly[0][0]]
            by = [v[1] for v in poly] + [poly[0][1]]
            ax.plot(bx, by, color="salmon", lw=0.6)
        ax.set_title(f"{lvl}  A_losa={slab['area_m2']:.1f} m2  "
                     f"A_trib={trib_out['per_level'][lvl]['A_trib']:.1f} m2")
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    (ROOT / "figures").mkdir(exist_ok=True)
    fig.savefig(ROOT / "figures" / "tributary_areas.png", dpi=150)
    plt.close(fig)


def print_final(report):
    print("=" * 62)
    print("RESUMEN GRAVEDAD v2 - q_G losa -> areas tributarias -> vigas")
    print("=" * 62)
    q = report["q_G"]
    print(f"q_G = {q['q_G_kN_m2']:.2f} kN/m2 (espesor {q['espesor_losa_m']} "
          f"x 25 + term {q['terminaciones_kN_m2']}) [{q['status']}]")
    print(f"  terminaciones: {q['fuente_terminaciones']}")
    print("-" * 62)
    print("POR PISO:")
    for lvl, v in report["areas_tributarias"]["per_level"].items():
        ea = v["error_area"]
        ec = v["error_carga"]
        print(f"  {lvl}: A_losa={v['A_losa']:.2f} m2  A_trib={v['A_trib']:.2f} m2  "
              f"err_area={('n/a' if ea is None else f'{ea*100:.3f}%')}  "
              f"carga_esp={v['carga_esperada']:.1f}  transf={v['carga_transferida']:.1f}  "
              f"err_carga={('n/a' if ec is None else f'{ec*100:.3f}%')}")
    print("-" * 62)
    sw = report["peso_propio"]
    g = report["carga_gravitacional"]
    print(f"Peso propio: cols={sw['columnas_kN']:.1f} vigas={sw['vigas_kN']:.1f} "
          f"muros={sw['muros_kN']:.1f} total={sw['total_kN']:.1f} kN")
    print(f"Carga losa (a vigas): {g['carga_losa_kN']:.1f} kN")
    print(f"Total gravitacional: {g['total_aplicada_kN']:.1f} kN")
    a = report["analisis"]
    print(f"Convergencia: {'OK' if a['convergio'] else 'FALLO'} retcode={a['retcode']}")
    r = report["reacciones"]
    print(f"Reacciones verticales: {r['fz']:.1f} kN "
          f"(aplicada {g['total_aplicada_kN']:.1f})")
    print(f"Error equilibrio: {100*abs(r['fz']-g['total_aplicada_kN'])/g['total_aplicada_kN']:.4f}%")
    if "verificaciones_diafragma" in report:
        for lvl, v in report["verificaciones_diafragma"].items():
            if isinstance(v, dict) and "state" in v:
                print(f"  Diafragma {lvl}: [{v['state']}] master={v.get('master')} "
                      f"esclavos={v.get('n_slaves')} "
                      f"compatH={v.get('compat_horiz_max_m', 'n/a')} m")
    for k, v in report["verificaciones_analisis"].items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                if isinstance(sv, dict):
                    print(f"    {sk}: {sv}")
                else:
                    print(f"    [{sv[0]}] {sv[1]}" if isinstance(sv, tuple) else f"    {sk}: {sv}")
        else:
            print(f"  [{v['state']}] {v['detail']}")


if __name__ == "__main__":
    main()