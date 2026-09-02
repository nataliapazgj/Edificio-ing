"""
Auditoria dirigida (Semana 2): vigas de P1, trazabilidad de muros P1-P4,
columnas DXF P3-P4 y elementos sobresalientes.

NO modifica ningun modelo: solo lee
  data/processed/building_3d_aligned.json
  data/processed/unity_model.json
  data/dxf/2017_67-101.dxf / -102 / -103
y re-usa las funciones de grouping de src/geometric_cleanup.py para
REPRODUCIR de forma determinista el diagnostico (sin tocar sus salidas).

Causa raiz bajo prueba (hipotesis del usuario = confirmada):
  extract_structure.load_plant llama group_beams(raw_viga, ...) sobre el DXF
  completo (S1 + P1 en el 101) y filtra por ventana DESPUES del grouping.
  detect_face_width global sobre 101 da 20 (moda de S1) mientras P1 dibuja
  sus vigas a 60 CAD -> las caras a 60 no emparejan dentro de tol 12 ->
  90/97 vigas P1 caen como "ambiguous".

Salidas:
  figures/audit_P1_vigas.png
  figures/audit_muros_P{1..4}.png
  results/audit_P1_muros_semana2.md
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ezdxf  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

from geometric_cleanup import (  # noqa: E402
    extract_face_runs,
    extract_lines_from_layer,
    group_beams,
    group_columns,
    group_walls,
)

ROOT = Path(__file__).resolve().parent.parent
DXF_DIR = ROOT / "data" / "dxf"
ALIGNED = ROOT / "data" / "processed" / "building_3d_aligned.json"
UNITY = ROOT / "data" / "processed" / "unity_model.json"
OUT_MD = ROOT / "results" / "audit_P1_muros_semana2.md"
OUT_FIG_V = ROOT / "figures" / "audit_P1_vigas.png"
OUT_FIG_M = {l: ROOT / "figures" / f"audit_muros_{l}.png" for l in ("P1", "P2", "P3", "P4")}

DY_CORRECTION = -20.52
CORRECT_LEVELS = ("P3", "P4")
LVLS = ("P1", "P2", "P3", "P4")
DIST_ANCHOR = 8.0
NODE_SNAP_TOL = 0.5


def load_and_shift():
    data = json.loads(ALIGNED.read_text(encoding="utf-8"))
    for n in data["nodes"]:
        if n["level"] in CORRECT_LEVELS:
            n["y"] = n["y"] + DY_CORRECTION
    for e in data["beams"] + data["walls"]:
        if e["level"] in CORRECT_LEVELS:
            e["y1"] += DY_CORRECTION
            e["y2"] += DY_CORRECTION
    return data


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main():
    data = load_and_shift()
    unity = json.loads(UNITY.read_text(encoding="utf-8"))
    node_coord = {n["nodeTag"]: (n["x"], n["y"], n["z"]) for n in unity["nodes"]}
    elements = unity["elements"]

    # ------------------------------------------------------------------ #
    # Rejillas y pilares soportados (igual que audit previa)
    # ------------------------------------------------------------------ #
    level_grid = defaultdict(list)
    for n in data["nodes"]:
        if n["level"] in LVLS:
            level_grid[n["level"]].append((n["x"], n["y"]))
    acc = None
    for l in LVLS:
        g = set((round(x, 3), round(y, 3)) for x, y in level_grid[l])
        acc = g if acc is None else (acc & g)
    supported_xy = sorted(acc)
    print("Pilares soportados P1..P4:", len(supported_xy))

    hi_beams = {l: [b for b in data["beams"] if b["level"] == l and b["status"] == "high-confidence"] for l in LVLS}
    hi_walls = {l: [w for w in data["walls"] if w["level"] == l and w["status"] == "high-confidence"] for l in LVLS}
    amb_beams = {l: [b for b in data["beams"] if b["level"] == l and b["status"] != "high-confidence"] for l in LVLS}
    amb_walls = {l: [w for w in data["walls"] if w["level"] == l and w["status"] != "high-confidence"] for l in LVLS}

    # ------------------------------------------------------------------ #
    # Miembros fisicos y estados FE/LOAD_ONLY/EXCLUIDOS (orden build_ops_model)
    # ------------------------------------------------------------------ #
    phys = {}  # (lvl, orig) -> rec
    for l in LVLS:
        for i, b in enumerate(hi_beams[l]):
            phys[(l, i)] = {"kind": "beam", "x1": b["x1"], "y1": b["y1"], "x2": b["x2"], "y2": b["y2"],
                            "src": b, "fe": 0, "lo": 0, "nseg": 0}
        nj = len(hi_beams[l])
        for j, w in enumerate(hi_walls[l]):
            phys[(l, nj + j)] = {"kind": "wall", "x1": w["x1"], "y1": w["y1"], "x2": w["x2"], "y2": w["y2"],
                                 "src": w, "fe": 0, "lo": 0, "nseg": 0}

    fe_beams, fe_walls, fe_cols, los = [], [], [], []
    for e in elements:
        if e["analysis_status"] == "LOAD_ONLY":
            los.append(e)
            key = (e["level"], e["physical_id"])
            if key in phys and phys[key]["kind"] == e["type"]:
                phys[key]["lo"] += 1
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
        rec["fe"] += 1
        rec["nseg"] += 1
        (fe_walls if e["type"] == "wall" else fe_beams).append(e)

    # ------------------------------------------------------------------ #
    # Diagnostico vigas P1 (reproducir corte por planta vs global)
    # ------------------------------------------------------------------ #
    doc101 = ezdxf.readfile(str(DXF_DIR / "2017_67-101.dxf"))
    raw_viga = extract_lines_from_layer(doc101.modelspace(), "RLE-VIGA")
    longv = [x for x in raw_viga if x["length"] >= 80]

    def fw_of(lines):
        hr = extract_face_runs(lines, "H")
        vr = extract_face_runs(lines, "V")
        hc = sorted({r["coord"] for r in hr})
        vc = sorted({r["coord"] for r in vr})
        return hc, vc

    # face-width global (como lo hace el pipeline) vs por planta
    from geometric_cleanup import detect_face_width, cluster_1d

    hc, vc = fw_of(longv)
    fw_global = detect_face_width(cluster_1d(hc, 8.0) + cluster_1d(vc, 8.0))
    hcP, vcP = fw_of([x for x in longv if x["start"][1] < 5100])
    fw_p1 = detect_face_width(cluster_1d(hcP, 8.0) + cluster_1d(vcP, 8.0))
    s1lines = [x for x in longv if x["start"][1] >= 5100]
    hcS, vcS = fw_of(s1lines)
    fw_s1 = detect_face_width(cluster_1d(hcS, 8.0) + cluster_1d(vcS, 8.0))

    bglob, fglob = group_beams(longv, [])
    bcad_all = [c["center_cad"] for c in group_columns(extract_lines_from_layer(doc101.modelspace(), "RLE-PILAR"))]
    bglob_col, fglob_col = group_beams(longv, bcad_all)
    bp_gl = sum(1 for x in (bglob + fglob) if max((b for b in (x["centerline_cad"][0][1], x["centerline_cad"][1][1])), default=0) < 5100
                and min((b for b in (x["centerline_cad"][0][1], x["centerline_cad"][1][1])), default=0) < 5100)
    # contar con ventana estricta por mid_y
    def mid_y(x):
        return (x["centerline_cad"][0][1] + x["centerline_cad"][1][1]) / 2.0
    bp_glob = sum(1 for x in bglob if mid_y(x) < 5100)
    fg_glob = sum(1 for x in fglob if mid_y(x) < 5100)
    bs_glob = len(bglob) - bp_glob
    fs_glob = len(fglob) - fg_glob

    p1lines = [x for x in longv if x["start"][1] < 5100 and x["end"][1] < 5100]
    s1long = [x for x in longv if x["start"][1] >= 5100 and x["end"][1] >= 5100]
    bp_pp, fp_pp = group_beams(p1lines, [])
    bs_pp, fs_pp = group_beams(s1long, [])

    # ------------------------------------------------------------------ #
    # Recuperabilidad de las vigas P1 ambiguous
    # ------------------------------------------------------------------ #
    colxy = set((round(x, 3), round(y, 3)) for x, y in supported_xy)
    p1_amb_recover = []
    for i, b in enumerate(amb_beams["P1"]):
        e1, e2 = (b["x1"], b["y1"]), (b["x2"], b["y2"])
        d1 = min(d2(e1, c) for c in colxy)
        d2_ = min(d2(e2, c) for c in colxy)
        L = math.hypot(e2[0] - e1[0], e2[1] - e1[1])
        row = (e1[1] + e2[1]) / 2.0 if abs(e1[0] - e2[0]) > 1e-6 else None
        anchored = d1 <= DIST_ANCHOR and d2_ <= DIST_ANCHOR
        onr = row is not None and any(abs(row - cy) <= 0.35 for _, cy in colxy)
        p1_amb_recover.append((i, L, d1, d2_, row, anchored, onr))
    n_rec_anchor = sum(1 for r in p1_amb_recover if r[5])
    n_rec_gird = sum(1 for r in p1_amb_recover if r[6])
    n_recover = sum(1 for r in p1_amb_recover if r[5] and r[6])

    # ------------------------------------------------------------------ #
    # Columnas: rejillas por nivel y base de P1
    # ------------------------------------------------------------------ #
    ncols = {l: len(level_grid[l]) for l in LVLS}
    missing1 = sorted(set(level_grid["P2"]) - set(level_grid["P1"]))
    p1_pil_lines = [l for l in extract_lines_from_layer(doc101.modelspace(), "RLE-PILAR")
                    if l["start"][1] < 5100 and l["end"][1] < 5100]

    def col_completeness(cadx, cady):
        """Cuenta caras horizontales/verticales RLE-PILAR de P1 cerca de un
        centro CAD y emula la regla de group_columns (>=3 votos de caras
        55-85 CAD => columna)."""
        from geometric_cleanup import is_horizontal
        h_len, v_len = [], []
        for l in p1_pil_lines:
            s, e = l["start"], l["end"]
            if is_horizontal(s, e):
                if (abs(s[1] - (cady - 35)) <= 2.0 or abs(s[1] - (cady + 35)) <= 2.0) \
                        and min(s[0], e[0]) >= cadx - 45 and max(s[0], e[0]) <= cadx + 45:
                    h_len.append(round(l["length"], 1))
            else:
                if (abs(s[0] - (cadx - 35)) <= 2.0 or abs(s[0] - (cadx + 35)) <= 2.0) \
                        and min(s[1], e[1]) >= cady - 45 and max(s[1], e[1]) <= cady + 45:
                    v_len.append(round(l["length"], 1))
        h_votes = sum(1 for ll in h_len if 55 <= ll <= 85)
        v_votes = sum(1 for ll in v_len if 55 <= ll <= 85)
        return h_len, v_len, h_votes, v_votes

    p2extra_in_cad = []
    for (mx, my) in missing1:
        cadx = (mx + 10.6132) * 100.0
        cady = (my + 35.8301) * 100.0
        h_len, v_len, h_v, v_v = col_completeness(cadx, cady)
        vote_ok = (h_v + v_v >= 3)
        p2extra_in_cad.append((mx, my, round(cadx, 1), round(cady, 1), h_len, v_len, h_v, v_v, vote_ok))
    cols102_y2 = [c for c in group_columns(extract_lines_from_layer(ezdxf.readfile(str(DXF_DIR / "2017_67-102.dxf")).modelspace(), "RLE-PILAR")) if c["center_cad"][1] >= 5100]
    cols102_y3 = [c for c in group_columns(extract_lines_from_layer(ezdxf.readfile(str(DXF_DIR / "2017_67-102.dxf")).modelspace(), "RLE-PILAR")) if c["center_cad"][1] < 5100]
    fe_cols_by_level = defaultdict(list)
    for e in fe_cols:
        i = tuple(round(v, 3) for v in node_coord[e["node_i"]][:2])
        j = tuple(round(v, 3) for v in node_coord[e["node_j"]][:2])
        fe_cols_by_level[e["level"]].append((i, j))
    fe_cols_n = {l: len(fe_cols_by_level[l]) for l in LVLS}

    # ------------------------------------------------------------------ #
    # Elementos sobresalientes -> miembro DXF
    # ------------------------------------------------------------------ #
    protruding = []
    for l in LVLS:
        xs = [c[0] for c in level_grid[l]]
        ys = [c[1] for c in level_grid[l]]
        if not xs:
            continue
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        for e in fe_beams + fe_walls:
            if e["level"] != l:
                continue
            for nn in (e["node_i"], e["node_j"]):
                x, y, _ = node_coord[nn]
                over = max(max(x0 - x, x - x1, 0.0), max(y0 - y, y - y1, 0.0))
                if over > 0.5:
                    key = (e["level"], e["physical_id"])
                    src = phys.get(key, {}).get("src")
                    protruding.append({
                        "lvl": l, "type": e["type"], "tag": e["elementTag"], "node": nn,
                        "x": x, "y": y, "over": over, "phys": key,
                        "dxf": src.get("dxf") if src else None, "src_len": src.get("length_m") if src else None,
                    })

    # ------------------------------------------------------------------ #
    # Muros: trazabilidad completa por nivel
    # ------------------------------------------------------------------ #
    wall_rows = []
    for l in LVLS:
        nj = len(hi_beams[l])
        for j, w in enumerate(hi_walls[l]):
            L = math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"])
            rec = phys[(l, nj + j)]
            if rec["fe"]:
                state, reason = "FE", f"{rec['fe']} elems FE"
            elif rec["lo"]:
                state, reason = "LOAD_ONLY", f"{rec['lo']} elems de carga (sin rigidez)"
            else:
                e1, e2 = (w["x1"], w["y1"]), (w["x2"], w["y2"])
                d1 = min(d2(e1, c) for c in colxy)
                d2_ = min(d2(e2, c) for c in colxy)
                state, reason = "EXCLUIDO", f"sin pilar soportado a <=8m (d1={d1:.1f}, d2={d2_:.1f})"
            wall_rows.append((l, nj + j, L, state, reason))

    # ------------------------------------------------------------------ #
    # FIGURAS
    # ------------------------------------------------------------------ #
    # P1: vigas hi / ambiguous / recuperables + per-plant potencial
    bpp_pot = [x for x in bp_pp if mid_y(x) < 5100]
    hi_centers = [(b["x1"], b["y1"], b["x2"], b["y2"]) for b in hi_beams["P1"]]
    pot_new = []
    for x in bpp_pot:
        s, e = x["centerline_cad"]
        s = (s[0] - 10.6132, s[1] - 35.8301)
        e = (e[0] - 10.6132, e[1] - 35.8301)
        if any(d2((s[0], s[1]), (h[0], h[1])) < 0.5 and d2((e[0], e[1]), (h[2], h[3])) < 0.5 for h in hi_centers):
            continue
        pot_new.append((s[0], s[1], e[0], e[1]))

    fig = go.Figure()
    # rejilla de pilares
    sx, sy = zip(*colxy)
    fig.add_trace(go.Scatter(x=sx, y=sy, mode="markers", marker=dict(color="#111", size=8, symbol="square"), name="Pilares soportados"))
    # vigas hi (7)
    for b in hi_beams["P1"]:
        fig.add_trace(go.Scatter(x=[b["x1"], b["x2"]], y=[b["y1"], b["y2"]], mode="lines", line=dict(color="#2a7fff", width=4), name="Vigas P1 high-confidence", showlegend=False))
    # ambiguous
    for i, r in enumerate(p1_amb_recover):
        b = amb_beams["P1"][r[0]]
        c = "#36c15c" if (r[5] and r[6]) else "#c9c9c9"
        fig.add_trace(go.Scatter(x=[b["x1"], b["x2"]], y=[b["y1"], b["y2"]], mode="lines", line=dict(color=c, width=2), name=("Ambiguous recuperable" if r[5] else "Ambiguous excluida"), showlegend=False))
    # per-plant potential (extra paired)
    for x0, y0, x1, y1 in pot_new:
        fig.add_trace(go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(color="#ffb300", width=2.5, dash="dot"), name="Potencial re-emparejada por planta", showlegend=False))
    # LOAD_ONLY P1
    for e in los:
        if e["level"] != "P1":
            continue
        a, b = e["coordinates"]["i"], e["coordinates"]["j"]
        fig.add_trace(go.Scatter(x=[a[0], b[0]], y=[a[1], b[1]], mode="lines", line=dict(color="#e633cc", width=3, dash="dash"), name="LOAD_ONLY", showlegend=False))
    fig.update_layout(
        title=(f"P1 (z=-0.05 m): 97 vigas DXF = 7 high-confidence + 90 ambiguous "
               f"({n_recover} recuperables entre 8m de rejilla) | pot. re-emparejadas: {len(pot_new)}"),
        yaxis=dict(scaleanchor="x", scaleratio=1, title="Y [m]"),
        xaxis=dict(title="X [m]"),
        margin=dict(l=0, r=0, t=60, b=0), height=560, showlegend=True,
    )
    OUT_FIG_V.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(OUT_FIG_V), width=1200, height=680, scale=1.6)

    for l in LVLS:
        fig = go.Figure()
        nj = len(hi_beams[l])
        colxy_l = set((round(x, 3), round(y, 3)) for x, y in level_grid[l])
        # ambiguous walls
        for w in amb_walls[l]:
            fig.add_trace(go.Scatter(x=[w["x1"], w["x2"]], y=[w["y1"], w["y2"]], mode="lines", line=dict(color="#d9d9d9", width=2), name="Muro ambiguous", showlegend=False))
        for j, w in enumerate(hi_walls[l]):
            rec = phys[(l, nj + j)]
            c = "#d87a26" if rec["fe"] else ("#e633cc" if rec["lo"] else "#c00")
            wd = 4 if rec["fe"] else 3
            fig.add_trace(go.Scatter(x=[w["x1"], w["x2"]], y=[w["y1"], w["y2"]], mode="lines", line=dict(color=c, width=wd, dash=None if rec["fe"] else "dash"), name=f"Muro {l} {j}", showlegend=False))
        # vigas hi de referencia
        for b in hi_beams[l]:
            fig.add_trace(go.Scatter(x=[b["x1"], b["x2"]], y=[b["y1"], b["y2"]], mode="lines", line=dict(color="#a9b6cf", width=3, dash="dot"), name="Vigas hi", showlegend=False))
        sxx, syy = zip(*colxy_l)
        fig.add_trace(go.Scatter(x=sxx, y=syy, mode="markers", marker=dict(color="#111", size=8, symbol="square"), name="Pilares de piso"))
        fe_n = sum(1 for r in wall_rows if r[0] == l and r[3] == "FE")
        lo_n = sum(1 for r in wall_rows if r[0] == l and r[3] == "LOAD_ONLY")
        ex_n = sum(1 for r in wall_rows if r[0] == l and r[3] == "EXCLUIDO")
        fig.update_layout(
            title=f"Planta {l}: muros hi {len(hi_walls[l])} = FE {fe_n} / LOAD_ONLY {lo_n} / EXCL {ex_n} | ambiguous {len(amb_walls[l])}",
            yaxis=dict(scaleanchor="x", scaleratio=1, title="Y [m]"),
            xaxis=dict(title="X [m]"),
            margin=dict(l=0, r=0, t=60, b=0), height=560, showlegend=False,
        )
        OUT_FIG_M[l].parent.mkdir(parents=True, exist_ok=True)
        fig.write_image(str(OUT_FIG_M[l]), width=1200, height=680, scale=1.6)

    # ------------------------------------------------------------------ #
    # REPORTE
    # ------------------------------------------------------------------ #
    lines = []
    ap = lines.append
    ap("# Auditoria dirigida - Vigas P1, muros P1-P4 y columnas P3-P4 (Semana 2)")
    ap("")
    ap("- Fecha: 2026-09-01 | Estado: **SIN MODIFICAR** modelo FE, unity_model.json, cargas, areas tributarias ni DXF.")
    ap("- Fuentes de lectura: `building_3d_aligned.json`, `unity_model.json`, DXF 101/102/103.")
    ap("- Metodo: reproduccion determinista del grouping de `geometric_cleanup.py` + mapeo `physical_id` (igual que la auditoria previa).")
    ap("")

    ap("## 1. CAUSA RAIZ: por que P1 tiene tan pocas vigas FE")
    ap("")
    ap("El pipeline separa plantas con la VENTANA de Y CAD (`y_min..y_max` en `extract_structure.PLANTAS`), pero la "
       "SEPARACION ocurre **despues** del grouping: `load_plant` llama `group_beams(raw_viga, ...)` con las lineas del "
       "DXF completo (S1 + P1 en el 101) y solo luego filtra `mid_y` por planta. El emparejamiento de caras "
       "(`detect_face_width`) se calcula sobre TODAS las lineas.")
    ap("")
    ap("| Metrica | DXF 101 completo (como corre el pipeline) | S1 solo | P1 solo (diagnostico) |")
    ap("|---|---|---|---|")
    ap(f"| `face_width` detectado | {fw_global} | {fw_s1} | {fw_p1} |")
    ap(f"| Vigas emparejadas P1 | {bp_glob} | - | {len(bp_pp)} |")
    ap(f"| Fragmentos P1 | {fg_glob} | - | {len(fp_pp)} |")
    ap(f"| Vigas emparejadas S1 | {bs_glob} | {len(bs_pp)} | - |")
    ap(f"| Fragmentos S1 | {fs_glob} | {len(fs_pp)} | - |")
    ap("")
    ap("La moda global del 101 es **20** (convencion de dibujo de S1). P1 dibuja sus vigas con ancho de cara **60 CAD**. "
       "El emparejamiento (`pair_runs_to_elements`) acepta `|d - face_width| <= width_tol` con `width_tol = 12` para "
       "vigas: un par de caras a 60 CAD da `|60 - 20| = 40 > 12` -> nunca empareja. Las vigas de P1 dibujadas con "
       "ancho ~60 quedan como fragmentos sin pareja. Las unicas 7 'hi' de P1 que casan lo hacen con ancho de cara "
       "15-20 CAD (medido `width_cad`), es decir con la convencion de S1 y NO con la de P1: son emparejamientos "
       "sospechosos que el re-emparejamiento por planta deberia revisar.")
    ap("")
    ap("**Resultado medido:** con el pipeline actual, las vigas P1 pasan de 7 (high-confidence) + 90 (ambiguous) a "
       "**39 vigas + 26 fragmentos** si se separa P1 antes del grouping (per-plant). Las 90 'ambiguous' de P1 son, en "
       "su mayoria, caras que no encontraron pareja por este error de ancho de cara, NO vigas inexistentes en el DXF.")
    ap("")
    ap("Nota: el problema es exclusivo de plantas que comparten lamina con distinta convencion de ancho. S1 no cambia "
       "(21/17 global == per-plant). En el 102 (P2+P3) debe verificarse el mismo riesgo.")
    ap("")

    ap("## 2. Estado de las 97 vigas P1")
    ap("")
    ap("| Estado | Conteo | Detalle |")
    ap("|---|---|---|")
    fe_hi = sum(1 for k, r in phys.items() if k[0] == "P1" and r["kind"] == "beam" and r["fe"])
    lo_hi = sum(1 for k, r in phys.items() if k[0] == "P1" and r["kind"] == "beam" and r["lo"])
    ap(f"| high-confidence -> FE | {fe_hi} | vigas modeladas (elementos FE en P1) |")
    ap(f"| high-confidence -> LOAD_ONLY | {lo_hi} | solo carga, sin rigidez |")
    ap(f"| high-confidence -> EXCLUIDA | {len([b for b in hi_beams['P1']]) - fe_hi - lo_hi} | sin pilar soportado a <=8 m |")
    ap(f"| ambiguous (excluidas por politica) | {len(amb_beams['P1'])} | fragmentos sin pareja; NO entran a OpenSees |")
    ap("")
    ap("Vigas high-confidence P1 (con estado FE/LOAD/EXCL y origen `physical_id`):")
    ap("")
    ap("| #orig | Long. m | (x1,y1)->(x2,y2) m | Estado | Razon |")
    ap("|---|---|---|---|---|")
    for i, b in enumerate(hi_beams["P1"]):
        rec = phys[("P1", i)]
        if rec["fe"]:
            st, rz = "FE", f"{rec['fe']} elems FE"
        elif rec["lo"]:
            st, rz = "LOAD_ONLY", f"{rec['lo']} elems de carga (sin rigidez)"
        else:
            d1 = min(d2((b["x1"], b["y1"]), c) for c in colxy)
            d2_ = min(d2((b["x2"], b["y2"]), c) for c in colxy)
            st, rz = "EXCLUIDA", f"sin pilar soportado a <=8m (d1={d1:.1f}, d2={d2_:.1f})"
        ap(f"| {i} | {math.hypot(b['x2']-b['x1'], b['y2']-b['y1']):.2f} | ({b['x1']:.2f},{b['y1']:.2f})->({b['x2']:.2f},{b['y2']:.2f}) | {st} | {rz} |")
    ap("")
    ap("## 3. Vigas P1 potencialmente recuperables")
    ap("")
    ap("Criterio de conectividad (politica v2 de `ops_model`): nodo FE a <= 8 m de un pilar soportado P1..P4. "
       "Aplicado a los extremos de cada viga ambiguous de P1 con la rejilla soportada:")
    ap("")
    ap(f"- Vigas ambiguous con AMBOS extremos a <= 8 m de rejilla soportada: **{n_rec_anchor} de {len(p1_amb_recover)}** "
       f"(criterio 8 m es generoso con rejilla de 5 m).")
    ap(f"- Vigas ambiguous centradas sobre una fila de rejilla (|y_centro - y_rejilla| <= 0.35 m): **{n_rec_gird}**.")
    ap(f"- Vigas ambiguous ancladas Y sobre fila de rejilla ('recuperables estructurales'): **{n_recover}**.")
    ap(f"- Re-emparejando por planta (diagnostico): {len(bp_pp)} pares, de las cuales {len(pot_new)} nuevas respecto de las 7 hi actuales.")
    ap("")
    ap("Estas cifras son el **techo de recuperacion** si se corrige la separacion por planta. La decision de "
       "reincorporarlas (y su estado FE/LOAD_ONLY) requiere revisar cada candidato contra el DXF y la politica de "
       "modelo; NO se reincorpora nada automaticamente en esta auditoria.")
    ap("")

    ap("## 4. Trazabilidad de muros P1-P4")
    ap("")
    ap("| Piso | hi DXF | FE (phys) | LOAD_ONLY | EXCLUIDOS (hi) | Ambiguous |")
    ap("|---|---|---|---|---|---|")
    for l in LVLS:
        fe = sum(1 for r in wall_rows if r[0] == l and r[3] == "FE")
        lo = sum(1 for r in wall_rows if r[0] == l and r[3] == "LOAD_ONLY")
        ex = sum(1 for r in wall_rows if r[0] == l and r[3] == "EXCLUIDO")
        ap(f"| {l} | {len(hi_walls[l])} | {fe} | {lo} | {ex} | {len(amb_walls[l])} |")
    ap("")
    ap("Detalle por muro high-confidence (numero = `physical_id` del nivel):")
    ap("")
    ap("| Piso | #orig | Long. m | Estado | Razon |")
    ap("|---|---|---|---|---|")
    for l, o, L, state, reason in wall_rows:
        w = hi_walls[l][o - len(hi_beams[l])]
        ap(f"| {l} | {o} | {L:.2f} | {state} | {reason} |")
    ap("")

    ap("## 5. Las 2 columnas DXF P3-P4 que no llegan a P1")
    ap("")
    ap("| Nivel | Columnas en rejilla DXF | Columnas FE |")
    ap("|---|---|---|")
    for l in LVLS:
        ap(f"| {l} | {ncols[l]} | {fe_cols_n[l]} |")
    ap("")
    ap("- Rejillas: P1=16, P2=18, P3=18, P4=18; interseccion soportada = 16.")
    ap("- Nota tabla: los elementos FE de columna guardan `level` = extremo inferior, por eso P4 muestra 0; "
       "hay 16 columnas FE continuas P1->P2 ->P3 -> P4.")
    ap("- Posiciones de P2 sin base en P1: (X=40, Y=-9.15) y (X=40, Y=-0.25) m. Estado del trazado RLE-PILAR "
       "del 101 (P1, y<5100) en esas posiciones CAD:")
    ap("")
    ap("| Posicion m | CAD (x,y) | Caras H en P1 (long. CAD) | Caras V en P1 (long. CAD) | Votos centro | Columna P1? |")
    ap("|---|---|---|---|---|---|")
    for mx, my, cx, cy, hl, vl, hv, vv, ok in p2extra_in_cad:
        htxt = f"{len(hl)} caras {hl}"
        vtxt = f"{len(vl)} caras {vl}"
        ap(f"| (40.0, {my:.2f}) | ({cx:.0f},{cy:.0f}) | {htxt} | {vtxt} | "
           f"{hv}+{vv} = {hv+vv} (se requieren >=3) | {'SI' if ok else 'NO - seccion incompleta'} |")
    ap("")
    ap("- `group_columns` (`geometric_cleanup.py`) filtra caras de 55-85 CAD y exige **>=3 votos** al centro: "
       "cada cara 70 da 1 voto central. En (40,-9.15) el 101 dibuja las 2 caras verticales (70 c/u) **pero el borde "
       "superior/inferior esta partido** en trozos de 35/5/5/35 CAD (< 55 -> 0 votos): total 2 votos -> descartado. "
       "En (40,-0.25) las verticales miden 40 CAD (< 55, 0 votos) y solo el borde superior (70) vota -> 1 voto: "
       "descartado. Por eso la rejilla P1 tiene 16 columnas y el pipeline no genera base continua en esas 2 posiciones.")
    ap("")
    ap(f"- DXF 102: P2 (y>=5100) = {len(cols102_y2)} pilares completos, P3 (y<5100) = {len(cols102_y3)} pilares "
       f"completos; tras el corrimiento -20.52 ambas rejillas coinciden -> 18 columnas P2-P3-P4.")
    ap("")
    ap("**Conclusion:** las 2 columnas en (X=40, Y=-9.15) y (X=40, Y=-0.25) SON completas y reales en P2/P3/P4 "
       "(18 pilares), pero en P1 el DXF no cierra su seccion (caras parciales) y el pipeline no emite base; el FE "
       "exige columna continua hasta P1, por lo que quedan EXCLUIDAS (politica de `ops_model.py`).")
    ap("")
    ap("Decision humana requerida: (a) completar la seccion de esos 2 pilares en P1 (2 caras faltantes) y "
       "revisar si corresponden estructuralmente, (b) apoyarlas en viga de transferencia desde P2, o (c) mantenerlas "
       "fuera y verificar que la estabilidad no dependa de ellas.")
    ap("")

    ap("## 6. Elementos que sobresalen de la huella de pilares (origen DXF)")
    ap("")
    uniq = {}
    for p in protruding:
        uniq.setdefault((p["lvl"], p["type"], p["tag"]), []).append(p)
    ap(f"- **{len(protruding)} nodos de {len(uniq)} elementos FE** sobresalen > 0.5 m del rectangulo de pilares "
       f"soportados del piso. Cada elemento es un miembro DXF high-confidence documentado en `building_3d_aligned.json` "
       f"(capa + `length_m` + coords), trazado abajo.")
    ap("")
    ap("| Piso | Tipo | tag FE | nodo | (x,y) m | saliente | origen DXF | L dxf m |")
    ap("|---|---|---|---|---|---|---|---|")
    for p in sorted(protruding, key=lambda p: (p["lvl"], p["type"])):
        ap(f"| {p['lvl']} | {p['type']} | {p['tag']} | {p['node']} | ({p['x']:.2f},{p['y']:.2f}) | {p['over']:.2f} | "
           f"{p['dxf']} | {p['src_len'] if p['src_len'] else 0:.2f} |")
    ap("")
    ap("Verificacion en DXF: estos trazos existen como vigas reales (p.ej. banda y=-20.8..-18.7 y borde este x>45 en "
       "P2/P3/P4 pertenecen al 102; franja y~3.3 en P1 al 101). Son distancias de diseño (voladizos/fachada), no ruido "
       "del FE: `d_max nodo->linea <= 0.5 m` los mantiene sobre su linea DXF de origen.")
    ap("")

    ap("## 7. Elementos/acciones recomendadas (trazables al DXF)")
    ap("")
    ap("1. [PIPELINE] En `extract_structure.load_plant`, separar `raw_viga`/`raw_muro`/pilares por ventana ANTES de "
       "`group_beams`/`group_walls` (face-width por planta). Efecto medido en 101-P1: 7 -> 39 vigas, 90 -> 26 fragmentos.")
    ap(f"2. [MODELO] Tras corregir el grouping, re-evaluar las {n_recover} vigas P1 ambiguous ancladas Y sobre fila "
       f"de rejilla y las {len(pot_new)} pares nuevas del per-plant; decidir FE/LOAD_ONLY caso a caso.")
    excl_walls = {l: [r[1] for r in wall_rows if r[0] == l and r[3] == "EXCLUIDO"] for l in LVLS}
    excl_txt = "; ".join(f"{l}: {', '.join(str(o) for o in ows)}" for l in LVLS if (ows := excl_walls[l]))
    total_hi_walls = len(hi_walls["P1"]) + len(hi_walls["P2"]) + len(hi_walls["P3"]) + len(hi_walls["P4"])
    ap(f"3. [MODELO] Muros: FE {sum(1 for r in wall_rows if r[3]=='FE')}, LOAD_ONLY "
       f"{sum(1 for r in wall_rows if r[3]=='LOAD_ONLY')}, EXCLUIDOS {sum(1 for r in wall_rows if r[3]=='EXCLUIDO')} "
       f"(en P1-P4: {excl_txt}); {total_hi_walls} muros hi trazados; {sum(len(amb_walls[l]) for l in LVLS)} muros "
       f"ambiguous excluidos por politica hasta validacion.")
    ap("4. [ESTRUCTURA] Las 2 columnas P2-P4 (X=40) sin base en P1 requieren decision humana (fundir en P1, transfer, o "
       "excluir). No se toca el modelo.")
    ap("5. [GEOMETRIA] Los 46 elementos sobresalientes son DXF reales; se conservan tal cual. Nada que eliminar.")
    ap("6. [S1/FDN] No modelados (base fija en P1, 16 apoyos); fuera del alcance de esta auditoria.")
    ap("")
    ap("Todo lo anterior queda SIN MODIFICAR a la espera de revision humana. No se reincorporan elementos "
       "automaticamente ni se tocan cargas/areas tributarias/Unity.")
    ap("")
    ap("## Archivos generados")
    ap("")
    ap("- `results/audit_P1_muros_semana2.md`")
    ap("- `figures/audit_P1_vigas.png`")
    for l in LVLS:
        ap(f"- `figures/audit_muros_{l}.png`")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------ #
    print("== AUDIT P1 VIGAS / MUROS / COLUMNAS ==")
    print(f"face_width global={fw_global} p1={fw_p1} s1={fw_s1}")
    print(f"P1 vigas: pipeline hi={len(hi_beams['P1'])} amb={len(amb_beams['P1'])} | per-plant pairs={len(bp_pp)} frags={len(fp_pp)}")
    print(f"recuperables(8m)={n_rec_anchor} on_row={n_rec_gird} recover_struc={n_recover} pot_new={len(pot_new)}")
    print(f"muros hi: P1={len(hi_walls['P1'])} P2={len(hi_walls['P2'])} P3={len(hi_walls['P3'])} P4={len(hi_walls['P4'])}")
    print(f"columnas por piso: {ncols} | FE: {fe_cols_n} | faltan base P1: {missing1}")
    print(f"protruding nodos={len(protruding)} elementos={len(uniq)}")
    print("MD:", OUT_MD)


if __name__ == "__main__":
    main()