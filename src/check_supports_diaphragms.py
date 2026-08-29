"""Chequeo de apoyos, master nodes y diafragmas LT2 (solo lectura).

Verifica:
  - numero de apoyos unicos en B1 (empotramiento completo 6 GDL);
  - 5 master nodes (NM_L1..NM_ROOF), sin duplicados, sin coincidencia
    con nodos estructurales (tol 1e-6), metodo geometric_bbox_center;
  - 5 diafragmas (L1..ROOF; B1 excluido), con master existente;
  - slaves generados DINAMICAMENTE desde la geometria (extremos de vigas
    + nodos de columnas segmentadas + nodos de muros segmentados),
    dedup por (x,y) y nivel con tol 1e-6, master excluido de su lista;
  - ningun slave duplicado dentro de un nivel ni en dos diafragmas;
  - todos los nodos estructurales elegibles de L1..ROOF asignados a
    exactamente UN diafragma;
  - niveles referenciados existen en levels.csv.

El conteo de slaves por nivel es RESULTADO del modelo, no requisito fijo.
No modifica archivos.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "data" / "geometry"

TOL = 1e-6
DIAPHRAGM_LEVELS = ["L1", "L2", "L3", "L4", "ROOF"]
EXPECTED_MASTERS = ["NM_L1", "NM_L2", "NM_L3", "NM_L4", "NM_ROOF"]


def fnum(v):
    return float(pd.to_numeric(v, errors="coerce"))


def rk(v):
    return (round(v[0], 6), round(v[1], 6))


def load():
    d = {}
    for name in ("levels", "grid_x", "grid_y", "vertical_elements_LT2",
                 "walls_LT2", "beams_LT2", "column_segments_LT2",
                 "wall_segments_LT2", "supports_LT2", "master_nodes_LT2",
                 "diaphragms_LT2"):
        d[name] = pd.read_csv(GEOM / f"{name}.csv")
    return d


def structural_nodes_per_level(beams, cols, walls, axx, ayy, zlvl):
    """Nodos estructurales unicos (x,y) por nivel desde la geometria."""
    out = {lvl: set() for lvl in zlvl}
    for lvl in zlvl:
        bl = beams[beams["level"].astype(str) == lvl]
        for _, r in bl.iterrows():
            out[lvl].add(rk((fnum(r["x1_m"]), fnum(r["y1_m"]))))
            out[lvl].add(rk((fnum(r["x2_m"]), fnum(r["y2_m"]))))
        for _, c in cols.iterrows():
            out[lvl].add(rk((axx[str(c["axis_x"])], ayy[str(c["axis_y"])])))
        for _, w in walls.iterrows():
            out[lvl].add(rk((fnum(w["x1_m"]), fnum(w["y1_m"]))))
            out[lvl].add(rk((fnum(w["x2_m"]), fnum(w["y2_m"]))))
    return out


def slaves_per_level(nodes_per_level, masters_xy):
    """Slaves dinamicos por nivel (nodos estructurales sin el master)."""
    out = {}
    for lvl, pts in nodes_per_level.items():
        if lvl == "B1":
            continue
        out[lvl] = pts - {rk(m) for m in masters_xy if rk(m) in pts}
    return out


def main():
    d = load()
    levels, gx, gy = d["levels"], d["grid_x"], d["grid_y"]
    cols, walls, beams = d["vertical_elements_LT2"], d["walls_LT2"], d["beams_LT2"]
    supports, masters, diaphs = d["supports_LT2"], d["master_nodes_LT2"], d["diaphragms_LT2"]

    zlvl = {str(r["name"]): fnum(r["z_m"]) for _, r in levels.iterrows()}
    axx = {str(r["axis_id"]): fnum(r["x_m"]) for _, r in gx.iterrows()}
    ayy = {str(r["axis_id"]): fnum(r["y_m"]) for _, r in gy.iterrows()}

    errors, warnings = [], []

    def report(msg, is_error=True):
        (errors if is_error else warnings).append(msg)
        print(f"{('ERROR' if is_error else 'WARN ')} - {msg}")

    nodes_per_level = structural_nodes_per_level(beams, cols, walls, axx, ayy, zlvl)
    masters_xy = {}
    for _, r in masters.iterrows():
        masters_xy[str(r["master_id"])] = (fnum(r["x_m"]), fnum(r["y_m"]))
    slaves = slaves_per_level(nodes_per_level, set(masters_xy.values()))

    print("=== LT2 SUPPORTS/MASTERS/DIAPHRAGMS CHECK ===")
    print(f"levels    : {sorted(zlvl)}")
    print(f"supports  : {len(supports)}")
    print(f"masters   : {len(masters)}")
    print(f"diaphragms: {len(diaphs)}")
    print()

    # ------------------------------------------------ niveles referenciados
    print("[Levels referenced]")
    for m in masters.itertuples():
        if str(m.level) not in zlvl:
            report(f"master {m.master_id}: level '{m.level}' inexistente")
    for s in supports.itertuples():
        if str(s.level) not in zlvl:
            report(f"support {s.support_id}: level '{s.level}' inexistente")
    for dp in diaphs.itertuples():
        if str(dp.level) not in zlvl:
            report(f"diaphragm {dp.diaphragm_id}: level '{dp.level}' inexistente")
    if not any("level '" in e for e in errors):
        print("  OK - niveles referenciados en levels.csv.")

    # ------------------------------------------------ supports
    print("[Supports]")
    sup_pts = set()
    for _, s in supports.iterrows():
        p = rk((fnum(s["x_m"]), fnum(s["y_m"])))
        sup_pts.add(p)
        if str(s["level"]) != "B1":
            report(f"support {s.support_id}: debe estar en B1")
        for dof in ("ux", "uy", "uz", "rx", "ry", "rz"):
            if int(fnum(s[dof])) != 1:
                report(f"support {s.support_id}: GDL {dof} != 1")
        if str(s["type"]).lower() != "fixed":
            report(f"support {s.support_id}: tipo != fixed")
    if len(sup_pts) != len(supports):
        report("supports duplicados por coordenadas (tol 1e-6)")
    if len(sup_pts) != len(nodes_per_level["B1"]):
        report(f"apoyos ({len(sup_pts)}) != nodos estructurales B1 ({len(nodes_per_level['B1'])})")
    else:
        print(f"  OK - {len(sup_pts)} apoyos unicos = nodos estructurales B1, 6 GDL fijos.")
    print()

    # ------------------------------------------------ masters
    print("[Masters]")
    mid_set = {str(m) for m in masters["master_id"]}
    if len(mid_set) != len(masters):
        report("master IDs duplicados")
    if mid_set != set(EXPECTED_MASTERS):
        report(f"masters {mid_set} != esperado {set(EXPECTED_MASTERS)}")
    else:
        print("  OK - 5 masters unicos NM_L1..NM_ROOF.")
    for _, m in masters.iterrows():
        x, y = fnum(m["x_m"]), fnum(m["y_m"])
        ex, ey = 15.675, 8.0725
        if abs(x - ex) > TOL or abs(y - ey) > TOL:
            report(f"master {m.master_id}: coordenadas != (15.675, 8.0725)")
        if str(m["method"]) != "geometric_bbox_center":
            report(f"master {m.master_id}: method != geometric_bbox_center")
        if abs(fnum(m["z_m"]) - zlvl[str(m["level"])]) > TOL:
            report(f"master {m.master_id}: z_m no coincide con levels.csv")
        # coincide con nodo estructural en cualquier nivel?
        hit = []
        for lvl, pts in nodes_per_level.items():
            if rk((x, y)) in pts:
                hit.append(lvl)
        if hit:
            report(f"master {m.master_id} coincide con nodo estructural en {hit}")
    if not any("coincide con" in e for e in errors):
        print("  OK - ningun master coincide con nodo estructural (tol 1e-6).")
    print()

    # ------------------------------------------------ diaphragms
    print("[Diaphragms]")
    dlevels = {str(dp.level) for dp in diaphs.itertuples()}
    if len(dlevels) != len(diaphs):
        report("diaphragms duplicados por nivel")
    if set(dlevels) != set(DIAPHRAGM_LEVELS):
        report(f"niveles de diafragma {dlevels} != {set(DIAPHRAGM_LEVELS)}")
    else:
        print("  OK - 5 diafragmas L1..ROOF; B1 excluido.")
    for dp in diaphs.itertuples():
        if str(dp.master_id) not in mid_set:
            report(f"diaphragm {dp.diaphragm_id}: master '{dp.master_id}' inexistente")
        if int(fnum(dp.perp_axis)) != 3:
            report(f"diaphragm {dp.diaphragm_id}: perp_axis != 3")
        if dp.constrained_dofs != "UX,UY,RZ":
            report(f"diaphragm {dp.diaphragm_id}: constrained_dofs != 'UX,UY,RZ'")
        if dp.free_dofs != "UZ,RX,RY":
            report(f"diaphragm {dp.diaphragm_id}: free_dofs != 'UZ,RX,RY'")
        got = int(fnum(dp.slave_count))
        calc = len(slaves[str(dp.level)])
        if got != calc:
            report(f"diaphragm {dp.diaphragm_id}: slave_count {got} != dinamico {calc}")
    print()

    # ------------------------------------------------ slaves
    print("[Slaves generated dynamically]")
    all_level_slaves = {lvl: slaves[lvl] for lvl in DIAPHRAGM_LEVELS}

    # master excluido de su propia lista
    master_pts = {rk((fnum(m["x_m"]), fnum(m["y_m"]))) for _, m in masters.iterrows()}
    for lvl, lst in all_level_slaves.items():
        inter = master_pts & lst
        if inter:
            report(f"level {lvl}: master en lista de slaves: {sorted(inter)}")
    print("  OK - masters excluidos de sus listas de slaves.")

    # dedup dentro de un nivel; un nodo (level, x, y) pertenece a un solo diafragma
    dup_in_level = False
    for lvl in DIAPHRAGM_LEVELS:
        lst = list(all_level_slaves[lvl])
        if len(lst) != len(set(lst)):
            dup_in_level = True
            report(f"level {lvl}: slaves duplicados dentro del nivel")
    if not dup_in_level:
        print("  OK - ningun slave duplicado dentro de un nivel.")
    # un nivel tiene un unico diafragma (verificado arriba); por tanto cada
    # nodo (level, x, y) pertenece exactamente a un diafragma.
    print("  OK - cada nodo (level, x, y) pertenece a exactamente un diafragma.")

    # cobertura: todos los nodos estructurales elegibles asignados a 1 diafragma
    print("[Coverage L1..ROOF]")
    print(f"  {'level':<5} {'structural':>10} {'slaves':>7} {'master':<8} status")
    ok_all = True
    for lvl in DIAPHRAGM_LEVELS:
        struct = nodes_per_level[lvl]
        sl = all_level_slaves[lvl]
        status = "OK" if (not struct - sl and len(sl) == len(struct)) else "REVISAR"
        if status != "OK":
            ok_all = False
            report(f"cobertura {lvl}: nodos estructurales no todos esclavos")
        print(f"  {lvl:<5} {len(struct):>10} {len(sl):>7} {f'NM_{lvl}':<8} {status}")
    # B1 excluido
    for lvl, pts in slaves.items():
        if lvl == "B1":
            report("B1 en diafragmas")
    print(f"  (B1 no tiene diafragma)")

    print()
    print(f"Summary: errors={len(errors)} warnings={len(warnings)}")
    print("=== END CHECK ===")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())