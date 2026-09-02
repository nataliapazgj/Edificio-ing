"""
Inspeccion programatica de archivos DXF — Etapa 2 Proyecto 1 MCOC.
Lee cuatro planos estructurales y genera un diagnostico reproducible.
No modifica los archivos originales.
"""

import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf

# ── Rutas ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DXF_DIR = ROOT / "data" / "dxf"
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

DXF_FILES = [
    "2017_67-100.dxf",
    "2017_67-101.dxf",
    "2017_67-102.dxf",
    "2017_67-103.dxf",
]

# Palabras clave para filtrar textos relevantes
LEVEL_KEYWORDS = [
    "planta", "nivel", "cota", "elevacion", "elev", "piso",
    "sotano", "subsuelo", "radier", "losa", "techo", "cubierta",
    "cielo", "fundacion", "zapata", "base",
]


# ── Utilidades ──────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_units(doc) -> str:
    """Lee $INSUNITS desde las variables de sistema del encabezado DXF."""
    UNITS_MAP = {
        0: "Unspecified",
        1: "Pulgadas (in)",
        2: "Pies (ft)",
        3: "Millas",
        4: "Milimetros (mm)",
        5: "Centimetros (cm)",
        6: "Metros (m)",
        7: "Kilometros (km)",
        8: "Microinches",
        9: "Mils",
        10: "Yardas",
        11: "Millas",
        12: "Kilometros (km)",
        14: "Pulgadas",
        15: "Pies",
    }
    try:
        val = doc.header.get("$INSUNITS", 0)
        return UNITS_MAP.get(val, f"Desconocido ($INSUNITS={val})")
    except Exception:
        return "No determinada"


def compute_bbox_manual(msp):
    """Calcula bounding box recorriendo entidades LINE, CIRCLE, ARC,
    LWPOLYLINE, POINT, INSERT. Mas lento pero fiable."""
    xmin = ymin = zmin = float("inf")
    xmax = ymax = zmax = float("-inf")
    count = 0

    def _update_point(x, y, z=0.0):
        nonlocal xmin, ymin, zmin, xmax, ymax, zmax, count
        if math.isfinite(x) and math.isfinite(y):
            xmin = min(xmin, x)
            ymin = min(ymin, y)
            zmin = min(zmin, z)
            xmax = max(xmax, x)
            ymax = max(ymax, y)
            zmax = max(zmax, z)
            count += 1

    for e in msp:
        dtype = e.dxftype()
        try:
            if dtype == "LINE":
                s = e.dxf.start
                en = e.dxf.end
                _update_point(s.x, s.y, s.z)
                _update_point(en.x, en.y, en.z)
            elif dtype == "CIRCLE":
                c = e.dxf.center
                r = e.dxf.radius
                _update_point(c.x - r, c.y - r, c.z)
                _update_point(c.x + r, c.y + r, c.z)
            elif dtype == "ARC":
                c = e.dxf.center
                r = e.dxf.radius
                _update_point(c.x - r, c.y - r, c.z)
                _update_point(c.x + r, c.y + r, c.z)
            elif dtype == "LWPOLYLINE":
                for pt in e.get_points(format="xy"):
                    _update_point(pt[0], pt[1])
            elif dtype == "POINT":
                loc = e.dxf.location
                _update_point(loc.x, loc.y, loc.z)
            elif dtype == "INSERT":
                ins = e.dxf.insert
                _update_point(ins.x, ins.y, ins.z)
            elif dtype == "SPLINE":
                for cp in e.control_points:
                    _update_point(cp[0], cp[1], cp[2] if len(cp) > 2 else 0)
            elif dtype == "ELLIPSE":
                c = e.dxf.center
                _update_point(c.x, c.y, c.z)
            elif dtype == "MTEXT" or dtype == "TEXT":
                ins = e.dxf.insert
                _update_point(ins.x, ins.y, ins.z)
        except Exception:
            pass

    if count > 0:
        return (xmin, ymin, zmin), (xmax, ymax, zmax)
    return None


