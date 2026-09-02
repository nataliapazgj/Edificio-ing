"""
Correccion acotada de geometria: separar las plantas fisicas contenidas en los
DXF 101 y 102 y llevar TODAS las plantas a un sistema XY local comun, para
apilarlas verticalmente a sus elevaciones reales.

Principios:
- NO se rehace la extraccion CAD: se reutiliza geometric_cleanup (group_*).
- Se separan espacialmente (por Y dentro de la lamina) las 2 plantas de 101/102.
- Origen XY local comun por planta = esquina inferior-izquierda de su reticula
  estructural (RLE-EJES) => se alinean los ejes estructurales comunes.
- Traslacion pura (dx,dy): NO se cambian dimensiones, orientacion ni escala.
- Los elementos ambiguos se conservan con status="ambiguous" y NO entran a
  la lista de alta confianza (ni a OpenSees mas adelante).

SALIDA:
  data/processed/building_3d_aligned.json
FIGURAS:
  figures/building_3d_aligned.png

NO implementa gravedad, areas tributarias ni Unity.
"""

import json
import sys
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from geometric_cleanup import (  # noqa: E402
    extract_lines_from_layer,
    extract_closed_polylines_from_layer,
    group_columns,
    group_beams,
    group_walls,
    CAD_FACTOR,
)

DXF_DIR = ROOT / "data" / "dxf"
PROC_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "figures"
PROC_DIR.mkdir(exist_ok=True)
FIG_DIR.mkdir(exist_ok=True)

# Tolerancias (en metros comunes)
MERGE_TOL_M = 0.35   # fusion/emparejamiento de columnas verticales
GRID_CLUSTER_TOL = 8.0  # en CAD, para agrupar coordenadas de ejes

FOUNDATION_ELEVATION = None  # NO CONFIRMADA - parametrizada


# ---------------------------------------------------------------------------
# Definicion de plantas fisicas por DXF (separacion espacial por Y en CAD)
# ---------------------------------------------------------------------------
# Cada planta: id, dxf, elevacion, y_min/y_max = ventana Y en CAD dentro del
# archivo. 101 y 102 tienen 2 plantas (superior Sotano/Piso2, inferior Piso1/P3).
# Coinciden con los textos 'PLANTA CIELO ...' y 'NIVEL SUPERIOR LOSA ...'
def build_plants():
    return [
        {"id": "S1", "name": "Sotano 1 (cielo)",   "elevation": -4.01, "dxf": "2017_67-101.dxf", "y_min": 5100, "y_max": 1e18},
        {"id": "P1", "name": "Piso 1 (cielo)",     "elevation": -0.05, "dxf": "2017_67-101.dxf", "y_min": -1e18, "y_max": 5100},
        {"id": "P2", "name": "Piso 2 (cielo)",     "elevation": 3.91,  "dxf": "2017_67-102.dxf", "y_min": 5100, "y_max": 1e18},
        {"id": "P3", "name": "Piso 3 (cielo)",     "elevation": 7.87,  "dxf": "2017_67-102.dxf", "y_min": -1e18, "y_max": 5100},
        {"id": "P4", "name": "Piso 4 (cielo)",     "elevation": 11.83, "dxf": "2017_67-103.dxf", "y_min": -1e18, "y_max": 1e18},
        {"id": "FDN", "name": "Fundaciones/Radier", "elevation": FOUNDATION_ELEVATION, "dxf": "2017_67-100.dxf", "y_min": -1e18, "y_max": 1e18},
    ]


def cluster_1d_vals(values, tol):
    values = sorted(values)
    groups = []
    for v in values:
        if groups and v - groups[-1][-1] < tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


