"""Orquestador del modelo combinado LT1 + LT2 (PASOS 1-9).

Flujo:
  1. Un único ops.wipe() + ops.model(basic, ndm=3, ndf=6).
  2. Construir LT2 (reutilizando ModelBuilder sin wipe).
  3. Construir LT1 transformado (adaptado, sin wipe, interfaz compartida).
  4. Diafragmas combinados por nivel (master LT2).
  5. Cargas LT2 (eleLoad, pattern 1) y LT1 (ops.load, pattern 6000 / serie 5000).
  6. Verificaciones previas (PASO 7); si falla alguna critica -> no analisis.
  7. Análisis estático gravitacional (PASO 8).
  8. Resultados en results/combined/ (PASO 9) y resumen en salida.

NO modifica archivos de LT1/LT2; NO hace commit/push.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "model_combined"))

import numpy as np  # noqa: E402
import openseespy.opensees as ops  # noqa: E402

from . import config as C
from .lt2_builder_wrapper import LT2Model
from .lt1_builder_combined import build_ops_model_combined
from .diaphragms_combined import build_diaphragms
from .lt1_gravity import build_tributary_lt1, apply_gravity_lt1
from .verify import CombinedChecks
from . import lt2_walls
from . import lt2_connect
import gravity_loads as gl  # noqa: E402


def build_lt2():
    m = LT2Model()
    m.build(skip_diaphragms=True)   # diafragmas los hara el orquestador
    m.wall_stats = lt2_walls.materialize_lt2_walls(m)
    m.connect_stats = lt2_connect.connect_floating_beams(m)
    return m


def build_lt1():
    from ops_model import load_aligned
    data = load_aligned()           # puro, incluye correccion Y P3/P4
    summary = build_ops_model_combined(data, with_init=False,
                                       apply_transform=True)
    return data, summary


def apply_lt2_gravity():
    points, _ = gl.build_point_loads()
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    n = 0
    for row in points.itertuples(index=False):
        ops.eleLoad("-ele", int(row.element_tag), "-type", "-beamPoint",
                    0.0, -float(row.load_kN), float(row.xloc))
        n += 1
    applied = float(points["load_kN"].sum())
    return points, applied, int(n)


def run_analysis():
    ops.system("BandGeneral")
    ops.numberer("RCM")
    # constraints Transformation ya seteado por LT2
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    rc = ops.analyze(1)
    return rc


def collect_results(lt2, lt1_summary, lt2_p, lt2_total, lt1_nodal, lt1_totals):
    res = {}
    res["n_nodes"] = len(ops.getNodeTags())
    res["n_elements"] = len(ops.getEleTags())
    # contadores por torre (LT1 del summary; LT2 derivado de tags)
    lt2_beams = len([t for t in ops.getEleTags() if 2001 <= t < 3001])
    lt2_cols = len([t for t in ops.getEleTags() if 3001 <= t < 4001])
    lt2_walls = len([t for t in ops.getEleTags() if 4001 <= t < 9000])
    lt2_conn = len([t for t in ops.getEleTags() if 9001 <= t < 10000])
    res["lt2_beams"] = lt2_beams
    res["lt2_cols"] = lt2_cols
    res["lt2_walls"] = lt2_walls
    res["lt2_connectors"] = lt2_conn
    res["lt1_columns"] = len(lt1_summary["col_elements"])
    res["lt1_beams"] = len(lt1_summary["beam_elements"])
    res["lt1_walls"] = len(lt1_summary["wall_elements"])
    res["n_interface"] = len(C.INTERFACE_MAP)
    res["lt2_total_load_kN"] = float(lt2_total)
    res["lt1_total_load_kN"] = lt1_totals["total"]
    res["combined_total_load_kN"] = float(lt2_total) + lt1_totals["total"]
    # reacciones
    support_tags = lt2.support_tags + lt1_summary["base_fixed_tags"]
    sum_rz = 0.0
    fx = fy = 0.0
    if res.get("rc") == 0 or True:
        ops.reactions()
        for tag in sorted(set(support_tags)):
            try:
                sum_rz += ops.nodeReaction(tag, 3)
                fx += ops.nodeReaction(tag, 1)
                fy += ops.nodeReaction(tag, 2)
            except Exception:
                pass
    res["sum_rz_kN"] = float(sum_rz)
    res["sum_fx_kN"] = float(fx)
    res["sum_fy_kN"] = float(fy)
    denom = res["combined_total_load_kN"]
    res["equil_err_rel"] = (abs(sum_rz - denom) / max(abs(denom), 1e-12)
                            if denom != 0 else np.nan)
    return res


def main():
    print("PASO 1: unico ops.wipe() + modelo basico")
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    print("PASO 2: construir LT2 (sin wipe)")
    lt2 = build_lt2()

    print("PASO 3: construir LT1 transformado")
    data, lt1 = build_lt1()

    print("PASO 4: diafragmas combinados")
    diaphs = build_diaphragms(lt2, lt1)

    print("PASO 5: cargas LT2 (pattern 1)")
    points, lt2_total, n_lt2 = apply_lt2_gravity()

    print("PASO 6: cargas LT1 (pattern 6000 / serie 5000)")
    trib = build_tributary_lt1(data, lt1)
    lt1_nodal, lt1_totals = apply_gravity_lt1(lt1, trib)

    print("PASO 7: verificaciones previas")
    chk = CombinedChecks(lt2, lt1, data, trib)
    checks = chk.run_all()
    critical_bad = chk.critical_only()

    report = {
        "checks": checks,
        "critical_bad": critical_bad,
        "diaphragms": diaphs,
        "lt2_total_load_kN": lt2_total,
        "lt1_self_kN": lt1_totals["self"],
        "lt1_slab_kN": lt1_totals["slab"],
        "lt1_total_load_kN": lt1_totals["total"],
    }

    # PASO 8: analisis (solo si pasan las criticas)
    rc = None
    if critical_bad:
        print("VERIFICACIONES CRITICAS FALLIDAS -> NO se ejecuta analisis:")
        for k in critical_bad:
            print(f"  - {k}: {checks[k][1]}")
    else:
        print("PASO 8: analisis estatico gravitacional")
        rc = run_analysis()
        print(f"analyze return code = {rc}")

    ops.reactions()
    support_tags = sorted(set(lt2.support_tags + lt1["base_fixed_tags"]))
    reactions = []
    if rc == 0:
        for tag in support_tags:
            reactions.append({
                "node_tag": tag,
                "Rx_kN": ops.nodeReaction(tag, 1),
                "Ry_kN": ops.nodeReaction(tag, 2),
                "Rz_kN": ops.nodeReaction(tag, 3),
            })
    Rz = float(sum(r["Rz_kN"] for r in reactions)) if rc == 0 else float("nan")
    totalv = lt2_total + lt1_totals["total"]
    rel_err = (abs(Rz - totalv) / max(abs(totalv), 1e-12)) if rc == 0 else float("nan")

    # desplazamiento maximo
    uz_max, uz_node = 0.0, None
    if rc == 0:
        for t in ops.getNodeTags():
            try:
                u = ops.nodeDisp(t, 3)
                if abs(u) > abs(uz_max):
                    uz_max, uz_node = u, t
            except Exception:
                pass

    stats = {
        "n_nodes": len(ops.getNodeTags()),
        "n_elements": len(ops.getEleTags()),
        "n_interface_shared": len(C.INTERFACE_MAP),
        "lt2_beams": len([t for t in ops.getEleTags() if 2001 <= t < 3001]),
        "lt2_cols": len([t for t in ops.getEleTags() if 3001 <= t < 4001]),
        "lt2_walls": len([t for t in ops.getEleTags() if 4001 <= t < 9000]),
        "lt2_connectors": len([t for t in ops.getEleTags() if 9001 <= t < 10000]),
        "lt1_columns": len(lt1["col_elements"]),
        "lt1_beams": len(lt1["beam_elements"]),
        "lt1_walls": len(lt1["wall_elements"]),
        "rc": rc,
        "lt2_total_load_kN": lt2_total,
        "lt1_total_load_kN": lt1_totals["total"],
        "combined_total_load_kN": totalv,
        "sum_rz_kN": Rz,
        "equil_rel_err": rel_err,
        "uz_max_m": uz_max,
        "uz_node": uz_node,
        "n_support": len(support_tags),
    }
    report["stats"] = stats

    # PASO 9: escritura de resultados
    write_outputs(report, lt2, lt1, reactions, data)

    print_summary(report)
    return 0 if (rc == 0 and not critical_bad) else (1 if critical_bad else 2)


def make_interface_csv(lt2=None, lt1=None):
    import csv
    rows = []
    lvz = {"P1": -0.05, "P2": 3.91, "P3": 7.87, "P4": 11.83}
    for lt1tag, lt2tag in C.INTERFACE_MAP.items():
        level = {5: "P1", 4: "P1", 6: "P1",
                 21: "P2", 20: "P2", 22: "P2",
                 39: "P3", 38: "P3", 40: "P3",
                 57: "P4", 56: "P4", 58: "P4"}[lt1tag]
        rows.append({
            "lt1_tag": lt1tag, "lt2_tag": lt2tag, "level": level,
            "z_m": lvz[level],
        })
    return rows


def write_outputs(report, lt2, lt1, reactions, data):
    import csv
    C.RESULTS.mkdir(parents=True, exist_ok=True)
    che = report["checks"]

    # summary.txt
    lines = []
    add = lines.append
    add("MODELO COMBINADO LT1 + LT2  ---  resumen")
    add("=" * 60)
    st = report["stats"]
    add(f"return_code (analyze)      : {st['rc']}")
    add(f"nodos totales              : {st['n_nodes']}")
    add(f"elementos totales          : {st['n_elements']}")
    add(f"nodos interfaz compartidos : {st['n_interface_shared']}")
    add(f"LT2: vigas={st['lt2_beams']} columnas={st['lt2_cols']} "
        f"muros-col={st['lt2_walls']} conectores={st['lt2_connectors']}")
    add(f"LT1: columnas={st['lt1_columns']} vigas={st['lt1_beams']} "
        f"muros={st['lt1_walls']}")
    add(f"carga vertical total LT1   : {st['lt1_total_load_kN']:.6f} kN")
    add(f"carga vertical total LT2   : {st['lt2_total_load_kN']:.6f} kN")
    add(f"carga vertical combinada   : {st['combined_total_load_kN']:.6f} kN")
    add(f"suma reacciones verticales : {st['sum_rz_kN']:.6f} kN")
    add(f"error relativo equilibrio  : {st['equil_rel_err']:.6e}")
    add(f"desplazamiento vertical max: {st['uz_max_m']}  en nodo {st['uz_node']}")
    add(f"apoyos considerados        : {st['n_support']}")
    add("")
    add("VERIFICACIONES PREVIAS:")
    for k, (st_, det) in che.items():
        add(f"  [{st_}] {k}: {det}")
    add("")
    add("Resultados entrega A-I: ver consola y CSV/visualizacion.")

    text = "\n".join(lines) + "\n"

    # model_stats.csv
    stats_rows = [{"metric": k, "value": v} for k, v in st.items()]
    for k, (st_, det) in che.items():
        stats_rows.append({"metric": "check_" + k, "value": st_+"|"+det})

    # gravity_check.csv
    grav = [
        {"metric": "lt2_total_load_kN", "value": st["lt2_total_load_kN"]},
        {"metric": "lt1_total_load_kN", "value": st["lt1_total_load_kN"]},
        {"metric": "combined_total_load_kN", "value": st["combined_total_load_kN"]},
        {"metric": "sum_rz_kN", "value": st["sum_rz_kN"]},
        {"metric": "equil_rel_err", "value": st["equil_rel_err"]},
    ]

    with open(C.RESULTS / "summary.txt", "w", encoding="utf-8") as f:
        f.write(text)

    with open(C.RESULTS / "model_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "value"])
        w.writeheader()
        w.writerows(stats_rows)

    with open(C.RESULTS / "gravity_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["metric", "value"])
        w.writeheader()
        w.writerows(grav)

    with open(C.RESULTS / "nodes_interface.csv", "w", newline="", encoding="utf-8") as f:
        rows = make_interface_csv()
        w = csv.DictWriter(f, fieldnames=["lt1_tag", "lt2_tag", "level", "z_m"])
        w.writeheader()
        w.writerows(rows)

    # visualizacion simple (columnas + vigas LT1 + nodos) -> HTML
    try:
        write_html(st)
    except Exception as e:
        print("warn: vis HTML no generada:", e)
    return C.RESULTS


def write_html(st):
    """Visualizacion 3D simple de la geometria combinada (plotly stand-alone)."""
    import json
    import os
    import plotly.graph_objects as go
    node_xyz = {t: ops.nodeCoord(t) for t in ops.getNodeTags()}
    xs, ys, zs = [], [], []
    for t, c in node_xyz.items():
        xs.append(c[0]); ys.append(c[1]); zs.append(c[2])
    # columnas/vigas como lineas
    lx, ly, lz = [], [], []
    for t in ops.getEleTags():
        try:
            n1, n2 = ops.eleNodes(t)
        except Exception:
            continue
        c1, c2 = node_xyz.get(n1), node_xyz.get(n2)
        if not c1 or not c2:
            continue
        # columna (cerca de e) distinto de viga? por ahora todas las lineas
        lx += [c1[0], c2[0], None]
        ly += [c1[1], c2[1], None]
        lz += [c1[2], c2[2], None]
    mesh = go.Scatter3d(x=lx, y=ly, z=lz, mode="lines",
                        line=dict(color="steelblue", width=3), name="elementos")
    iface = [t for t in C.INTERFACE_MAP.values()]
    ips = go.Scatter3d(
        x=[node_xyz[t][0] for t in iface],
        y=[node_xyz[t][1] for t in iface],
        z=[node_xyz[t][2] for t in iface],
        mode="markers", marker=dict(color="red", size=6), name="interfaz")
    fig = go.Figure(data=[mesh, ips])
    fig.update_layout(scene=dict(aspectmode="data",
                                 xaxis_title="X", yaxis_title="Y",
                                 zaxis_title="Z"), title="Modelo combinado LT1+LT2")
    with open(C.RESULTS / "combined_geometry.html", "w", encoding="utf-8") as f:
        f.write(fig.to_html(include_plotlyjs="cdn"))
    print("Escrito:", C.RESULTS / "combined_geometry.html")


def print_summary(report):
    st = report["stats"]
    print("\n=== RESUMEN COMBINADO ===")
    print(f"rc={st['rc']}  nodos={st['n_nodes']}  elems={st['n_elements']}  "
          f"interfaz={st['n_interface_shared']}")
    print(f"LT2 vigas={st['lt2_beams']} cols={st['lt2_cols']} "
          f"muros-col={st['lt2_walls']} conect={st['lt2_connectors']} | "
          f"LT1 cols={st['lt1_columns']} vigas={st['lt1_beams']} "
          f"muros={st['lt1_walls']}")
    print(f"carga LT1={st['lt1_total_load_kN']:.4f}  LT2={st['lt2_total_load_kN']:.4f} "
          f"combinada={st['combined_total_load_kN']:.4f}")
    print(f"Rz={st['sum_rz_kN']:.4f}  err_rel={st['equil_rel_err']:.4e}")
    print(f"|Uz|max={st['uz_max_m']}  nodo={st['uz_node']}")


if __name__ == "__main__":
    sys.exit(main())