"""
Exploracion detallada de coordenadas, cotas y ejes de los DXF.
Fase preliminar para determinar el factor de conversion CAD->metros.
"""

import ezdxf
from pathlib import Path
from collections import defaultdict
import math
import json
import hashlib

ROOT = Path(__file__).resolve().parent.parent
DXF_DIR = ROOT / "data" / "dxf"

DXF_FILES = [
    "2017_67-100.dxf",
    "2017_67-101.dxf",
    "2017_67-102.dxf",
    "2017_67-103.dxf",
]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

hashes_before = {f: sha256(DXF_DIR / f) for f in DXF_FILES}

for fname in DXF_FILES:
    filepath = DXF_DIR / fname
    doc = ezdxf.readfile(str(filepath))
    msp = doc.modelspace()

    print("=" * 90)
    print(f"  {fname}")
    print("=" * 90)

    # ── 1. DIMENSION entities ─────────────────────────────────────────
    print("\n  --- DIMENSION entities ---")
    dims = [e for e in msp if e.dxftype() == "DIMENSION"]
    print(f"  Total: {len(dims)}")

    # Group by layer
    dim_by_layer = defaultdict(list)
    for d in dims:
        layer = d.dxf.layer
        dim_by_layer[layer].append(d)

    for layer in sorted(dim_by_layer.keys()):
        ents = dim_by_layer[layer]
        print(f"\n  Capa: {layer} ({len(ents)} dimensiones)")
        for i, d in enumerate(ents[:15]):  # primeras 15 por capa
            try:
                # Texto de la cota (el valor medido)
                text = d.dxf.text if hasattr(d.dxf, "text") else ""
                # Puntos de definicion
                p1 = d.dxf.defpoint if hasattr(d.dxf, "defpoint") else None
                p2 = d.dxf.defpoint2 if hasattr(d.dxf, "defpoint2") else None
                # Punto de texto
                ptext = d.dxf.text_midpoint if hasattr(d.dxf, "text_midpoint") else None

                # Distancia euclidiana entre defpoint y defpoint2
                if p1 and p2:
                    dx = p2.x - p1.x
                    dy = p2.y - p1.y
                    dist_cad = math.sqrt(dx*dx + dy*dy)
                else:
                    dist_cad = None

                # Tipo de cota
                dimtype = d.dxf.dimtype if hasattr(d.dxf, "dimtype") else "?"

                print(f"    [{i}] text='{text}'  distCAD={dist_cad:.4f if dist_cad else 'N/A':>12s}"
                      f"  dimtype={dimtype}"
                      f"  p1=({p1.x:.2f},{p1.y:.2f})" if p1 else ""
                      f"  p2=({p2.x:.2f},{p2.y:.2f})" if p2 else "")

            except Exception as ex:
                print(f"    [{i}] ERROR: {ex}")

    # ── 2. Axis lines (RLE-EJES) ─────────────────────────────────────
    print("\n  --- Ejes estructurales (RLE-EJES layer) ---")
    axis_lines = [e for e in msp if e.dxf.layer == "RLE-EJES" and e.dxftype() == "LINE"]
    print(f"  LINE entities en RLE-EJES: {len(axis_lines)}")
    for i, ln in enumerate(axis_lines[:30]):
        s = ln.dxf.start
        e = ln.dxf.end
        length = math.sqrt((e.x - s.x)**2 + (e.y - s.y)**2)
        print(f"    [{i}] ({s.x:.2f},{s.y:.2f}) -> ({e.x:.2f},{e.y:.2f})  L={length:.2f}")

    # Also check axis text from RLE-EJE (MTEXT entities)
    print("\n  --- Ejes (RLE-EJE MTEXT entities) ---")
    axis_texts = [e for e in msp if e.dxf.layer == "RLE-EJE" and e.dxftype() == "MTEXT"]
    print(f"  MTEXT entities en RLE-EJE: {len(axis_texts)}")
    for i, mt in enumerate(axis_texts[:40]):
        txt = mt.text if hasattr(mt, "text") else ""
        ins = mt.dxf.insert if hasattr(mt.dxf, "insert") else (0, 0, 0)
        print(f"    [{i}] text='{txt[:60]}'  pos=({ins.x:.2f},{ins.y:.2f})")

    # ── 3. Circles on RLE-EJE (axis bubbles) ─────────────────────────
    print("\n  --- Ejes (RLE-EJE CIRCLE entities) ---")
    axis_circles = [e for e in msp if e.dxf.layer == "RLE-EJE" and e.dxftype() == "CIRCLE"]
    print(f"  CIRCLE entities en RLE-EJE: {len(axis_circles)}")
    for i, c in enumerate(axis_circles[:40]):
        center = c.dxf.center
        radius = c.dxf.radius
        print(f"    [{i}] center=({center.x:.2f},{center.y:.2f})  r={radius:.2f}")

    # ── 4. RLE-PILAR lines ───────────────────────────────────────────
    print("\n  --- Pilares (RLE-PILAR) ---")
    pilar_lines = [e for e in msp if e.dxf.layer == "RLE-PILAR"]
    pilar_types = defaultdict(int)
    for e in pilar_lines:
        pilar_types[e.dxftype()] += 1
    print(f"  Entidades: {dict(pilar_types)}")
    for i, e in enumerate(pilar_lines[:20]):
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            length = math.sqrt((en.x - s.x)**2 + (en.y - s.y)**2)
            print(f"    LINE ({s.x:.2f},{s.y:.2f}) -> ({en.x:.2f},{en.y:.2f})  L={length:.2f}")
        elif e.dxftype() == "ARC":
            c = e.dxf.center
            r = e.dxf.radius
            print(f"    ARC center=({c.x:.2f},{c.y:.2f})  r={r:.2f}")

    # ── 5. RLE-VIGA lines ────────────────────────────────────────────
    print("\n  --- Vigas (RLE-VIGA) ---")
    viga_lines = [e for e in msp if e.dxf.layer == "RLE-VIGA"]
    viga_types = defaultdict(int)
    for e in viga_lines:
        viga_types[e.dxftype()] += 1
    print(f"  Entidades: {dict(viga_types)}")
    for i, e in enumerate(viga_lines[:20]):
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            length = math.sqrt((en.x - s.x)**2 + (en.y - s.y)**2)
            print(f"    LINE ({s.x:.2f},{s.y:.2f}) -> ({en.x:.2f},{en.y:.2f})  L={length:.2f}")

    # ── 6. RLE-MURO lines ────────────────────────────────────────────
    print("\n  --- Muros (RLE-MURO) ---")
    muro_ents = [e for e in msp if e.dxf.layer == "RLE-MURO"]
    muro_types = defaultdict(int)
    for e in muro_ents:
        muro_types[e.dxftype()] += 1
    print(f"  Entidades: {dict(muro_types)}")
    for i, e in enumerate(muro_ents[:20]):
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            length = math.sqrt((en.x - s.x)**2 + (en.y - s.y)**2)
            print(f"    LINE ({s.x:.2f},{s.y:.2f}) -> ({en.x:.2f},{en.y:.2f})  L={length:.2f}")

    # ── 7. RLE-LOSA lines ────────────────────────────────────────────
    print("\n  --- Losas (RLE-LOSA) ---")
    losa_ents = [e for e in msp if e.dxf.layer == "RLE-LOSA"]
    losa_types = defaultdict(int)
    for e in losa_ents:
        losa_types[e.dxftype()] += 1
    print(f"  Entidades: {dict(losa_types)}")
    for i, e in enumerate(losa_ents[:15]):
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            length = math.sqrt((en.x - s.x)**2 + (en.y - s.y)**2)
            print(f"    LINE ({s.x:.2f},{s.y:.2f}) -> ({en.x:.2f},{en.y:.2f})  L={length:.2f}")

    # ── 8. RLE-FUNDACION lines ───────────────────────────────────────
    print("\n  --- Fundaciones (RLE-FUNDACION) ---")
    fund_ents = [e for e in msp if e.dxf.layer == "RLE-FUNDACION"]
    fund_types = defaultdict(int)
    for e in fund_ents:
        fund_types[e.dxftype()] += 1
    print(f"  Entidades: {dict(fund_types)}")
    for i, e in enumerate(fund_ents[:20]):
        if e.dxftype() == "LINE":
            s, en = e.dxf.start, e.dxf.end
            length = math.sqrt((en.x - s.x)**2 + (en.y - s.y)**2)
            print(f"    LINE ({s.x:.2f},{s.y:.2f}) -> ({en.x:.2f},{en.y:.2f})  L={length:.2f}")

    print()

# ── Verificar integridad ──────────────────────────────────────────────
hashes_after = {f: sha256(DXF_DIR / f) for f in DXF_FILES}
print("=" * 90)
print("  VERIFICACION DE INTEGRIDAD")
print("=" * 90)
for f in DXF_FILES:
    ok = hashes_before[f] == hashes_after[f]
    print(f"  {f}: {'OK' if ok else 'FALLO'}")