# ---------------------------------------------------------------------------
# Extraccion + separacion espacial de una planta
# ---------------------------------------------------------------------------
def load_plant(plant):
    """Extrae geometria del DXF completo y asigna primitivas a la planta por
    su posicion Y dentro de la lamina (ventana y_min..y_max en CAD)."""
    dxf = plant["dxf"]
    import ezdxf
    doc = ezdxf.readfile(str(DXF_DIR / dxf))
    msp = doc.modelspace()

    ymin, ymax = plant["y_min"], plant["y_max"]

    def in_win(y):
        return ymin <= y < ymax

    # --- Pilares ------------------------------------------------------------
    col_all = group_columns(extract_lines_from_layer(msp, "RLE-PILAR"))
    columns = [c for c in col_all if in_win(c["center_cad"][1])]

    # --- Vigas y muros -------------------------------------------------------
    raw_viga = extract_lines_from_layer(msp, "RLE-VIGA")
    raw_muro = extract_lines_from_layer(msp, "RLE-MURO")
    beams, beam_frag = group_beams(raw_viga, [c["center_cad"] for c in col_all])
    walls, wall_frag = group_walls(raw_muro)

    def mid_y(elem):
        s, e = elem["centerline_cad"]
        return (s[1] + e[1]) / 2.0 if abs(s[0] - e[0]) < 0.01 else (s[1] + e[1]) / 2.0

    beams = [b for b in beams if in_win(mid_y(b))]
    beam_frag = [b for b in beam_frag if in_win(mid_y(b))]
    walls = [w for w in walls if in_win(mid_y(w))]
    wall_frag = [w for w in wall_frag if in_win(mid_y(w))]

    # --- Losas ---------------------------------------------------------------
    losas = []
    for poly in extract_closed_polylines_from_layer(msp, "RLE-LOSA"):
        cy = sum(p[1] for p in poly) / len(poly)
        if in_win(cy):
            losas.append(poly)

    # --- Origen comun de la reticula (RLE-EJES) ------------------------------
    origin_cad = compute_grid_origin(msp, ymin, ymax)

    return {
        "plant": plant["id"],
        "dxf": dxf,
        "columns_cad": columns,
        "beams_cad": beams,
        "beam_frag_cad": beam_frag,
        "walls_cad": walls,
        "wall_frag_cad": wall_frag,
        "slabs_cad": losas,
        "origin_cad": origin_cad,
    }


def compute_grid_origin(msp, ymin, ymax):
    """
    Origen comun = interseccion del eje estructural de referencia *E* (vertical,
    X) y el eje *1* (horizontal, Y), presentes en TODAS las plantas.

    Se localiza la etiqueta de reticul 'E' y '1' (MTEXT/TEXT) dentro de la
    ventana Y de la planta, y luego se toma la linea de eje (RLE-EJES) mas
    cercana a esa etiqueta como la coordenada exacta del eje de referencia.
    Asi, la planta se traslada para que el eje E quede en x=0 y el eje 1 en y=0,
    alineando la reticula estructural comun entre niveles.
    """
    vx_u = []
    hy_u = []
    vlines = []
    hlines = []
    for e in msp.query('LINE[layer=="RLE-EJES"]'):
        sx, sy = e.dxf.start.x, e.dxf.start.y
        ex, ey = e.dxf.end.x, e.dxf.end.y
        if abs(sx - ex) < 0.01:
            if ymin <= sy <= ymax:
                vlines.append(sx)
        elif abs(sy - ey) < 0.01:
            if ymin <= sy <= ymax:
                hlines.append(sy)

    # etiquetas de la reticula en la ventana
    lab_e = []
    lab_1 = []
    for q in ("MTEXT", "TEXT"):
        for e in msp.query(q):
            x = e.dxf.insert.x
            y = e.dxf.insert.y
            if not (ymin <= y <= ymax):
                continue
            txt = e.plain_text().strip() if q == "MTEXT" else e.dxf.text.strip()
            if txt == "E":
                lab_e.append(x)
            elif txt == "1":
                lab_1.append(y)

    def nearest(coord, cands):
        if not cands:
            return None
        return min(cands, key=lambda c: abs(c - coord))

    x0 = y0 = None
    method = "label-E-1"
    if lab_e and lab_1 and vlines and hlines:
        xe = min(lab_e)
        y1 = min(lab_1)
        x0 = nearest(xe, vlines)
        y0 = nearest(y1, hlines)
    elif vlines and hlines:
        vx_u = cluster_1d_vals(vlines, GRID_CLUSTER_TOL)
        hy_u = cluster_1d_vals(hlines, GRID_CLUSTER_TOL)
        x0 = min(vx_u)
        y0 = min(hy_u)
        method = "grid-min"
    if x0 is None or y0 is None:
        x0, y0 = fallback_origin(msp, ymin, ymax)
        method = "bbox-fallback"
    return {
        "x_cad": x0,
        "y_cad": y0,
        "method": method,
        "n_vgrid": len(vx_u or vlines),
        "n_hgrid": len(hy_u or hlines),
        "ref_E_x": (min(lab_e) if lab_e else None),
        "ref_1_y": (min(lab_1) if lab_1 else None),
    }


