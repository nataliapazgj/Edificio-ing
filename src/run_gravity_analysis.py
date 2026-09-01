# -*- coding: utf-8 -*-
"""BLOQUE 3 — Analisis estatico de gravedad del modelo LT2 (L1-L4).

Construye el modelo con el builder existente (sin duplicar nodos/elementos),
aplica las cargas gravitacionales derivadas de las areas tributarias L1-L4
(data/loads -> results/gravity_loads_applied_LT2.csv) mediante
`eleLoad -beamPoint` conservando fuerza total y primer momento, resuelve el
sistema lineal estatico y reporta equilibrio global, desplazamientos y
reacciones.

Reglas:
- no se inventan muros ni elementos; si el modelo sin muros resulta
  inestable, se reporta explicitamente (return code != 0) sin restricciones
  arbitrarias;
- no se toca la geometria ni las restricciones del modelo;
- ROOF, carga lineal ROOF y WALL_EDGE_PENDING quedan fuera (no aplicadas).

Salidas:
  results/gravity_reactions_LT2.csv
  results/gravity_displacements_LT2.csv
  reports/gravity_analysis_LT2.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import openseespy.opensees as ops

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_opensees_model import ModelBuilder  # noqa: E402
import gravity_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
REP = ROOT / "reports"
OUT_REACT = RES / "gravity_reactions_LT2.csv"
OUT_DISP = RES / "gravity_displacements_LT2.csv"
OUT_REPORT = REP / "gravity_analysis_LT2.md"
TOL = 1e-3


def _pt(x, y, z):
    return (round(x, 6), round(y, 6), round(z, 6))


def diagnose_mechanisms(builder):
    """Nodos estructurales sin camino al empotramiento base por el p«rtico.

    El modelo sin muros es un mecanismo: el bloque OESTE/nucleo (x<11 m) es
    resistido por muros M001..M004 (no materializados), de modo que su grilla
    de vigas no esta anclada a ninguna columna que llegue a B1. Aqui se
    cuantifican esos nodos "flotantes" (dependientes del muro).
    """
    zl = builder.level_tags
    base_k = set()
    for tag in builder._expectations["support_tags"]:
        base_k.add(builder.tag_to_key[tag])

    # grafo de continuidad estructural via vigas y columnas
    from collections import defaultdict, deque
    adj = defaultdict(list)
    def link(a, b):
        if a != b:
            adj[a].append(b)
            adj[b].append(a)
    # columnas (continuidad vertical) y vigas (plano)
    sup = set(builder.structural_tags)
    for e_ in builder.elems["columns"]:
        if e_["n1"] in sup and e_["n2"] in sup:
            link(builder.tag_to_key[e_["n1"]], builder.tag_to_key[e_["n2"]])
    for e_ in builder.elems["beams"]:
        if e_["n1"] in sup and e_["n2"] in sup:
            link(builder.tag_to_key[e_["n1"]], builder.tag_to_key[e_["n2"]])

    nodes = {builder.tag_to_key[t] for t in builder.structural_tags}
    seen = set()
    dq = deque(base_k)
    while dq:
        n = dq.popleft()
        if n in seen:
            continue
        seen.add(n)
        for m in adj[n]:
            if m not in seen:
                dq.append(m)
    floating = sorted(nodes - seen)
    return floating, _pt, base_k


def build_and_apply():
    """Modelo (builder) + patron de cargas punto sobre vigas L1-L4."""
    builder = ModelBuilder()
    report = builder.run()

    points, _ = gravity_loads.build_point_loads()
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    n_loads = 0
    for row in points.itertuples(index=False):
        ops.eleLoad("-ele", int(row.element_tag), "-type", "-beamPoint",
                    0.0, -float(row.load_kN), float(row.xloc))
        n_loads += 1

    applied_total = float(points["load_kN"].sum())
    n_beams = int(points.beam_id.nunique())
    return builder, report, applied_total, n_beams, int(n_loads)


def run(builder):
    """Analisis estatico lineal. Devuelve (rc, reactions_df, disp_df)."""
    ops.system("BandGeneral")
    ops.numberer("RCM")
    # constraints() ya configurado por el builder (Transformation)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    rc = ops.analyze(1)

    support_tags = builder._expectations["support_tags"]

    react_rows = []
    if rc == 0:
        ops.reactions()
        for tag in sorted(support_tags):
            x, y, z = builder.tag_to_key[tag]
            rx = ops.nodeReaction(tag, 1)
            ry = ops.nodeReaction(tag, 2)
            rz = ops.nodeReaction(tag, 3)
            react_rows.append({
                "node_tag": tag,
                "x_m": x, "y_m": y, "z_m": z,
                "Rx_kN": round(rx, 6), "Ry_kN": round(ry, 6),
                "Rz_kN": round(rz, 6),
            })
    reactions = pd.DataFrame(react_rows)

    master_coords = {builder.master_tag_by_id[r.master_id]:
                     (r.x_m, r.y_m, r.z_m) for r in builder.masters.itertuples()}
    coord_map = dict(builder.tag_to_key)
    coord_map.update(master_coords)

    disp_rows = []
    all_tags = sorted(builder.structural_tags) + sorted(builder.master_tags)
    for tag in all_tags:
        x, y, z = coord_map[tag]
        if rc != 0:
            ux = uy = uz = np.nan
        else:
            ux = ops.nodeDisp(tag, 1)
            uy = ops.nodeDisp(tag, 2)
            uz = ops.nodeDisp(tag, 3)
        disp_rows.append({
            "node_tag": tag,
            "x_m": x, "y_m": y, "z_m": z,
            "ux_m": round(ux, 9), "uy_m": round(uy, 9), "uz_m": round(uz, 9),
            "is_master": tag in builder.master_tags,
        })
    displacements = pd.DataFrame(disp_rows)
    return rc, reactions, displacements


def master_verbose(builder, displacements):
    out = {}
    for r in builder.masters.itertuples():
        tag = builder.master_tag_by_id[r.master_id]
        d = displacements[displacements.node_tag == tag].iloc[0]
        out[r.master_id] = dict(
            tag=tag,
            ux_m=d["ux_m"], uy_m=d["uy_m"], uz_m=d["uz_m"],
            level=r.master_id)
    return out


def write_report(builder, report, points, rc, reactions, disp,
                 applied_total, n_beams, n_loads):
    expected_total = float(gravity_loads.expected_beam_loads()
                           ["total_slab_load_kN"].sum())
    n_supports = len(reactions) if rc == 0 else len(builder._expectations[
        "support_tags"])

    sum_rz = float(reactions["Rz_kN"].sum()) if rc == 0 else np.nan
    abs_diff = abs(sum_rz - applied_total) if rc == 0 else np.nan
    rel_err = (abs_diff / max(applied_total, 1e-12)) if rc == 0 else np.nan

    if rc == 0:
        uz = disp.loc[disp.is_master == False, "uz_m"].to_numpy()
        i_max = int(np.argmax(np.abs(uz)))
        row = disp.loc[disp.is_master == False].iloc[i_max]
        uz_max = float(row["uz_m"])
        node_uz = int(row["node_tag"])
        masters = master_verbose(builder, disp)
    else:
        uz_max = np.nan
        node_uz = None
        masters = {r.master_id: {"tag": None, "ux_m": np.nan,
                                 "uy_m": np.nan, "uz_m": np.nan}
                   for r in builder.masters.itertuples()}

    lines = []
    add = lines.append
    add("# Analisis gravitacional LT2 (BLOQUE 3)")
    add("")
    add("## Resumen")
    add("")
    add(f"- return_code (ops.analyze): **{rc}**"
        + ("  -> convergió" if rc == 0 else "  -> NO convergió (posible "
          "inestabilidad real; revise mecanismos sin muros)"))
    add(f"- Carga total aplicada (vigas L1-L4, areas tributarias): "
        f"**{applied_total:.6f} kN**")
    add(f"- Carga esperada (beam_gravity_loads_LT2.csv): "
        f"**{expected_total:.6f} kN**")
    if rc == 0:
        add(f"- Suma de reacciones verticales |ΣRz|: **{sum_rz:.6f} kN** "
            f"en {n_supports} apoyos")
        add(f"- Diferencia absoluta: **{abs_diff:.6e} kN**")
        add(f"- Error relativo de equilibrio: **{rel_err:.3e}**")
        add(f"- |Uz| máxima (nodos estructurales): **{uz_max:.6f} m** "
            f"en nodo {node_uz}")
    else:
        add("- Reacciones/desplazamientos no disponibles (análisis falló).")
    add("")
    if rc != 0:
        floating, _pt, _ = diagnose_mechanisms(builder)
        add("## Diagnostico de no convergencia")
        add("")
        add("- El sistema es **singular** (return_code = -3): el modelo sin "
           "muros no es autoportante en la direccion vertical fuera del plano.")
        add(f"- Nodos estructurales sin camino al empotramiento B1 por el "
           f"portico (solo via muros): **{len(floating)}** de "
           f"{builder._expectations['expected']['structural_nodes']}.")
        if floating:
            add("- Estos nodos corresponden al bloque OESTE/nucleo (bordes x=0.4 "
               "y lineas V40/V30) y la malla del ala norte/sur, resistida por "
               "muros M001..M004 que **no estan materializados** "
               "(pendiente definido en el proyecto).")
            add(f"- Ejemplos: {_pt(*floating[0])}, {_pt(*floating[1])} ...")
        add("- No se anadieron restricciones ni muros arbitrarios: se reporta "
           "la inestabilidad tal como esta, sin ocultar el mecanismo.")
    add("")
    add("## Cargas aplicadas")
    add("")
    add(f"- Fuente: `data/loads/tributary_areas_LT2.csv` "
        f"(receiver_type=BEAM, L1-L4).")
    add(f"- Representación: `eleLoad -beamPoint`, franjas de {gravity_loads.STEP} m "
        "a lo largo de cada viga; fuerza total y primer momento conservados "
        "exactamente (`results/gravity_loads_applied_LT2.csv`).")
    add(f"- Vigas con carga: {n_beams}; puntos de carga: {n_loads}.")
    add("- Excluidas: ROOF, carga lineal ROOF 1500 kg/m, "
        "WALL_EDGE_PENDING (24 áreas de muro, 638.4139 kN), SC.")
    add("")
    add("## Modelo")
    add("")
    add(f"- Nodos: {report['actual']['total_nodes']} "
        f"(estructurales {report['actual']['structural_nodes']}, "
        f"masters {report['actual']['masters']}).")
    add(f"- Elementos: vigas materializadas {report['actual']['beams']}, "
        f"columnas {report['actual']['columns']}; muros pendientes "
        f"({report['expected']['walls']}).")
    add(f"- Diafragmas rígidos (UX,UY,RZ) con Transformation: "
        f"{report['slaves_per_level']}.")
    add(f"- Material: {report['material_params']['material_id']} "
        f"E={report['material_params']['E_kN_m2']:.3g} kN/m², "
        f"nu={report['material_params']['nu']}, "
        f"G={report['material_params']['G_kN_m2']:.3g} kN/m²")
    add("")
    add("## Reacciones por apoyo")
    add("")
    if rc == 0:
        for _, r in reactions.sort_values("node_tag").iterrows():
            add(f"- nodo {int(r.node_tag)} ({r['x_m']:.3f}, {r['y_m']:.3f}, "
                f"{r['z_m']:.3f}): Rz = {r['Rz_kN']:.6f} kN "
                f"(Rx={r['Rx_kN']:.6f}, Ry={r['Ry_kN']:.6f})")
    add("")
    add("## Desplazamientos de masters")
    add("")
    for mid, d in masters.items():
        add(f"- {mid} (tag {d['tag']}): ux={d['ux_m']:.9f} m, "
            f"uy={d['uy_m']:.9f} m, uz={d['uz_m']:.9f} m")
    add("")
    add("## Archivos")
    add("")
    add(f"- `results/gravity_loads_applied_LT2.csv`")
    add(f"- `results/gravity_loads_beam_summary_LT2.csv`")
    add(f"- `results/gravity_reactions_LT2.csv`")
    add(f"- `results/gravity_displacements_LT2.csv`")
    add(f"- `figures/gravity_loads_L1.png`")
    add("")
    REP.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dict(return_code=rc, P=applied_total, Rz=sum_rz,
                abs_diff=abs_diff, rel_err=rel_err,
                uz_max=uz_max, node_uz=node_uz, n_beams=n_beams,
                n_loads=n_loads)

def main():
    builder, report, applied_total, n_beams, n_loads = build_and_apply()
    rc, reactions, disp = run(builder)
    RES.mkdir(parents=True, exist_ok=True)
    if rc == 0:
        reactions.to_csv(OUT_REACT, index=False)
    disp.to_csv(OUT_DISP, index=False)
    summary = write_report(builder, report, None, rc, reactions, disp,
                           applied_total, n_beams, n_loads)
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"{k:12s} = {v:.9g}")
        else:
            print(f"{k:12s} = {v}")
    if rc != 0:
        print("ATENCION: analisis no convergio; ver reporte. No se ocultan "
              "posibles mecanismos estructurales.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())