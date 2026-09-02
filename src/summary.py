"""Resumen de resultados para verificacion manual."""
import csv

labels = ['N_i','Vy_i','Vz_i','T_i','My_i','Mz_i',
          'N_j','Vy_j','Vz_j','T_j','My_j','Mz_j']

print("=" * 72)
print('  ORDEN DE COMPONENTES - eleResponse(tag, "forces") en elasticBeamColumn 3D')
print("=" * 72)
print()
print("  Extremo i (nodo i):  [0] N_i   [1] Vy_i   [2] Vz_i")
print("                       [3] T_i   [4] My_i   [5] Mz_i")
print("  Extremo j (nodo j):  [6] N_j   [7] Vy_j   [8] Vz_j")
print("                       [9] T_j  [10] My_j   [11] Mz_j")
print()
print("  N  = fuerza axial        Vy = cortante local y")
print("  Vz = cortante local z    T  = torsion")
print("  My = momento flector eje y-local   Mz = momento flector eje z-local")
print()

# 1. Desplazamientos
print("=" * 72)
print("  1. DESPLAZAMIENTOS — NODOS 5-10")
print("=" * 72)
print(f"  {'Nodo':>4s}  {'Ux [m]':>14s}  {'Uy [m]':>14s}  {'Uz [m]':>14s}")
print("-" * 72)

with open("results/displacements.csv") as f:
    for row in csv.DictReader(f):
        tag = int(row["nodeTag"])
        ux = float(row["Ux_m"])
        uy = float(row["Uy_m"])
        uz = float(row["Uz_m"])
        print(f"  {tag:>4d}  {ux:>+14.8e}  {uy:>+14.8e}  {uz:>+14.8e}")

print()

# 2. Columnas
print("=" * 72)
print("  2. COLUMNAS E1-E4 — FUERZAS LOCALES COMPLETAS")
print("=" * 72)

with open("results/element_forces.csv") as f:
    cols = [r for r in csv.DictReader(f) if r["type"] == "Columna"]

for row in cols:
    tag = int(row["elementTag"])
    ni, nj = int(row["ni"]), int(row["nj"])
    vals = [float(row[l]) for l in labels]
    print(f"  E{tag}  ({ni}->{nj})")
    print(f"    Ext i: N={vals[0]:>+10.4f}  Vy={vals[1]:>+10.4f}  Vz={vals[2]:>+10.4f}")
    print(f"           T={vals[3]:>+10.4f}  My={vals[4]:>+10.4f}  Mz={vals[5]:>+10.4f}")
    print(f"    Ext j: N={vals[6]:>+10.4f}  Vy={vals[7]:>+10.4f}  Vz={vals[8]:>+10.4f}")
    print(f"           T={vals[9]:>+10.4f}  My={vals[10]:>+10.4f}  Mz={vals[11]:>+10.4f}")
    print(f"    >>> Fuerza axial: N_i = {vals[0]:+.4f} kN,  N_j = {vals[6]:+.4f} kN")
    print()

# 3. Vigas
print("=" * 72)
print("  3. VIGAS E5-E11 — FUERZAS LOCALES COMPLETAS")
print("=" * 72)

with open("results/element_forces.csv") as f:
    beams = [r for r in csv.DictReader(f) if r["type"] != "Columna"]

for row in beams:
    tag = int(row["elementTag"])
    ni, nj = int(row["ni"]), int(row["nj"])
    etype = row["type"]
    vals = [float(row[l]) for l in labels]
    print(f"  E{tag}  ({ni}->{nj})  [{etype}]")
    print(f"    Ext i: N={vals[0]:>+10.4f}  Vy={vals[1]:>+10.4f}  Vz={vals[2]:>+10.4f}")
    print(f"           T={vals[3]:>+10.4f}  My={vals[4]:>+10.4f}  Mz={vals[5]:>+10.4f}")
    print(f"    Ext j: N={vals[6]:>+10.4f}  Vy={vals[7]:>+10.4f}  Vz={vals[8]:>+10.4f}")
    print(f"           T={vals[9]:>+10.4f}  My={vals[10]:>+10.4f}  Mz={vals[11]:>+10.4f}")
    print(f"    >>> My_i={vals[4]:+.4f}  My_j={vals[10]:+.4f}  |  Mz_i={vals[5]:+.4f}  Mz_j={vals[11]:+.4f}")
    print()

print("=" * 72)
print("  FIN DEL RESUMEN")
print("=" * 72)
