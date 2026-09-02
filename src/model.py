"""
Benchmark estructural 3D — modelo + analisis + resultados.
Unidades: kN, m
"""

import os
import csv
import openseespy.opensees as ops

# ── Inicializar modelo ──────────────────────────────────────────────────
ops.wipe()
ops.model("basic", "-ndm", 3, "-ndf", 6)

# ── Nodos de base (z = 0) ──────────────────────────────────────────────
ops.node(1,  0.00, 0.00, 0.00)
ops.node(2, 10.00, 0.00, 0.00)
ops.node(3,  0.00, 7.25, 0.00)
ops.node(4, 10.00, 7.25, 0.00)

# ── Nodos del nivel superior (z = 3.96) ────────────────────────────────
ops.node(5,  0.00, 0.00, 3.96)
ops.node(6,  5.00, 0.00, 3.96)
ops.node(7, 10.00, 0.00, 3.96)
ops.node(8,  0.00, 7.25, 3.96)
ops.node(9,  5.00, 7.25, 3.96)
ops.node(10,10.00, 7.25, 3.96)

# ── Apoyos: empotramiento nodos 1-4 (6 DOF restringidos) ──────────────
FIX = [1, 1, 1, 1, 1, 1]   # Ux Uy Uz Rx Ry Rz

for tag in range(1, 5):
    ops.fix(tag, *FIX)

# ── Material elástico ──────────────────────────────────────────────────
E  = 25_000_000.0       # kN/m²
nu = 0.20
G  = E / (2.0 * (1.0 + nu))

# ── Secciones ──────────────────────────────────────────────────────────
# Columna 0.70 x 0.70 m (cuadrada)
A_col  = 0.49           # m²
Iy_col = 0.0200083      # m⁴
Iz_col = 0.0200083      # m⁴
J_col  = 0.0338         # m⁴

# Viga 0.60 x 0.80 m (b x h)
A_beam  = 0.48          # m²
Iy_beam = 0.0256        # m⁴
Iz_beam = 0.0144        # m⁴
J_beam  = 0.0308        # m⁴

# ── Transformaciones geométricas ───────────────────────────────────────
# vecxz orienta el eje z-local; el eje y-local se deriva automáticamente.
ops.geomTransf("Linear", 1, 0, 0, 1)    # vigas paralelas a X global; vecxz = (0,0,1)
ops.geomTransf("Linear", 2, 0, 0, 1)    # vigas paralelas a Y global; vecxz = (0,0,1)
ops.geomTransf("Linear", 3, 1, 0, 0)    # columnas verticales;        vecxz = (1,0,0)

# ── Elementos elasticBeamColumn 3D ────────────────────────────────────
#
#  Columnas verticales ( transfTag = 3 )
ops.element("elasticBeamColumn", 1,  1,  5, A_col,  E, G, J_col, Iy_col, Iz_col, 3)
ops.element("elasticBeamColumn", 2,  2,  7, A_col,  E, G, J_col, Iy_col, Iz_col, 3)
ops.element("elasticBeamColumn", 3,  3,  8, A_col,  E, G, J_col, Iy_col, Iz_col, 3)
ops.element("elasticBeamColumn", 4,  4, 10, A_col,  E, G, J_col, Iy_col, Iz_col, 3)

#  Vigas paralelas a X global ( transfTag = 1 )
ops.element("elasticBeamColumn", 5,  5,  6, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 1)
ops.element("elasticBeamColumn", 6,  6,  7, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 1)
ops.element("elasticBeamColumn", 7,  8,  9, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 1)
ops.element("elasticBeamColumn", 8,  9, 10, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 1)

#  Vigas paralelas a Y global ( transfTag = 2 )
ops.element("elasticBeamColumn", 9,  5,  8, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 2)
ops.element("elasticBeamColumn", 10, 6,  9, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 2)
ops.element("elasticBeamColumn", 11, 7, 10, A_beam, E, G, J_beam, Iy_beam, Iz_beam, 2)

# ── Información de verificación ─────────────────────────────────────────
all_nodes = ops.getNodeTags()

print("=" * 65)
print("  MODELO 3D — NODOS")
print("=" * 65)
for tag in all_nodes:
    x, y, z = ops.nodeCoord(tag)
    is_fixed = "EMPOTRADO" if tag in range(1, 5) else "libre"
    print(f"  Nodo {tag:>2d}  ({x:7.2f}, {y:7.2f}, {z:7.2f})  — {is_fixed}")
print(f"  Total nodos: {len(all_nodes)}")

all_elems = ops.getEleTags()
print("-" * 65)
print("  ELEMENTOS")
print("-" * 65)
for tag in all_elems:
    ni, nj = ops.eleNodes(tag)
    if tag <= 4:
        etype = "Columna"
    elif tag <= 8:
        etype = "Viga X"
    else:
        etype = "Viga Y"
    print(f"  Elem {tag:>2d}  Nodo {ni:>2d} -> {nj:<2d}  ({etype})")
