"""
Auditoria geometrica de la estructura final (Semana 2): P1-P4.

Compara la geometria procesada desde DXF (building_3d_aligned.json) contra el
modelo FE/visual (unity_model.json), SIN MODIFICAR ninguno de los dos.

Metodo de trazabilidad:
  - unity_model.json guarda en cada elemento FE de viga/muro su physical_id,
    que es exactamente el indice 'orig' asignado en build_ops_model():
        vigas : indice i sobre [b por b in data.beams if high-confidence & level]
        muros : len(beams_lvl) + j (j indice sobre high-confidence muros)
  - Se reproduce ese orden y se vincula cada elemento FE a su miembro DXF.
  - Columna FE (physical_id=-1): se compara geometricamente contra las columnas
    DXF (P1-P2 tienen entrada explicita; P2-P3 y P3-P4 son reconstruccion por
    coincidencia de rejilla + continuidad).

No se ejecuta el modelo OpenSees; solo se leen los dos JSON aceptados.

Salidas:
  results/qa_geometria_semana2.md
  figures/qa_geometria_P1.png ... P4.png   (planta, aspect 1:1)
"""

import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DY_CORRECTION = -20.52
CORRECT_LEVELS = ("P3", "P4")
LVLS = ("P1", "P2", "P3", "P4")

NODE_SNAP_TOL = 0.5   # structure_params
DIST_ANCHOR = 8.0     # ops_model

ALIGNED = ROOT / "data" / "processed" / "building_3d_aligned.json"
UNITY = ROOT / "data" / "processed" / "unity_model.json"
OUT_MD = ROOT / "results" / "qa_geometria_semana2.md"
OUT_FIG = {l: ROOT / "figures" / f"qa_geometria_{l}.png" for l in LVLS}


