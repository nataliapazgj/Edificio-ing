import pandas as pd

levels = pd.read_csv("data/geometry/levels.csv")
grid_x = pd.read_csv("data/geometry/grid_x.csv")
grid_y = pd.read_csv("data/geometry/grid_y.csv")
vertical = pd.read_csv("data/geometry/vertical_elements_LT2.csv")
sections = pd.read_csv("data/sections/sections_LT2.csv")
walls = pd.read_csv("data/geometry/walls_LT2.csv")

print("=== LT2 GEOMETRY CHECK ===")
print()

columns = vertical[vertical["type"] == "column"]

print(f"Columns registered : {len(columns)}")
print(f"Walls registered   : {len(walls)}")

print()
print("Referenced axes/levels check:")

x_axis = set(grid_x["axis_id"].astype(str))
y_axis = set(grid_y["axis_id"].astype(str))
z_level = set(levels["name"].astype(str))

missing_refs = []
for _, e in vertical.iterrows():
    eid = e["element_id"]
    for ref, tag, valid in (
        (str(e["axis_x"]), "axis X", x_axis),
        (str(e["axis_y"]), "axis Y", y_axis),
        (str(e["from_level"]), "from_level", z_level),
        (str(e["to_level"]), "to_level", z_level),
    ):
        if ref not in valid:
            missing_refs.append(f"{eid}: undefined {tag} '{ref}'")

for _, w in walls.iterrows():
    wid = w["wall_id"]
    for ref, tag in (
        (str(w["from_level"]), "from_level"),
        (str(w["to_level"]), "to_level"),
    ):
        if ref not in z_level:
            missing_refs.append(f"{wid}: undefined {tag} '{ref}'")

if missing_refs:
    print("ERROR - References to undefined axes or levels:")
    for msg in missing_refs:
        print(f"  - {msg}")
else:
    print("  All axes and levels referenced are defined.")

print()
print("Columns by section:")
print(columns["section"].value_counts())

print()

defined_sections = set(sections["section_id"])
used_sections = set(columns["section"])

missing_sections = used_sections - defined_sections

if missing_sections:
    print("ERROR - Undefined sections:")
    for section in missing_sections:
        print(f"  - {section}")
else:
    print("All referenced column sections are defined.")

print()

if len(walls) == 0:
    print("INFO - Wall digitization pending.")
else:
    invalid_walls = walls[
        (walls["x1_m"] == walls["x2_m"]) &
        (walls["y1_m"] == walls["y2_m"])
    ]

    if len(invalid_walls) > 0:
        print("ERROR - Zero-length walls found:")
        print(invalid_walls["wall_id"].tolist())
    else:
        print("No zero-length walls.")

print()
print("=== END CHECK ===")