print(f"  Total elementos: {len(all_elems)}")

print("-" * 65)
print(f"  E  = {E:.0f} kN/m2")
print(f"  G  = {G:.0f} kN/m2")
print("=" * 65)

# ── Carga gravitacional: peso propio de losa ───────────────────────────
#
# Se distribuye la carga de losa mediante areas tributarias a 45 grados.
# Cada carga lineal se aplica como eleLoad en ejes LOCALES.
# Con vecxz = (0,0,1) el eje z-local apunta hacia arriba (Z global),
# por lo que una carga vertical hacia abajo es -w en z-local.

gamma_conc = 25.0          # kN/m3
t_losa     = 0.15          # m
q_losa     = gamma_conc * t_losa   # 3.75 kN/m2
A_total    = 10.0 * 7.25          # 72.50 m2

# Areas tributarias y cargas lineales por elemento (hacia abajo => negativo)
#   eleTag: (longitud_m, Area_trib_m2, w_kN_m)
tributary = {
    5:  (5.00,   6.250, -4.6875),       # viga X, nodo 5-6
    6:  (5.00,   6.250, -4.6875),       # viga X, nodo 6-7
    7:  (5.00,   6.250, -4.6875),       # viga X, nodo 8-9
    8:  (5.00,   6.250, -4.6875),       # viga X, nodo 9-10
    9:  (7.25,  11.875, -6.1422413793), # viga Y, nodo 5-8
    10: (7.25,  23.750, -12.2844827586),# viga Y, nodo 6-9  (interior)
    11: (7.25,  11.875, -6.1422413793), # viga Y, nodo 7-10
}

# Definir pattern y timeSeries
ops.timeSeries("Linear", 1)
ops.pattern("Plain", 1, 1)

# Aplicar eleLoad (wy=0, wz=w) en ejes locales
for etag, (L, A_trib, w) in tributary.items():
    ops.eleLoad("-ele", etag, "-type", "-beamUniform", 0.0, w)

# ── Verificacion de cargas ────────────────────────────────────────────
print()
print("=" * 70)
print("  VERIFICACION — CARGA GRAVITACIONAL (PESO PROPIO DE LOSA)")
print("=" * 70)
print(f"  q_losa = {gamma_conc} x {t_losa} = {q_losa:.2f} kN/m2")
print(f"  A total losa = {A_total:.2f} m2")
print(f"  Carga total teorica = q x A = {q_losa * A_total:.3f} kN")
print("-" * 70)
print(f"  {'Elem':>4s}  {'Ni-Nj':>7s}  {'L [m]':>7s}  {'A_trib':>10s}  {'w [kN/m]':>12s}  {'w*L [kN]':>10s}")
print("-" * 70)

total_transferida = 0.0
for etag in sorted(tributary.keys()):
    L, A_trib, w = tributary[etag]
    ni, nj = ops.eleNodes(etag)
    force = abs(w) * L
    total_transferida += force
    print(f"  {etag:>4d}  {ni:>2d}-{nj:<2d}  {L:>7.2f}  {A_trib:>10.3f}  {abs(w):>12.6f}  {force:>10.3f}")

carga_teorica = q_losa * A_total
diferencia = total_transferida - carga_teorica

print("-" * 70)
print(f"  Carga total transferida (suma w*L) = {total_transferida:.6f} kN")
print(f"  Carga total teorica    (q x A)      = {carga_teorica:.6f} kN")
print(f"  Diferencia                          = {diferencia:.10f} kN")
print("=" * 70)
if abs(diferencia) < 1.0e-6:
    print("  OK: la diferencia es practicamente cero.")
else:
    print("  ALERTA: revisar distribucion tributaria.")
print("=" * 70)

# ── Configuracion y ejecucion del analisis ─────────────────────────────
ops.system("BandSPD")
ops.numberer("RCM")
ops.constraints("Plain")
ops.integrator("LoadControl", 1.0)
ops.algorithm("Linear")
ops.analysis("Static")
ops.record()

ok = ops.analyze(1)
ops.reactions()

print()
print("=" * 70)
print("  RESULTADO DEL ANALISIS")
print("=" * 70)
print(f"  ops.analyze(1) = {ok}  (0 = exitoso)")
print("=" * 70)

# ── Reacciones en nodos empotrados ─────────────────────────────────────
# reaction(nodeTag, dof)  dof: 1=Ux 2=Uy 3=Uz 4=Rx 5=Ry 6=Rz
support_nodes = [1, 2, 3, 4]
reaction_dofs = {"Ux": 1, "Uy": 2, "Uz": 3, "Rx": 4, "Ry": 5, "Rz": 6}

print()
print("  REACCIONES EN APOYOS")
print("-" * 70)
print(f"  {'Nodo':>4s}  {'Rz [kN]':>12s}  {'Rx [kN]':>12s}  {'Ry [kN]':>12s}")
print("-" * 70)