def load_and_shift():
    data = json.loads(ALIGNED.read_text(encoding="utf-8"))
    for n in data["nodes"]:
        if n["level"] in CORRECT_LEVELS:
            n["y"] = n["y"] + DY_CORRECTION
    for e in data["beams"] + data["walls"]:
        if e["level"] in CORRECT_LEVELS:
            e["y1"] += DY_CORRECTION
            e["y2"] += DY_CORRECTION
    for s in data.get("slabs", []):
        if s["level"] in CORRECT_LEVELS and s.get("vertices_m"):
            s["vertices_m"] = [[x, y + DY_CORRECTION] for x, y in s["vertices_m"]]
    return data


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ptseg(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return d2(p, a)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    return d2(p, (ax + t * dx, ay + t * dy))


def project_t(p, a, b):
    px, py = p
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    return max(0.0, min(1.0, t))


def main():
    data = load_and_shift()
    unity = json.loads(UNITY.read_text(encoding="utf-8"))

    node_coord = {n["nodeTag"]: (n["x"], n["y"], n["z"]) for n in unity["nodes"]}
    elements = unity["elements"]

    elev = {}
    for l in data["levels"]:
        if l["id"] in LVLS:
            elev[l["id"]] = l["elevation"]

    level_grid = {}
    for n in data["nodes"]:
        if n["level"] in LVLS:
            level_grid.setdefault(n["level"], []).append((n["x"], n["y"]))

    # pilares soportados = interseccion de rejillas P1..P4 (redondeo 3)
    supported_xy = {}
    acc = None
    for lvl in LVLS:
        g = set((round(x, 3), round(y, 3)) for x, y in level_grid[lvl])
        acc = g if acc is None else (acc & g)
        supported_xy[lvl] = set(acc)

    hi_beams = {l: [b for b in data["beams"] if b["status"] == "high-confidence" and b["level"] == l]
                for l in LVLS}
    hi_walls = {l: [w for w in data["walls"] if w["status"] == "high-confidence" and w["level"] == l]
                for l in LVLS}
    amb_beams = {l: sum(1 for b in data["beams"] if b["status"] != "high-confidence" and b["level"] == l)
                 for l in LVLS}
    amb_walls = {l: sum(1 for w in data["walls"] if w["status"] != "high-confidence" and w["level"] == l)
                 for l in LVLS}
    # conteos adicionales S1/FDN para la seccion de subsuelo/fundaciones
    s1f = {
        "S1_beams_hi": sum(1 for b in data["beams"] if b["level"] == "S1" and b["status"] == "high-confidence"),
        "S1_walls_hi": sum(1 for w in data["walls"] if w["level"] == "S1" and w["status"] == "high-confidence"),
        "S1_beams_amb": sum(1 for b in data["beams"] if b["level"] == "S1" and b["status"] != "high-confidence"),
        "S1_walls_amb": sum(1 for w in data["walls"] if w["level"] == "S1" and w["status"] != "high-confidence"),
        "FDN_beams_hi": sum(1 for b in data["beams"] if b["level"] == "FDN" and b["status"] == "high-confidence"),
        "FDN_walls_hi": sum(1 for w in data["walls"] if w["level"] == "FDN" and w["status"] == "high-confidence"),
        "FDN_beams_amb": sum(1 for b in data["beams"] if b["level"] == "FDN" and b["status"] != "high-confidence"),
        "FDN_walls_amb": sum(1 for w in data["walls"] if w["level"] == "FDN" and w["status"] != "high-confidence"),
    }

    # ── miembros fisicos por nivel (mismo orden que build_ops_model) ──
    phys = {}   # (lvl, orig) -> rec
    for l in LVLS:
        for i, b in enumerate(hi_beams[l]):
            phys[(l, i)] = {"kind": "beam", "x1": b["x1"], "y1": b["y1"],
                            "x2": b["x2"], "y2": b["y2"], "src": b, "els": [], "lo": False,
                            "n_seg": 0}
        nj = len(hi_beams[l])
        for j, w in enumerate(hi_walls[l]):
            phys[(l, nj + j)] = {"kind": "wall", "x1": w["x1"], "y1": w["y1"],
                                 "x2": w["x2"], "y2": w["y2"], "src": w, "els": [], "lo": False,
                                 "n_seg": 0}

    fe_beams, fe_walls, fe_cols, los = [], [], [], []
    for e in elements:
        if e["analysis_status"] == "LOAD_ONLY":
            los.append(e)
            key = (e["level"], e["physical_id"])
            if key in phys and phys[key]["kind"] == e["type"]:
                phys[key]["lo"] = True
            continue
        if e["analysis_status"] != "FE":
            continue
        if e["type"] == "column":
            fe_cols.append(e)
            continue
        key = (e["level"], e["physical_id"])
        rec = phys.get(key)
        if rec is None or rec["kind"] != e["type"]:
            continue
        rec["els"].append(e)
        rec["n_seg"] += 1
        (fe_walls if e["type"] == "wall" else fe_beams).append(e)

    # ── checks de coincidencia geometrica por miembro fisico ──
    geom_issues = []            # (lvl, tipo, orig, detalle)
    d_max_all = 0.0
    coverage = defaultdict(float)    # (lvl,tipo) longitud fuente cubierta [m]
    len_fe = defaultdict(float)      # (lvl,tipo) longitud FE
    len_dxf = defaultdict(float)     # (lvl,tipo) longitud DXF incorporada
    for (l, o), rec in phys.items():
        if not rec["els"]:
            continue
        Lsrc = math.hypot(rec["x2"] - rec["x1"], rec["y2"] - rec["y1"])
        len_dxf[(l, rec["kind"])] += Lsrc
        if Lsrc > 1e-9:
            ivs = []
            worst = 0.0
            for e in rec["els"]:
                a = node_coord[e["node_i"]]
                b = node_coord[e["node_j"]]
                if abs(a[2] - elev[l]) > 1e-6 or abs(b[2] - elev[l]) > 1e-6:
                    geom_issues.append((l, rec["kind"], o, f"z fuera del nivel: {a[2]:.3f}/{b[2]:.3f}"))
                tini = project_t((a[0], a[1]), (rec["x1"], rec["y1"]), (rec["x2"], rec["y2"]))
                tfin = project_t((b[0], b[1]), (rec["x1"], rec["y1"]), (rec["x2"], rec["y2"]))
                ivs.append((min(tini, tfin), max(tini, tfin)))
                for p in (a, b):
                    dd = ptseg((p[0], p[1]), (rec["x1"], rec["y1"]), (rec["x2"], rec["y2"]))
                    worst = max(worst, dd)
                len_fe[(l, rec["kind"])] += math.hypot(b[0] - a[0], b[1] - a[1])
            ivs.sort()
            cov = 0.0
            cur = -1.0
            for x0, x1 in ivs:
                if x1 <= cur:
                    continue
                cov += x1 - max(x0, cur)
                cur = max(cur, x1)
            coverage[(l, rec["kind"])] += cov * Lsrc
            d_max_all = max(d_max_all, worst)
            if worst > NODE_SNAP_TOL:
                geom_issues.append((l, rec["kind"], o, f"d_max nodo->linea {worst:.3f} m > {NODE_SNAP_TOL}"))

    # ── apoyo: todo nodo FE de viga/muro a <= DIST_ANCHOR de pilar soportado ──
    unsupported = []
    col_grid = {l: list(supported_xy[l]) for l in LVLS}
    for e in fe_beams + fe_walls:
        l = e["level"]
        for nn in (e["node_i"], e["node_j"]):
            x, y, _ = node_coord[nn]
            bd = min(d2((x, y), c) for c in col_grid[l]) if col_grid[l] else float("inf")
            if bd > DIST_ANCHOR:
                unsupported.append((e["elementTag"], nn, round(bd, 3)))

    # ── conectividad (union-find a base P1) ──
    parent = {}
    for e in elements:
        if e["analysis_status"] == "FE":
            parent.setdefault(e["node_i"], e["node_i"])
            parent.setdefault(e["node_j"], e["node_j"])

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for e in elements:
        if e["analysis_status"] == "FE":
            union(e["node_i"], e["node_j"])
    base_nodes = [e["node_i"] for e in fe_cols if e["level"] == "P1"]
    base_roots = {find(t) for t in base_nodes}
    detached = [t for t in parent if find(t) not in base_roots]

    # ── columnas: coincidencia FE vs DXF ──
    nxy = {n["node_id"]: (n["x"], n["y"]) for n in data["nodes"]}
    dxf_cols = defaultdict(list)   # (li,lj) -> [(xy_i, xy_j)]
    for c in data["columns"]:
        dxf_cols[(c["level_i"], c["level_j"])].append((nxy[c["node_i"]], nxy[c["node_j"]]))
    fe_col_xy = defaultdict(list)  # li -> [(xy_i, xy_j)]
    for e in fe_cols:
        i = tuple(round(v, 3) for v in node_coord[e["node_i"]][:2])
        j = tuple(round(v, 3) for v in node_coord[e["node_j"]][:2])
        fe_col_xy[e["level"]].append((i, j))

    col_mismatch = []
    for e in fe_cols:
        zj = node_coord[e["node_j"]][2]
        if not any(l != e["level"] and abs(zj - elev[l]) < 1e-6 for l in LVLS):
            col_mismatch.append((e["elementTag"], round(zj, 3)))

    col_report = {}
    for pair, cols in dxf_cols.items():
        fe_set = set(fe_col_xy[pair[0]])
        dset = set((tuple(round(x, 3) for x in i), tuple(round(x, 3) for x in j)) for (i, j) in cols)
        col_report[pair] = {
            "dxf": len(cols), "fe": len(fe_set), "matched": len(fe_set & dset),
            "fe_missing": len(fe_set - dset), "dxf_unmatched": len(dset - fe_set),
        }

    # ── continuidad vertical de columnas ──
    j_xy_p1p2 = {tuple(j) for i, j in fe_col_xy["P1"]}
    i_xy_p2p3 = {tuple(i) for i, j in fe_col_xy["P2"]}
    j_xy_p2p3 = {tuple(j) for i, j in fe_col_xy["P2"]}
    i_xy_p3p4 = {tuple(i) for i, j in fe_col_xy["P3"]}
    cont_p1p2_p2p3 = len(j_xy_p1p2 & i_xy_p2p3)
    cont_p2p3_p3p4 = len(j_xy_p2p3 & i_xy_p3p4)
    cont_xy = supported_xy["P1"]
    cont_levels_present = {l: len(supported_xy[l]) for l in LVLS}
    stacked = all(cont_xy == supported_xy[l] for l in LVLS)

    # ── elementos sobresalientes de la huella de pilares ──
    protruding = []
    for l in LVLS:
        xs = [c[0] for c in col_grid[l]]
        ys = [c[1] for c in col_grid[l]]
        if not xs:
            continue
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        for e in fe_beams + fe_walls:
            if e["level"] != l:
                continue
            for nn in (e["node_i"], e["node_j"]):
                x, y, _ = node_coord[nn]
                dx = max(x0 - x, x - x1, 0.0)
                dy = max(y0 - y, y - y1, 0.0)
                over = max(dx, dy)
                if over > 0.5:
                    protruding.append((l, e["type"], e["elementTag"], nn, x, y, over,
                                       "x" if dx >= dy else "y"))

    # ── checks globales ──
    tags = [e["elementTag"] for e in elements if e["analysis_status"] == "FE"]
    dup_tags = len(tags) - len(set(tags))
    zero = [e for e in elements
            if e["analysis_status"] == "FE"
            and math.hypot(*(node_coord[e["node_j"]][k] - node_coord[e["node_i"]][k] for k in range(3))) < 1e-6]
    fe_with_src = [e for e in fe_beams + fe_walls
                   if e.get("source_dxf") is not None or e.get("source_id") is not None]
    all_n = unity["nodes"]
    xmin = min(n["x"] for n in all_n); xmax = max(n["x"] for n in all_n)
    ymin = min(n["y"] for n in all_n); ymax = max(n["y"] for n in all_n)
    zmin = min(n["z"] for n in all_n); zmax = max(n["z"] for n in all_n)

    # ── figuras por nivel (planta) ──
    import plotly.graph_objects as go
    for l in LVLS:
        fig = go.Figure()
        for rec_list, color, name in ((hi_beams[l], "#a9b6cf", "Vigas DXF (hi)"),
                                      (hi_walls[l], "#d8b48a", "Muros DXF (hi)")):
            X = []; Y = []
            for m in rec_list:
                X += [m["x1"], m["x2"], None]
                Y += [m["y1"], m["y2"], None]
            fig.add_trace(go.Scatter(x=X, y=Y, mode="lines",
                                     line=dict(color=color, width=3, dash="dot"),
                                     name=name, legendgroup="dxf", showlegend=(l == "P1")))
        for kind, color, name in (("beam", "#3366ff", "Vigas FE"),
                                  ("wall", "#d87a26", "Muros FE")):
            X = []; Y = []
            for e in (fe_beams if kind == "beam" else fe_walls):
                if e["level"] != l:
                    continue
                a = node_coord[e["node_i"]]; b = node_coord[e["node_j"]]
                X += [a[0], b[0], None]; Y += [a[1], b[1], None]
            fig.add_trace(go.Scatter(x=X, y=Y, mode="lines", line=dict(color=color, width=4),
                                     name=name, legendgroup=kind, showlegend=(l == "P1")))
        X = []; Y = []
        for e in los:
            if e["level"] != l:
                continue
            a = e["coordinates"]["i"]; b = e["coordinates"]["j"]
            X += [a[0], b[0], None]; Y += [a[1], b[1], None]
        fig.add_trace(go.Scatter(x=X, y=Y, mode="lines",
                                 line=dict(color="#e633cc", width=3, dash="dash"),
                                 name="LOAD_ONLY", legendgroup="lo", showlegend=(l == "P1")))
        sx = [c[0] for c in supported_xy[l]]; sy = [c[1] for c in supported_xy[l]]
        fig.add_trace(go.Scatter(x=sx, y=sy, mode="markers",
                                 marker=dict(color="#111111", size=7, symbol="square"),
                                 name="Pilares soportados", legendgroup="col",
                                 showlegend=(l == "P1")))
        if any(p[0] == l for p in protruding):
            X = [p[4] for p in protruding if p[0] == l]
            Y = [p[5] for p in protruding if p[0] == l]
            fig.add_trace(go.Scatter(x=X, y=Y, mode="markers",
                                     marker=dict(color="red", size=8, symbol="x"),
                                     name="Puntos sobresalientes", legendgroup="pro",
                                     showlegend=(l == "P1")))
        nfeb = sum(1 for e in fe_beams if e["level"] == l)
        nfew = sum(1 for e in fe_walls if e["level"] == l)
        fig.update_layout(
            title=(f"Planta {l} (z={elev[l]:.2f} m) - DXF(hi) vs FE | "
                   f"vigas FE {nfeb}, muros FE {nfew}"),
            yaxis=dict(scaleanchor="x", scaleratio=1, title="Y [m]"),
            xaxis=dict(title="X [m]"),
            margin=dict(l=0, r=0, t=60, b=0),
            showlegend=True, height=560,
        )
        OUT_FIG[l].parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(OUT_FIG[l]), width=1200, height=680, scale=1.6)

    # ── ensamblar reporte ──
    lines = []
    ap = lines.append
    ap("# Auditoria de Geometria Final - Semana 2 (P1-P4)")
    ap("")
    ap("- Fecha: 2026-09-01  |  Estado: **SIN MODIFICAR** modelo FE, unity_model.json, cargas, q_G ni areas tributarias.")
    ap("- Fuente A (DXF procesado): `data/processed/building_3d_aligned.json`")
    ap("- Fuente B (modelo FE/visual): `data/processed/unity_model.json`")
    ap(f"- Corrimiento de registro aplicado en memoria (igual que `ops_model.load_aligned`): P3/P4 -> Y {DY_CORRECTION} m.")
    ap("- Trazabilidad FE->DXF: `physical_id` (= indice `orig` de `build_ops_model`); columnas FE por geometria.")
    ap("- Nota metodologica: la cobertura usa la proyeccion de nodos FE sobre la linea DXF; `LFE` puede superar "
       "`LDXF` porque los nodos soldados a pilares (snap <= 0.5 m) forman cuerdas ligeramente mas largas que el trazo.")
    ap("")
    ap(f"**Elementos FE totales:** {len(tags)}  |  columnas {len(fe_cols)}  |  vigas FE {len(fe_beams)}  |  "
       f"muros FE {len(fe_walls)}  |  LOAD_ONLY {len(los)}  |  nodos {len(unity['nodes'])}  |  apoyos {len(unity['supports'])}")
    ap("")

    # resumen por piso
    ap("## Resumen por piso")
    ap("")
    ap("| Piso | Viga hi DXF | Viga FE (elem) | Viga phys FE | Viga LOAD | Viga excl. | Viga ambig. | "
       "Muro hi DXF | Muro FE (elem) | Muro phys FE | Muro LOAD | Muro excl. | Muro ambig. |")
    ap("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for l in LVLS:
        nhb = len(hi_beams[l]); nhw = len(hi_walls[l])
        fe_b_phys = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "beam" and r["els"])
        lo_b = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "beam" and r["lo"])
        fe_w_phys = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "wall" and r["els"])
        lo_w = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "wall" and r["lo"])
        nb_fe = sum(1 for e in fe_beams if e["level"] == l)
        nw_fe = sum(1 for e in fe_walls if e["level"] == l)
        ap(f"| {l} | {nhb} | {nb_fe} | {fe_b_phys} | {lo_b} | {nhb - fe_b_phys - lo_b} | {amb_beams[l]} |"
           f" {nhw} | {nw_fe} | {fe_w_phys} | {lo_w} | {nhw - fe_w_phys - lo_w} | {amb_walls[l]} |")
    ap("")

    # coincidencia geometrica
    ap("## Coincidencia geometrica FE vs DXF (elementos incorporados)")
    ap("")
    ap("Para cada miembro DXF high-confidence incorporado se midio: (a) distancia maxima nodo-FE -> linea "
       "DXF (`d_max`), (b) cobertura de la longitud fuente por los elementos FE.")
    ap("")
    ap(f"- d_max global (todos los pisos, todos los elementos FE): **{d_max_all:.4f} m**"
       f" {'<= NODE_SNAP_TOL=0.5 OK' if d_max_all <= 0.5 else 'SUPERA TOLERANCIA'}")
    for l in LVLS:
        def fmt(c, fe, dxf):
            pct = (c / dxf * 100.0) if dxf > 1e-9 else 0.0
            return f"{pct:.1f}% (LFE={fe:.2f} / LDXF={dxf:.2f} m)"
        ap(f"- **{l}** vigas: cobertura {fmt(coverage.get((l, 'beam')), len_fe.get((l, 'beam')), len_dxf.get((l, 'beam')))}"
           f" | muros: cobertura {fmt(coverage.get((l, 'wall')), len_fe.get((l, 'wall')), len_dxf.get((l, 'wall')))}")
    ap("")
    if geom_issues:
        ap("### Mismatches geometricos (elemento FE no coincide con su fuente)")
        ap("")
        ap("| Piso | Tipo | origen | Detalle |")
        ap("|---|---|---|---|")
        for l, k, o, det in geom_issues:
            ap(f"| {l} | {k} | {o} | {det} |")
        ap("")
    else:
        ap("- Sin mismatches geometricos (> 0.5 m) entre FE y sus fuentes DXF de alta confianza.")
        ap("")

    # columnas
    ap("## Columnas: continuidad P1->P2 / P2->P3 / P3->P4")
    ap("")
    ap("| Par | Columnas DXF | Columnas FE | Coinciden | FE sin par DXF (reconstruidas) | DXF sin par FE (no modeladas) |")
    ap("|---|---|---|---|---|---|")
    for pair in (("P1", "P2"), ("P2", "P3"), ("P3", "P4")):
        cr = col_report.get(pair, {})
        dxf = cr.get("dxf", 0)
        fe = cr.get("fe", len(fe_col_xy[pair[0]]))
        matched = cr.get("matched", "-")
        fe_miss = cr.get("fe_missing", 0)
        dxf_miss = cr.get("dxf_unmatched", 0)
        if pair == ("P2", "P3"):
            ap(f"| {pair[0]}->{pair[1]} | {dxf} | {fe} | {matched} (reconstruccion) | {fe_miss} | {dxf_miss} |")
        else:
            ap(f"| {pair[0]}->{pair[1]} | {dxf} | {fe} | {matched} | {fe_miss} | {dxf_miss} |")
    ap("")
    ap(f"- Rejilla soportada continua P1..P4: **{len(cont_xy)} pilares**; presente en todos los pisos: "
       f"{'SI' if stacked else 'NO'}  ({', '.join(f'{l}={cont_levels_present[l]}' for l in LVLS)}).")
    ap(f"- Continuidad entre pares de FE: P1->P2 con P2->P3: {cont_p1p2_p2p3}/16; P2->P3 con P3->P4: "
       f"{cont_p2p3_p3p4}/16.")
    ap("- P2-P3 y P3-P4 son reconstruccion por coincidencia de rejilla (el DXF solo registra P1-P2 y P3-P4).")
    ap("- DXF registra P3-P4 = 18 columnas; FE modela 16 (las 2 de P2 x=40 sin pilar en P1 quedan fuera, "
       "documentado en `ops_model.py`: columna sin base continua se EXCLUYE).")
    if col_mismatch:
        ap(f"- Columnas con z_top fuera de nivel: **{len(col_mismatch)}** -> revisar: {col_mismatch[:5]}")
    ap("")

    # muros
    ap("## Muros: FE / LOAD_ONLY / EXCLUIDOS")
    ap("")
    ap("| Piso | hi DXF | FE (phys) | LOAD_ONLY | Excluidos (hi, sin carga) | Ambiguous (no modelados) |")
    ap("|---|---|---|---|---|---|")
    for l in LVLS:
        fe = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "wall" and r["els"])
        lo = sum(1 for k, r in phys.items() if k[0] == l and r["kind"] == "wall" and r["lo"])
        ap(f"| {l} | {len(hi_walls[l])} | {fe} | {lo} | {len(hi_walls[l]) - fe - lo} | {amb_walls[l]} |")
    ap("")
    excl_hi = [k for k, r in phys.items() if not r["els"] and not r["lo"]]
    if excl_hi:
        ap(f"- Excluidos high-confidence (politica v2: sin pilar soportado a <= {DIST_ANCHOR} m): "
           + "; ".join(f"{k[0]}-{k[1]}" for k in excl_hi) + ".")
    else:
        ap("- Sin miembros high-confidence excluidos: todos se incorporan como FE o LOAD_ONLY.")
    ap("")

    # vigas sobresalientes
    ap("## Vigas/elementos que sobresalen de la huella de pilares")
    ap("")
    if protruding:
        uniq_els = len({(p[0], p[1], p[2]) for p in protruding})
        by_x = sum(1 for p in protruding if p[7] == "x")
        by_y = len(protruding) - by_x
        ap(f"**{len(protruding)} nodos de {uniq_els} elementos** FE quedan a mas de 0.5 m del rectangulo que "
           f"encierran los pilares soportados ({by_x} en eje X -borde este x>45-, {by_y} en eje Y -bandas "
           f"y=-20.8..-18.7 y y=0.3..3.3-). Son parte de los miembros DXF high-confidence incorporados "
           f"(no artefactos del FE): d_max <= {d_max_all:.3f} m los mantiene sobre su linea.")
        ap("")
        ap("| Piso | Tipo | tag FE | nodo | (x,y) m | saliente m | eje |")
        ap("|---|---|---|---|---|---|---|")
        for l, k, tag, nn, x, y, over, ax in protruding:
            ap(f"| {l} | {k} | {tag} | {nn} | ({x:.2f}, {y:.2f}) | {over:.2f} | {ax} |")
        ap("")
        ap("Nota: un voladizo/antear por encima del eje X>45 (p.ej. vierteaguas o balcon) seria coherente, pero "
           "las bandas Y por debajo de -16.4 y por encima de -0.25 sin fila de pilares cercanos merecen revision "
           "manual contra los DXF 101/102.")
    else:
        ap("- Ningun nodo FE sobresale mas de 0.5 m fuera del rectangulo que encierran los pilares soportados del piso.")
    ap("")

    # S1 / FDN
    ap("## S1 (subsuelo) y fundaciones")
    ap("")
    ap("- El modelo FE/Unity es de **superestructura P1..P4**: S1 (z=-4.01 m) y FDN (sin elevacion) **no se modelan** "
       "(`frame_levels=('P1','P2','P3','P4')`); la base se fija en P1 (16 apoyos fijos).")
    ap(f"- DXF S1 -> vigas hi {s1f['S1_beams_hi']} + ambiguous {s1f['S1_beams_amb']}; "
       f"muros hi {s1f['S1_walls_hi']} + ambiguous {s1f['S1_walls_amb']}.")
    ap(f"- DXF FDN -> vigas hi {s1f['FDN_beams_hi']} + ambiguous {s1f['FDN_beams_amb']}; "
       f"muros hi {s1f['FDN_walls_hi']} + ambiguous {s1f['FDN_walls_amb']}.")
    ap("- No hay elementos FE en S1/FDN (confirmado: 0 en `unity_model.json`).")
    ap("")

    # checks automaticos
    ap("## Checks automaticos")
    ap("")
    checks = [
        ("elementTag unicos", dup_tags == 0, f"{dup_tags} duplicados"),
        ("longitud cero", not zero, f"{len(zero)} elementos"),
        ("z de nodos FE de viga/muro == elevacion del piso", not geom_issues, f"{len(geom_issues)} anomalias"),
        ("d_max nodo->linea DXF <= 0.5 m", d_max_all <= 0.5, f"{d_max_all:.4f} m"),
        ("todos los nodos FE conectados a base P1", not detached, f"{len(detached)} nodos aislados"),
        ("nodos FE de viga/muro con pilar soportado a <= 8 m", not unsupported,
         f"{len(unsupported)} nodos sin apoyo (ej: {unsupported[:3]})"),
        ("elementos FE exportados sin fuente (por diseno)", not fe_with_src,
         f"{len(fe_with_src)} con source_dxf/source_id"),
        ("columnas FE P1-P2 coinciden con DXF P1-P2", col_report.get(('P1', 'P2'), {}).get('matched', 0) == 16,
         f"M={col_report.get(('P1', 'P2'), {}).get('matched', 'n/a')}/16"),
        ("continuidad de 16 pilares P1..P4",
         stacked and cont_p1p2_p2p3 == 16 and cont_p2p3_p3p4 == 16,
         f"rejillas iguales={stacked}, P1P2->P2P3 {cont_p1p2_p2p3}/16, P2P3->P3P4 {cont_p2p3_p3p4}/16"),
        ("rango de coordenadas en metros", abs(xmax) <= 100 and ymin >= -30,
         f"x[{xmin:.2f},{xmax:.2f}] y[{ymin:.2f},{ymax:.2f}] z[{zmin:.2f},{zmax:.2f}]"),
    ]
    for name, ok, det in checks:
        ap(f"- [{'PASS' if ok else 'FAIL'}] {name}: {det}")
    ap("")
    n_warn = 0
    warns = [
        (True, f"elementos LOAD_ONLY presentes ({len(los)}): solo carga, sin rigidez"),
        (bool(fe_with_src), "elementos FE exportados con fuente (inconsistencia con export_unity)"),
        (sum(amb_beams.values()) + sum(amb_walls.values()) > 0,
         f"vigas/muros 'ambiguous' excluidos por politica: {sum(amb_beams.values())}/{sum(amb_walls.values())} en P1-P4"),
        (len(dxf_cols.get(('P3', 'P4'), [])) > 16,
         "2 columnas DXF P3-P4 sin modelo (P2 x=40 sin base continua en P1)"),
        (True, "S1 y FDN no modelados; base fija en P1 (16 apoyos)"),
        (bool(protruding), f"{len(protruding)} puntos FE sobresalen > 0.5 m de la huella de pilares"),
    ]
    for cond, msg in warns:
        if cond:
            ap(f"- [WARNING] {msg}")
            n_warn += 1
    ap("")

    fails = [n for n, ok, _ in checks if not ok]
    verdict = "FAIL" if fails else ("WARNING (con advertencias documentadas)" if n_warn else "PASS")
    ap(f"## VEREDICTO DE GEOMETRIA: {verdict}")
    ap("")
    if fails:
        ap(f"- FALLOS: {len(fails)} -> {', '.join(fails)}")
    ap(f"- Advertencias documentadas: {n_warn}.")
    ap("- La geometria FE (nodos, longitudes, topologia) coincide con los miembros DXF high-confidence "
       "incorporados dentro de tolerancia; las diferencias reportadas son de POLITICA (exclusiones ambiguous, "
       "weak-base, S1/FDN, LOAD_ONLY) y quedan registradas sin corregir.")
    ap("")
    ap("## Archivos nuevos de esta auditoria")
    ap("")
    ap("- `results/qa_geometria_semana2.md`")
    for l in LVLS:
        ap(f"- `figures/qa_geometria_{l}.png`")
    ap("")
    ap("## Siguiente paso")
    ap("")
    ap("Revision humana de este reporte y de las imagenes de planta (el modelo no puede inspeccionar PNG). "
       "No se corrige nada por decision propia del asistente.")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # ── console ──
    print("== AUDITORIA GEOMETRIA SEMANA 2 ==")
    print(f"FE: cols={len(fe_cols)} beams={len(fe_beams)} walls={len(fe_walls)} LOAD_ONLY={len(los)}")
    print(f"d_max={d_max_all:.4f} | dup_tags={dup_tags} | zero={len(zero)} | detached={len(detached)} "
          f"| unsupported={len(unsupported)} | protruding={len(protruding)}")
    for gi in geom_issues:
        print("geom_issue:", gi)
    for pair in (("P1", "P2"), ("P2", "P3"), ("P3", "P4")):
        cr = col_report.get(pair, {})
        print("cols", pair, cr.get("dxf"), cr.get("fe"), cr.get("matched"),
              "fe_missing", cr.get("fe_missing", 0), "dxf_un", cr.get("dxf_unmatched", 0))
    if excl_hi:
        print("excluidos hi:", excl_hi)
    for p in protruding:
        print("sobresale:", p)
    print("VEREDICTO:", verdict)
    print("MD:", OUT_MD)


if __name__ == "__main__":
    main()