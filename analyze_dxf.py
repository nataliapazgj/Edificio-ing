import ezdxf
from collections import defaultdict

DXF_PATH = r"data\dxf\2017_67-103.dxf"
print(f"Loading {DXF_PATH} ...")
doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

TARGET_LAYERS = ["RLE-VIGA", "RLE-PILAR", "RLE-MURO", "RLE-EJES", "RLE-EJE"]
TEXT_LAYERS = ["RLE-EJE", "RLE-EJES", "RLE-TEXTO-1", "RLA-TEXTOS1"]

# Collect all entities by layer
by_layer = defaultdict(list)
for e in msp:
    by_layer[e.dxf.layer].append(e)

# Also check for TEXT/MTEXT in text layers from ALL layers
all_text_entities = []
for e in msp:
    if e.dxftype() in ("TEXT", "MTEXT") and e.dxf.layer in TEXT_LAYERS:
        all_text_entities.append(e)


def get_geometry_info(entity):
    """Return a dict with geometry info depending on entity type."""
    info = {}
    t = entity.dxftype()
    d = entity.dxfattribs()
    info["type"] = t
    info["layer"] = d.get("layer", "?")
    info["attrib_keys"] = sorted(d.keys())

    if t == "LINE":
        info["start"] = entity.dxf.start
        info["end"] = entity.dxf.end
    elif t == "LWPOLYLINE":
        pts = list(entity.get_points(format="xy"))
        info["vertices"] = pts
        info["n_vertices"] = len(pts)
        info["closed"] = entity.closed
    elif t == "POLYLINE":
        verts = list(entity.vertices)
        info["vertices"] = [(v.dxf.location.x, v.dxf.location.y) for v in verts]
        info["n_vertices"] = len(info["vertices"])
        info["closed"] = entity.is_closed
    elif t == "ARC":
        info["center"] = entity.dxf.center
        info["radius"] = entity.dxf.radius
        info["start_angle"] = entity.dxf.start_angle
        info["end_angle"] = entity.dxf.end_angle
    elif t == "CIRCLE":
        info["center"] = entity.dxf.center
        info["radius"] = entity.dxf.radius
    elif t == "ELLIPSE":
        info["center"] = entity.dxf.center
        info["major_axis"] = entity.dxf.major_axis
        info["ratio"] = entity.dxf.ratio
    elif t == "POINT":
        info["location"] = entity.dxf.location
    elif t == "SPLINE":
        info["control_points"] = len(entity.control_points)
        info["knots"] = len(entity.knots)
    elif t in ("TEXT", "MTEXT"):
        if t == "TEXT":
            info["text"] = entity.dxf.text
            info["height"] = entity.dxf.height
            info["insert"] = entity.dxf.insert
        else:
            info["text"] = entity.text
            info["height"] = d.get("height", d.get("char_height", "?"))
            info["insert"] = entity.dxf.insert
    elif t == "INSERT":
        info["name"] = entity.dxf.name
        info["insert"] = entity.dxf.insert
    elif t == "HATCH":
        info["pattern"] = d.get("pattern_name", "?")
    elif t == "SOLID":
        info["points"] = [entity.dxf.get(f"v{i}") for i in range(1, 5) if f"v{i}" in entity.dxfattribs()]
    elif t == "3DFACE":
        info["points"] = [entity.dxf.get(f"v{i}") for i in range(1, 5) if f"v{i}" in entity.dxfattribs()]
    elif t == "DIMENSION":
        info["dimtype"] = d.get("dimtype", "?")
    elif t == "ATTRIB":
        info["tag"] = d.get("tag", "?")
        info["text"] = d.get("text", "?")
    elif t == "LEADER":
        pass
    elif t == "RAY":
        info["start"] = entity.dxf.start
        info["direction"] = entity.dxf.direction
    elif t == "XLINE":
        info["start"] = entity.dxf.start
        info["direction"] = entity.dxf.direction
    return info


def print_layer_section(layer_name, entities, show_n=5):
    print(f"\n{'='*80}")
    print(f"  LAYER: {layer_name}  |  Total entities: {len(entities)}")
    print(f"{'='*80}")

    if not entities:
        print("  (no entities found)")
        return

    # Count by type
    type_counts = defaultdict(int)
    for e in entities:
        type_counts[e.dxftype()] += 1

    print(f"\n  Entity type counts:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:25s} : {c}")

    # All attrib keys per type
    print(f"\n  DXF attribute keys per type:")
    type_keys = defaultdict(set)
    for e in entities:
        type_keys[e.dxftype()].update(e.dxfattribs().keys())
    for t in sorted(type_keys.keys()):
        print(f"    {t}:")
        for k in sorted(type_keys[t]):
            print(f"      - {k}")

    # Show first N entities
    n = min(show_n, len(entities))
    print(f"\n  First {n} entities with geometry:")
    for i, e in enumerate(entities[:n]):
        info = get_geometry_info(e)
        print(f"  --- Entity #{i+1} ---")
        for k, v in info.items():
            print(f"    {k}: {v}")


# ===== 1. RLE-VIGA =====
print_layer_section("RLE-VIGA", by_layer.get("RLE-VIGA", []), show_n=5)

# ===== 2. RLE-PILAR =====
print_layer_section("RLE-PILAR", by_layer.get("RLE-PILAR", []), show_n=5)

# ===== 3. RLE-MURO =====
print_layer_section("RLE-MURO", by_layer.get("RLE-MURO", []), show_n=5)

# ===== 4. RLE-EJES =====
print_layer_section("RLE-EJES", by_layer.get("RLE-EJES", []), show_n=10)

# ===== 5. RLE-EJE =====
print_layer_section("RLE-EJE", by_layer.get("RLE-EJE", []), show_n=5)

# ===== 6. TEXT/MTEXT on text layers =====
print(f"\n{'='*80}")
print(f"  TEXT/MTEXT on layers: {TEXT_LAYERS}")
print(f"  Total found: {len(all_text_entities)}")
print(f"{'='*80}")

for i, e in enumerate(all_text_entities[:20]):
    t = e.dxftype()
    if t == "TEXT":
        content = e.dxf.text
        height = e.dxf.height
        insert = e.dxf.insert
    else:
        content = e.text
        height = e.dxf.char_height if "char_height" in e.dxfattribs() else "?"
        insert = e.dxf.insert
    layer = e.dxf.layer
    print(f"  #{i+1:2d}  [{t:6s}]  layer={layer:20s}  height={height}  insert=({insert.x:.2f}, {insert.y:.2f})  text={content!r}")

print("\n\nDONE.")