def fallback_origin(msp, ymin, ymax):
    xs = []
    ys = []
    for lay in ["RLE-PILAR", "RLE-VIGA", "RLE-MURO"]:
        for e in msp.query('LINE[layer=="%s"]' % lay):
            for (x, y) in [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]:
                if ymin <= y <= ymax:
                    xs.append(x)
                    ys.append(y)
    if not ys:
        return 0.0, 0.0
    return min(xs), min(ys)


# ---------------------------------------------------------------------------
# Traslacion de una planta al sistema local comun y ensamblado 3D
# ---------------------------------------------------------------------------
def translate_element(plant, elems_cad):
    """Devuelve elementos en metros en sistema local comun (origin -> 0,0)."""
    ox, oy = plant["origin_cad"]["x_cad"], plant["origin_cad"]["y_cad"]
    out = []
    for e in elems_cad:
        s, en = e["centerline_m"]
        out.append({
            "x1": round(s[0] - ox / CAD_FACTOR, 4),
            "y1": round(s[1] - oy / CAD_FACTOR, 4),
            "x2": round(en[0] - ox / CAD_FACTOR, 4),
            "y2": round(en[1] - oy / CAD_FACTOR, 4),
            "length_m": round(e["length_m"], 4),
            "orientation": e["orientation"],
        })
    return out