reactions_data = []
sum_Rz = 0.0
for tag in support_nodes:
    Rx = ops.nodeReaction(tag, 1)
    Ry = ops.nodeReaction(tag, 2)
    Rz = ops.nodeReaction(tag, 3)
    sum_Rz += Rz
    reactions_data.append([tag, Rx, Ry, Rz])
    print(f"  {tag:>4d}  {Rz:>12.4f}  {Rx:>12.4f}  {Ry:>12.4f}")

print("-" * 70)
print(f"  Suma Rz = {sum_Rz:.6f} kN")
print(f"  Carga aplicada = {carga_teorica:.6f} kN")
print(f"  Diferencia = {sum_Rz - carga_teorica:.10f} kN")
if abs(sum_Rz - carga_teorica) < 1.0e-3:
    print("  OK: equilibrio vertical verificado.")
else:
    print("  ALERTA: revisar equilibrio.")
print("=" * 70)

# ── Desplazamientos nodos superiores ───────────────────────────────────
upper_nodes = [5, 6, 7, 8, 9, 10]
disp_labels = ["Ux", "Uy", "Uz", "Rx", "Ry", "Rz"]

print()
print("  DESPLAZAMIENTOS — NODOS SUPERIORES")
print("-" * 78)
header = f"  {'Nodo':>4s}"
for lbl in disp_labels:
    header += f"  {lbl:>12s}"
print(header)
print("-" * 78)

disp_data = []
max_abs_Uz = 0.0
max_Uz_node = 0
for tag in upper_nodes:
    disp = [ops.nodeDisp(tag, i) for i in range(1, 7)]
    disp_data.append([tag] + disp)
    if abs(disp[2]) > max_abs_Uz:
        max_abs_Uz = abs(disp[2])
        max_Uz_node = tag
    vals = "".join(f"  {v:>12.8f}" for v in disp)
    print(f"  {tag:>4d}{vals}")

print("-" * 78)
print(f"  Desplazamiento vertical maximo: Uz = {ops.nodeDisp(max_Uz_node, 3):.8f} m")
print(f"  En nodo {max_Uz_node}")
print("=" * 70)

# ── Fuerzas elementales (ejes locales) ─────────────────────────────────
# ops.eleResponse(tag, "localForce") devuelve fuerzas en ejes LOCALES:
# [N_i, Vy_i, Vz_i, T_i, My_i, Mz_i, N_j, Vy_j, Vz_j, T_j, My_j, Mz_j]
#
# NOTA: ops.eleResponse(tag, "forces") y ops.eleForce(tag) devuelven
# fuerzas en ejes GLOBALES, no locales. Usar "localForce" explicitamente.
force_labels = [
    "Ni", "Vyi", "Vzi", "Ti", "Myi", "Mzi",
    "Nj", "Vyj", "Vzj", "Tj", "Myj", "Mzj",
]

print()
print("  FUERZAS LOCALES — 11 ELEMENTOS")
print("-" * 120)
header2 = f"  {'Elem':>4s}  {'Ni':>3s}-{'Nj':<3s}  {'Tipo':>8s}"
for lbl in force_labels:
    header2 += f"  {lbl:>10s}"
print(header2)
print("-" * 120)

elem_forces_data = []
for tag in all_elems:
    ni, nj = ops.eleNodes(tag)
    forces = list(ops.eleResponse(tag, "localForce"))
    if tag <= 4:
        etype = "Columna"
    elif tag <= 8:
        etype = "Viga X"
    else:
        etype = "Viga Y"
    row = [tag] + forces
    elem_forces_data.append(row)
    vals = "".join(f"  {v:>10.4f}" for v in forces)
    print(f"  {tag:>4d}  {ni:>3d}-{nj:<3d}  {etype:>8s}{vals}")

print("-" * 120)
print("=" * 70)

# ── Guardar resultados en CSV ──────────────────────────────────────────
os.makedirs("results", exist_ok=True)

with open("results/reactions.csv", "w", newline="") as f:
    w_csv = csv.writer(f)
    w_csv.writerow(["nodeTag", "Rx_kN", "Ry_kN", "Rz_kN"])
    for row in reactions_data:
        w_csv.writerow(row)
print("  Guardado: results/reactions.csv")

with open("results/displacements.csv", "w", newline="") as f:
    w_csv = csv.writer(f)
    w_csv.writerow(["nodeTag", "Ux_m", "Uy_m", "Uz_m", "Rx_rad", "Ry_rad", "Rz_rad"])
    for row in disp_data:
        w_csv.writerow(row)
print("  Guardado: results/displacements.csv")

with open("results/element_forces.csv", "w", newline="") as f:
    w_csv = csv.writer(f)
    w_csv.writerow(["elementTag", "Ni", "Vyi", "Vzi", "Ti", "Myi", "Mzi",
                     "Nj", "Vyj", "Vzj", "Tj", "Myj", "Mzj"])
    for row in elem_forces_data:
        w_csv.writerow(row)
print("  Guardado: results/element_forces.csv")

print("=" * 70)
print("  FIN DEL ANALISIS GRAVITACIONAL")
print("=" * 70)