def collect_entity_info(msp):
    """Recorre todas las entidades y retorna informacion por capa."""
    layer_entities = defaultdict(Counter)
    all_entity_types = Counter()
    blocks_used = Counter()
    texts = []
    inserts = []
    other = Counter()

    for e in msp:
        dtype = e.dxftype()
        layer = e.dxf.layer

        layer_entities[layer][dtype] += 1
        all_entity_types[dtype] += 1

        if dtype == "TEXT":
            txt = e.dxf.text if hasattr(e.dxf, "text") else ""
            pt = e.dxf.insert if hasattr(e.dxf, "insert") else (0, 0, 0)
            texts.append((layer, txt, pt))

        elif dtype == "MTEXT":
            txt = e.text if hasattr(e, "text") else ""
            pt = e.dxf.insert if hasattr(e.dxf, "insert") else (0, 0, 0)
            texts.append((layer, txt, pt))

        elif dtype == "INSERT":
            bname = e.dxf.name if hasattr(e.dxf, "name") else ""
            pt = e.dxf.insert if hasattr(e.dxf, "insert") else (0, 0, 0)
            inserts.append((layer, bname, pt))
            blocks_used[bname] += 1

        else:
            other[dtype] += 1

    return {
        "layer_entities": dict(layer_entities),
        "all_entity_types": dict(all_entity_types),
        "blocks_used": dict(blocks_used),
        "texts": texts,
        "inserts": inserts,
        "other": dict(other),
    }


# ── Palabras clave para detectar capas estructurales ───────────────────
STRUCTURAL_KEYWORDS = {
    "ejes": ["eje", "axis", "grid"],
    "vigas": ["viga", "beam", "vig"],
    "pilares": ["pilar", "columna", "col", "pillar", "cols"],
    "muros": ["muro", "wall", "mur"],
    "losas": ["losa", "slab", "forjado"],
    "fundaciones": ["fundacion", "cimentacion", "footing", "fund", "zapata"],
    "niveles": ["nivel", "level", "cota", "elev", "niv"],
}


def classify_layer(layer_name: str) -> list:
    name_lower = layer_name.lower()
    cats = []
    for cat, kws in STRUCTURAL_KEYWORDS.items():
        for kw in kws:
            if kw in name_lower:
                cats.append(cat)
                break
    return cats


# ── Procesamiento principal ────────────────────────────────────────────
report_lines = []


def pr(line=""):
    report_lines.append(line)


