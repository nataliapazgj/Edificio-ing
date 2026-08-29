import pandas as pd

vertical = pd.read_csv("data/geometry/vertical_elements_LT2.csv")
sections = pd.read_csv("data/sections/sections_LT2.csv")
walls = pd.read_csv("data/geometry/walls_LT2.csv")

print("=== LT2 GEOMETRY CHECK ===")
print()

columns = vertical[vertical["type"] == "column"]

print(f"Columns registered : {len(columns)}")
print(f"Walls registered   : {len(walls)}")

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