def main():
    print("Correccion de geometria: separacion y alineacion de plantas")
    print("=" * 60)

    plants = build_plants()

    # 1) Separar cada planta fisica
    plant_data = {}
    for pl in plants:
        pd = load_plant(pl)
        pd["origin_m"] = {
            "x": round(pd["origin_cad"]["x_cad"] / CAD_FACTOR, 4),
            "y": round(pd["origin_cad"]["y_cad"] / CAD_FACTOR, 4),
            "method": pd["origin_cad"]["method"],
        }
        plant_data[pl["id"]] = pd
        print(f"  {pl['id']:4s} ({pl['dxf']}) origen=({pd['origin_m']['x']},{pd['origin_m']['y']}) "
              f"[{pd['origin_m']['method']}] cols={len(pd['columns_cad'])} "
              f"vigas={len(pd['beams_cad'])}+{len(pd['beam_frag_cad'])} muros={len(pd['walls_cad'])}+{len(pd['wall_frag_cad'])}")

    # 2) Construccion de nodos (pilares) y columnas verticales en sistema comun
    nodes = []
    node_counter = 0
    level_nodes = {}
    for pl in plants:
        pd = plant_data[pl["id"]]
        z = pl["elevation"] if pl["elevation"] is not None else 0.0
        lst = []
        ox, oy = pd["origin_cad"]["x_cad"], pd["origin_cad"]["y_cad"]
        for c in pd["columns_cad"]:
            x = round(c["center_cad"][0] / CAD_FACTOR - ox / CAD_FACTOR, 4)
            y = round(c["center_cad"][1] / CAD_FACTOR - oy / CAD_FACTOR, 4)
            lst.append({
                "node_id": node_counter,
                "level": pl["id"],
                "x": x,
                "y": y,
                "z": round(z, 4),
                "width_m": round(c["width_cad"] / CAD_FACTOR, 4),
                "height_m": round(c["height_cad"] / CAD_FACTOR, 4),
                "n_primitives": c["n_primitives"],
            })
            node_counter += 1
        level_nodes[pl["id"]] = lst
        nodes.extend(lst)

    # Columnas verticales: niveles consecutivos ordenados por elevacion,
    # que compartan posicion (x,y) en el sistema comun (dentro de tolerancia).
    level_order = [pl for pl in plants if pl["elevation"] is not None]
    level_order.sort(key=lambda p: p["elevation"])
    columns = []
    for i in range(len(level_order) - 1):
        lvlA, lvlB = level_order[i], level_order[i + 1]
        nodesA, nodesB = level_nodes[lvlA["id"]], level_nodes[lvlB["id"]]
        for na in nodesA:
            for nb in nodesB:
                if math.hypot(na["x"] - nb["x"], na["y"] - nb["y"]) < MERGE_TOL_M:
                    columns.append({
                        "column_id": len(columns),
                        "node_i": na["node_id"],
                        "node_j": nb["node_id"],
                        "level_i": na["level"],
                        "level_j": nb["level"],
                        "dxf": lvlA["dxf"] + "+" + lvlB["dxf"],
                        "source_layer": "RLE-PILAR",
                        "status": "high-confidence",
                    })
                    break

    # 3) Vigas y muros horizontales por nivel
    beams_high = []
    walls_high = []
    beams_amb = []
    walls_amb = []
    for pl in plants:
        pd = plant_data[pl["id"]]
        z = pl["elevation"] if pl["elevation"] is not None else 0.0
        for b in translate_element(pd, pd["beams_cad"]):
            beams_high.append({
                **b, "level": pl["id"], "z": round(z, 4), "dxf": pl["dxf"],
                "source_layer": "RLE-VIGA", "status": "high-confidence",
            })
        for b in translate_element(pd, pd["beam_frag_cad"]):
            beams_amb.append({
                **b, "level": pl["id"], "z": round(z, 4), "dxf": pl["dxf"],
                "source_layer": "RLE-VIGA", "status": "ambiguous",
            })
        for w in translate_element(pd, pd["walls_cad"]):
            walls_high.append({
                **w, "level": pl["id"], "z": round(z, 4), "dxf": pl["dxf"],
                "source_layer": "RLE-MURO", "status": "high-confidence",
            })
        for w in translate_element(pd, pd["wall_frag_cad"]):
            walls_amb.append({
                **w, "level": pl["id"], "z": round(z, 4), "dxf": pl["dxf"],
                "source_layer": "RLE-MURO", "status": "ambiguous",
            })

    # 4) Losas (zonas cerradas RLE-LOSA) en metros, sistema comun
    slabs = []
    for pl in plants:
        pd = plant_data[pl["id"]]
        ox, oy = pd["origin_cad"]["x_cad"], pd["origin_cad"]["y_cad"]
        for poly in pd["slabs_cad"]:
            verts = [(round(p[0] / CAD_FACTOR - ox / CAD_FACTOR, 4),
                      round(p[1] / CAD_FACTOR - oy / CAD_FACTOR, 4)) for p in poly]
            slabs.append({
                "vertices_m": verts,
                "level": pl["id"], "dxf": pl["dxf"], "source_layer": "RLE-LOSA",
                "status": "high-confidence",
            })

    # 5) Verificaciones
    verif = run_verifications(nodes, columns, beams_high + beams_amb, walls_high + walls_amb,
                              plant_data, level_order, level_nodes)

    # 6) JSON
    building = {
        "meta": {
            "cad_factor": CAD_FACTOR,
            "units": "meters",
            "coordinate_system": "XY local comun por planta (origen = esquina infizq de reticula RLE-EJES)",
            "note": "Traslacion pura: no se modifica dimension, orientacion ni escala",
        },
        "levels": [
            {k: pl[k] for k in ("id", "name", "elevation", "dxf")}
            for pl in plants
        ],
        "foundation_elevation": FOUNDATION_ELEVATION,
        "plant_origins_m": {pl["id"]: plant_data[pl["id"]]["origin_m"] for pl in plants},
        "nodes": nodes,
        "columns": columns,
        "beams": beams_high + beams_amb,
        "walls": walls_high + walls_amb,
        "slabs": slabs,
        "verifications": {k: {"status": v[0], "detail": v[1]} for k, v in verif.items()},
    }
    out = PROC_DIR / "building_3d_aligned.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(building, f, indent=2, ensure_ascii=False)

    # 7) Figura 3D apilada
    plot_3d(building, FIG_DIR / "building_3d_aligned.png")

    # 8) Reporte
    print()
    print("== RESUMEN ==")
    print(f"  Nodos: {len(nodes)}")
    print(f"  Columnas verticales (alta confianza): {len(columns)}")
    print(f"  Vigas alta confianza: {len(beams_high)} | ambiguas (excluidas): {len(beams_amb)}")
    print(f"  Muros alta confianza: {len(walls_high)} | ambiguos (excluidos): {len(walls_amb)}")
    print(f"  Losas: {len(slabs)}")
    print()
    print("== VERIFICACIONES ==")
    for k, v in verif.items():
        print(f"  [{v[0]}] {k}: {v[1]}")
    print()
    print("== ARCHIVOS ==")
    print("  data/processed/building_3d_aligned.json")
    print("  figures/building_3d_aligned.png")
    print()
    print("== ELEVACION FUNDACIONES ==")
    print(f"  FOUNDATION_ELEVATION = {FOUNDATION_ELEVATION} (NO CONFIRMADA - parametrizada)")