def process_one_dxf(filename: str):
    filepath = DXF_DIR / filename
    pr("=" * 80)
    pr(f"  ARCHIVO: {filename}")
    pr("=" * 80)

    h = sha256(filepath)
    pr(f"  SHA-256: {h}")
    pr(f"  Tamano:  {filepath.stat().st_size:,} bytes")
    pr()

    try:
        doc = ezdxf.readfile(str(filepath))
        pr("  Lectura DXF: OK")
    except Exception as exc:
        pr(f"  ERROR al leer DXF: {exc}")
        pr()
        return {"file": filename, "ok": False, "error": str(exc)}

    msp = doc.modelspace()

    # Unidades
    units = get_units(doc)
    pr(f"  Unidades ($INSUNITS): {units}")

    # Version DXF
    try:
        dxf_version = doc.dxfversion
        pr(f"  Version DXF: {dxf_version}")
    except Exception:
        pr("  Version DXF: No determinada")
    pr()

    # Extension geometrica (manual)
    bbox = compute_bbox_manual(msp)
    if bbox:
        extmin, extmax = bbox
        pr("  Extension geometrica (calculada manualmente):")
        pr(f"    Min: ({extmin[0]:.4f}, {extmin[1]:.4f}, {extmin[2]:.4f})")
        pr(f"    Max: ({extmax[0]:.4f}, {extmax[1]:.4f}, {extmax[2]:.4f})")
        dx = extmax[0] - extmin[0]
        dy = extmax[1] - extmin[1]
        dz = extmax[2] - extmin[2]
        pr(f"    Dimensiones: {dx:.4f} x {dy:.4f} x {dz:.4f}")
    else:
        pr("  Extension geometrica: No determinada")
    pr()

    # Entidades
    info = collect_entity_info(msp)
    total_ent = sum(info["all_entity_types"].values())
    pr(f"  Total entidades (modelspace): {total_ent}")
    pr()

    # Tipos de entidad
    pr("  Tipos de entidad (todas las capas):")
    pr(f"    {'Tipo':<20s}  {'Cantidad':>8s}")
    pr("    " + "-" * 32)
    for etype, cnt in sorted(info["all_entity_types"].items(), key=lambda x: -x[1]):
        pr(f"    {etype:<20s}  {cnt:>8d}")
    pr()

    # Bloques definidos
    block_names = []
    try:
        block_defs = list(doc.blocks)
        block_names = [b.name for b in block_defs if not b.name.startswith("*")]
        pr(f"  Bloques definidos (no anonimos): {len(block_names)}")
        if block_names:
            for bn in sorted(block_names):
                pr(f"    - {bn}")
    except Exception:
        pr("  Bloques definidos: No se pudo leer")
    pr()

    # Bloques referenciados (INSERT)
    if info["blocks_used"]:
        pr("  Bloques referenciados (INSERT):")
        for bn, cnt in sorted(info["blocks_used"].items(), key=lambda x: -x[1]):
            pr(f"    - {bn}: {cnt} inserciones")
    pr()

    # Capas y entidades por capa
    pr("  Capas y entidades por capa:")
    pr(f"    {'Capa':<30s}  {'Entidades':>10s}  Tipos")
    pr("    " + "-" * 80)
    for layer_name in sorted(info["layer_entities"].keys()):
        etype_dict = info["layer_entities"][layer_name]
        n_total = sum(etype_dict.values())
        types_str = ", ".join(
            f"{t}:{c}" for t, c in sorted(etype_dict.items(), key=lambda x: -x[1])
        )
        cats = classify_layer(layer_name)
        cat_str = f"  [{', '.join(cats)}]" if cats else ""
        pr(f"    {layer_name:<30s}  {n_total:>10d}  {types_str}{cat_str}")
    pr()

    # Clasificacion estructural de capas
    structural_layers = defaultdict(list)
    for layer_name in info["layer_entities"]:
        cats = classify_layer(layer_name)
        for cat in cats:
            structural_layers[cat].append(layer_name)

    pr("  Capas clasificadas como estructurales:")
    if structural_layers:
        for cat in sorted(structural_layers.keys()):
            for ln in structural_layers[cat]:
                pr(f"    [{cat}] {ln}")
    else:
        pr("    (No se detectaron capas con keywords estructurales)")
    pr()

    # ── Textos relevantes para niveles / plantas / cotas ───────────────
    n_texts = len(info["texts"])
    pr(f"  Textos totales detectados: {n_texts}")

    # Filtrar textos que contienen keywords de nivel/planta
    level_texts = []
    for layer, txt, pt in info["texts"]:
        txt_lower = txt.lower().strip()
        if any(kw in txt_lower for kw in LEVEL_KEYWORDS):
            level_texts.append((layer, txt, pt))

    pr(f"  Textos relevantes (plantas/niveles/cotas): {len(level_texts)}")
    if level_texts:
        pr(f"    {'Capa':<25s}  {'Texto':<60s}  Posicion")
        pr("    " + "-" * 110)
        for layer, txt, pt in level_texts:
            txt_show = txt[:58] if txt else ""
            pt_str = f"({pt[0]:.2f}, {pt[1]:.2f})" if pt else "N/A"
            pr(f"    {layer:<25s}  {txt_show:<60s}  {pt_str}")
    pr()

    # Inserciones (INSERT)
    n_inserts = len(info["inserts"])
    if n_inserts > 0:
        pr(f"  Inserciones (INSERT) detectadas: {n_inserts}")
        pr(f"    {'Capa':<25s}  {'Bloque':<40s}  Posicion")
        pr("    " + "-" * 90)
        for layer, bname, pt in info["inserts"][:60]:
            pt_str = f"({pt[0]:.2f}, {pt[1]:.2f})" if pt else "N/A"
            pr(f"    {layer:<25s}  {bname:<40s}  {pt_str}")
        if n_inserts > 60:
            pr(f"    ... y {n_inserts - 60} inserciones mas")
        pr()

    pr()

    return {
        "file": filename,
        "ok": True,
        "sha256": h,
        "units": units,
        "bbox": bbox,
        "total_entities": total_ent,
        "entity_types": info["all_entity_types"],
        "layer_entities": info["layer_entities"],
        "blocks_defined": block_names,
        "blocks_used": info["blocks_used"],
        "n_texts": n_texts,
        "n_inserts": n_inserts,
        "structural_layers": dict(structural_layers),
        "level_texts": level_texts,
    }


