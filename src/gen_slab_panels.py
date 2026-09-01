# -*- coding: utf-8 -*-
"""Generador reproducible de paños de losa LT2 (BLOQUE 2A).

La topología de paños se deriva de la grilla de vigas digitalizada en
data/geometry/beams_LT2.csv (compatible con el modelo) y de la documentación
de huecos de escalera (reports/digitalizacion_vi_roof_pendiente.md).

Bloques:
  - Planta tipo L1-L4 (plano 101): recinto continuo x[0.4, 31.25] y[0, 16.15]
    particionado por líneas de viga. Reutiliza plantilla TYP para L1..L4.
  - ROOF (plano 102): mismos bloques base, RESTANDO los huecos de escalera
    documentados (hueco principal x[0.998,16.546] y[2.90,7.92]; 2º hueco este).

Salida: data/loads/slab_panels_LT2.csv

No calcula áreas tributarias (bloque posterior). No modifica vigas/nodos/muros.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "loads" / "slab_panels_LT2.csv"

G = 9.81

# --------------------------------------------------------------------------
# Plantilla típica L1-L4: celdas rectangulares definidas por la grilla de vigas
# Bloque IZQUIERDO (x 0.4 -> 11.25), filas y[0,4.265,8.9,11.885,16.15]
# y columnas x[0.4,3.75,7.5,11.25]  -> 3 columnas x 4 filas
# Bloque DERECHO   (x 11.25 -> 31.25), filas y[0,8.9,16.15]
# y columnas x[11.25,16.25,21.25,26.25,31.25] -> 4 columnas x 2 filas
# --------------------------------------------------------------------------

LEFT_Y = [0.0, 4.265, 8.9, 11.885, 16.15]
LEFT_X = [0.4, 3.75, 7.5, 11.25]
RIGHT_Y = [0.0, 8.9, 16.15]
RIGHT_X = [11.25, 16.25, 21.25, 26.25, 31.25]

# --------------------------------------------------------------------------
# Huecos CONFIRMADOS de planta tipo (plan 101, validacion visual L1-L4)
# --------------------------------------------------------------------------
# Abertura principal del nucleo derecho en RB_c3_r0, delimitada por los muros
# M.H.A. ya digitalizados (M005 x=28.205 e=25; M006 y=3.180 e=30; M007
# x=31.250 e=25). Coincide con el recinto x[28.205,31.25] y[3.180,6.275].
NUCLEO_DERECHO_HOLE = (28.205, 3.180, 31.250, 6.275)

# Abertura rectangular alargada ADYACENTE al nucleo, vista en plan 101 pero sin
# geometria determinable de forma segura desde el plano/elementos digitalizados.
# Se registra como hole PENDIENTE (PENDING_GEOMETRY_CONFIRMATION), sin restar area.
NUCLEO_ADYACENTE_PENDIENTE = "abertura rectangular alargada adyacente al nucleo derecho (RB_c3_r0); coordenadas por confirmar en plan 101"


def poly_str(x0, y0, x1, y1):
    """Poligono cerrado (sentido antihorario) como texto trazable."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return ";".join(f"{x:.6f},{y:.6f}" for x, y in pts)


def hole_rects_str(holes):
    """Convierte lista de huecos (x0,y0,x1,y1) a texto; vacio si no hay huecos."""
    if not holes:
        return ""
    return "|".join(poly_str(*h) for h in holes)


def area_rect(x0, y0, x1, y1):
    return abs(x1 - x0) * abs(y1 - y0)


def cells_leftblock():
    out = []
    for ci in range(len(LEFT_X) - 1):
        x0, x1 = LEFT_X[ci], LEFT_X[ci + 1]
        for ri in range(len(LEFT_Y) - 1):
            y0, y1 = LEFT_Y[ri], LEFT_Y[ri + 1]
            cid = f"LB_c{ci}_r{ri}"
            out.append((cid, x0, y0, x1, y1))
    return out


def cells_rightblock():
    out = []
    for ci in range(len(RIGHT_X) - 1):
        x0, x1 = RIGHT_X[ci], RIGHT_X[ci + 1]
        for ri in range(len(RIGHT_Y) - 1):
            y0, y1 = RIGHT_Y[ri], RIGHT_Y[ri + 1]
            cid = f"RB_c{ci}_r{ri}"
            out.append((cid, x0, y0, x1, y1))
    return out


# --------------------------------------------------------------------------
# Huecos documentados de ROOF (plano 102, reports V.I.)
# --------------------------------------------------------------------------
def rect_overlap_frac(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1):
    ox0, ox1 = max(ax0, bx0), min(ax1, bx1)
    oy0, oy1 = max(ay0, by0), min(ay1, by1)
    if ox1 <= ox0 or oy1 <= oy0:
        return 0.0
    overlap = area_rect(ox0, oy0, ox1, oy1)
    return overlap


def subtract_hole_frac(cx0, cy0, cx1, cy1, holes):
    """Fraccion (0..1) del panel cubierta por huecos y centroide aproximado."""
    tot = area_rect(cx0, cy0, cx1, cy1)
    sub = sum(rect_overlap_frac(cx0, cy0, cx1, cy1, *h) for h in holes)
    return min(sub / tot, 1.0)