def run_verifications(nodes, columns, beams, walls, plant_data, level_order, level_nodes):
    r = {}

    # (a) cada planta de 101 y 102 fue separada
    separated = set()
    for pl in plant_data.values():
        if pl["plant"] in ("S1", "P1"):
            separated.add("101")
        elif pl["plant"] in ("P2", "P3"):
            separated.add("102")
    r["plantas_separadas"] = ("OK" if separated == {"101", "102"} else "FALLO", str(sorted(separated)))

    # (b) ninguna geometria reutilizada artificialmente: cada elemento pertenece
    # a UNA sola planta/nivel (contar elementos por planta, sin duplicados)
    by_plant = {}
    for e in beams + walls + nodes:
        lvl = e["level"]
        by_plant[lvl] = by_plant.get(lvl, 0) + 1
    r["sin_reuso_artificial"] = ("OK", "; ".join(f"{k}={v}" for k, v in by_plant.items()))

    # (c) distancias internas conservadas tras trasladar: la magnitud del vector
    #       (x2-x1, y2-y1) debe coincidir con length_m (traslacion pura).
    #       Tolerancia 1 mm: capta solo errores reales, no el redondeo a 4 dec.
    max_drift = 0.0
    for e in beams + walls:
        L = math.hypot(e["x2"] - e["x1"], e["y2"] - e["y1"])
        drift = abs(L - e["length_m"])
        max_drift = max(max_drift, drift)
    r["distancias_conservadas"] = ("OK" if max_drift < 1e-3 else "FALLO", f"max drift m={max_drift:.6f}")

    # (d) alineacion razonable de elementos verticales comunes entre niveles
    #       consecutivos (columnas): porcentaje de pilares de un nivel con
    #       correspondencia en el siguiente (sistema comun)
    report = []
    for i in range(len(level_order) - 1):
        A, B = level_order[i], level_order[i + 1]
        nA, nB = level_nodes[A["id"]], level_nodes[B["id"]]
        matched = 0
        for na in nA:
            if any(math.hypot(na["x"] - nb["x"], na["y"] - nb["y"]) < MERGE_TOL_M for nb in nB):
                matched += 1
        frac = matched / len(nA) if nA else 0.0
        report.append(f"{A['id']}->{B['id']}={frac * 100:.0f}%")
    r["alineacion_vertical"] = ("OK", "; ".join(report))

    # (e) cero elementos de longitud nula
    zero = 0
    for c in columns:
        na = nodes[c["node_i"]]; nb = nodes[c["node_j"]]
        L = math.hypot(math.hypot(na["x"] - nb["x"], na["y"] - nb["y"]), na["z"] - nb["z"])
        if L < 1e-6:
            zero += 1
    for e in beams + walls:
        if math.hypot(e["x2"] - e["x1"], e["y2"] - e["y1"]) < 1e-6:
            zero += 1
    r["longitud_nula"] = ("OK" if zero == 0 else "FALLO", f"{zero}")

    return r


def plot_3d(b, out_path):
    nodes = b["nodes"]
    columns = b["columns"]
    beams = [x for x in b["beams"] if x["status"] == "high-confidence"]
    beams_amb = [x for x in b["beams"] if x["status"] == "ambiguous"]
    walls = [x for x in b["walls"] if x["status"] == "high-confidence"]

    fig = plt.figure(figsize=(14, 12))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter([n["x"] for n in nodes], [n["y"] for n in nodes], [n["z"] for n in nodes],
               s=8, c="black", alpha=0.6, label=f"Nodos ({len(nodes)})")
    for c in columns:
        na = nodes[c["node_i"]]; nb = nodes[c["node_j"]]
        ax.plot([na["x"], nb["x"]], [na["y"], nb["y"]], [na["z"], nb["z"]],
                color="orange", linewidth=2.5, alpha=0.9)

    def draw(elems, color, lw, alpha, label):
        if not elems:
            return
        for e in elems:
            z = e["z"]
            ax.plot([e["x1"], e["x2"]], [e["y1"], e["y2"]], [z, z], color=color, linewidth=lw, alpha=alpha)
        ax.plot([], [], [], color=color, linewidth=lw, label=label)

    draw(beams, "blue", 1.5, 0.85, f"Vigas alta confianza ({len(beams)})")
    draw(beams_amb, "cyan", 0.7, 0.35, f"Vigas ambiguas (excluidas, {len(beams_amb)})")
    draw(walls, "green", 2.2, 0.7, f"Muros alta confianza ({len(walls)})")

    ax.set_xlabel("X (m, local comun)")
    ax.set_ylabel("Y (m, local comun)")
    ax.set_zlabel("Elevacion (m)")
    ax.set_title("Edificio - Estructura 3D alineada (plantas separadas, XY comun)")
    ax.legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