# ── Ejecucion ──────────────────────────────────────────────────────────
pr("REPORTE DE INSPECCION DXF — ETAPA 2")
pr("Proyecto 1 MCOC — Metodos Computacionales")
pr()
pr("Este reporte es generado automaticamente por src/inspect_dxf.py")
pr("No se modificaron los archivos DXF originales.")
pr()

hashes_before = {}
for fname in DXF_FILES:
    hashes_before[fname] = sha256(DXF_DIR / fname)

results = []
for fname in DXF_FILES:
    r = process_one_dxf(fname)
    results.append(r)

# ── Verificaciones ─────────────────────────────────────────────────────
pr()
pr("=" * 80)
pr("  VERIFICACIONES")
pr("=" * 80)
pr()

ok_files = [r["file"] for r in results if r.get("ok")]
fail_files = [r["file"] for r in results if not r.get("ok")]
pr(f"  V1 — Archivos legibles: {len(ok_files)}/{len(DXF_FILES)}")
if fail_files:
    pr(f"    FALLO en: {', '.join(fail_files)}")
    for r in results:
        if not r.get("ok"):
            pr(f"      {r['file']}: {r.get('error', 'desconocido')}")
else:
    pr("    OK — Todos los archivos se leyeron correctamente")
pr()

hashes_after = {}
for fname in DXF_FILES:
    hashes_after[fname] = sha256(DXF_DIR / fname)

hash_ok = all(hashes_before[f] == hashes_after[f] for f in DXF_FILES)
pr("  V2 — Integridad de archivos originales:")
if hash_ok:
    pr("    OK — Los hashes SHA-256 no cambiaron")
else:
    pr("    FALLO — Algunos archivos fueron modificados:")
    for f in DXF_FILES:
        if hashes_before[f] != hashes_after[f]:
            pr(f"      {f}: {hashes_before[f][:16]}... -> {hashes_after[f][:16]}...")
pr()

pr(f"  V3 — Reporte completo: {len(ok_files)}/{len(DXF_FILES)} archivos")
if len(ok_files) == len(DXF_FILES):
    pr("    OK — El reporte contiene resultados para los 4 archivos")
else:
    pr("    FALLO — Faltan resultados para algunos archivos")
pr()

# ── Tabla resumen ──────────────────────────────────────────────────────
pr()
pr("=" * 80)
pr("  TABLA RESUMEN")
pr("=" * 80)
pr()
pr(
    f"  {'Archivo':<22s}  {'Unidades':<18s}  {'Entidades':>10s}"
    f"  {'Capas':>6s}  {'Textos':>7s}  {'INSERTs':>8s}"
)
pr("  " + "-" * 80)
for r in results:
    if r.get("ok"):
        n_layers = len(r["layer_entities"])
        pr(
            f"  {r['file']:<22s}  {r['units']:<18s}  {r['total_entities']:>10d}"
            f"  {n_layers:>6d}  {r['n_texts']:>7d}  {r['n_inserts']:>8d}"
        )
    else:
        pr(f"  {r['file']:<22s}  ERROR: {r.get('error', '?')}")
pr()

# ── Guardar reporte ────────────────────────────────────────────────────
report_path = RESULTS_DIR / "dxf_inspection_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"Reporte guardado en: {report_path}")
print(f"Archivos verificados: {len(ok_files)}/{len(DXF_FILES)}")
print(f"Hashes intactos: {hash_ok}")