def build_rows():
    rows = []

    # ---- L1..L4 (plantilla tipo, plan 101) ----
    # Nomenclatura de estado:
    #   CONFIRMED_SLAB            -> evidencia visual explicita (plan 101)
    #   PENDING_VISUAL_CONFIRMATION-> derivado solo por descomposicion de grilla
    #                                (NO se llama CONFIRMADO a regiones sin
    #                                 evidencia visual individual)
    EVIDENCIA_VISUAL = {"LB_c0_r0": "simbolo losa 0101/15 (plan 101)",
                        "LB_c0_r3": "simbolo losa 0114/15 (plan 101)",
                        "RB_c3_r0": "losa 15 cm con abertura(s) de nucleo (plan 101)"}
    for lvl in ["L1", "L2", "L3", "L4"]:
        panels = cells_leftblock() + cells_rightblock()
        for cid, x0, y0, x1, y1 in panels:
            p = f"{lvl}_P_{cid}"
            base_area = area_rect(x0, y0, x1, y1)

            if cid in EVIDENCIA_VISUAL:
                status = "CONFIRMED_SLAB"
                notes = f"LOSA {EVIDENCIA_VISUAL[cid]}; espesor 15 cm"
            else:
                status = "PENDING_VISUAL_CONFIRMATION"
                notes = "paño derivado por descomposicion automatica de grilla (plan 101); sin confirmacion visual individual"

            holes, hole_status = [], ""
            if cid == "RB_c3_r0":
                # abertura principal del nucleo, delimitada por M.H.A. (confirmada)
                holes = [NUCLEO_DERECHO_HOLE]
                hole_status = "CONFIRMED"
                # abertura alargada adyacente: geometria no determinable con
                # seguridad -> pendiente de confirmacion (no resta area)
                hole_status += ";PENDING_GEOMETRY_CONFIRMATION"
                notes += f"; hole_pending={NUCLEO_ADYACENTE_PENDIENTE}"

            net_area = base_area
            for h in holes:
                net_area -= area_rect(*h)
            rows.append({
                "panel_id": p,
                "level": lvl,
                "source_plan": "2024_22-101-Model",
                "slab_id": f"S_{lvl}_TYP",
                "polygon": poly_str(x0, y0, x1, y1),
                "area_m2": round(max(net_area, 0.0), 6),
                "holes": hole_rects_str(holes),
                "hole_status": hole_status,
                "thickness_m": 0.15,
                "qG_kN_m2": round(635 * G / 1000, 6),
                "status": status,
                "template": "TYP",
                "notes": notes,
            })

    # ---- ROOF ----
    holes = [(0.998, 2.90, 16.546, 7.92),
             (18.52, 2.92, 21.295, 7.92)]
    roof_panels = cells_leftblock() + cells_rightblock()
    for cid, x0, y0, x1, y1 in roof_panels:
        frac = subtract_hole_frac(x0, y0, x1, y1, holes)
        p = f"ROOF_P_{cid}"
        presence = "CONFIRMADO" if frac < 1e-9 else (
            "PARCIAL_ABERTURA" if 0 < frac < 0.999 else "ABERTURA")
        if frac >= 0.999:
            # panel totalmente cubierto por hueco -> no hay losa
            status = "SIN_LOSA_HUECO"
            notes = "paño totalmente dentro de hueco de escalera documentado (plano 102)"
            area_eff = 0.0
        elif frac > 1e-9:
            status = "PENDING_VISUAL_CONFIRMATION"
            notes = (f"paño intersectado por hueco de escalera documentado "
                     f"(fracción restante={1-frac:.3f}); espesor ROOF pendiente")
            area_eff = round(area_rect(x0, y0, x1, y1) * (1 - frac), 6)
        else:
            status = "CONFIRMADO"
            notes = "paño base ROOF; espesor/e pendiente de plan 102"
            area_eff = round(area_rect(x0, y0, x1, y1), 6)
        rows.append({
            "panel_id": p,
            "level": "ROOF",
            "source_plan": "2024_22-102-Model",
            "slab_id": "S_ROOF_TYP",
            "polygon": poly_str(x0, y0, x1, y1),
            "area_m2": area_eff,
            "holes": "",
            "hole_status": "",
            "thickness_m": None,
            "qG_kN_m2": None,
            "status": status,
            "template": "ROOF",
            "notes": notes,
        })

    return rows


def main():
    rows = build_rows()
    df = pd.DataFrame(rows, columns=[
        "panel_id", "level", "source_plan", "slab_id", "polygon", "area_m2",
        "holes", "hole_status", "thickness_m", "qG_kN_m2", "status",
        "template", "notes",
    ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Escrito: {OUT}")
    print("Paneles por nivel:")
    cnt = df.groupby("level").size()
    area = df.groupby("level")["area_m2"].sum()
    for lvl in ["L1", "L2", "L3", "L4", "ROOF"]:
        if lvl in cnt.index:
            print(f"  {lvl:<5} paneles={cnt[lvl]:>3}  area_total_losa={area[lvl]:10.3f} m2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
