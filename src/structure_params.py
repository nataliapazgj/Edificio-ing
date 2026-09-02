"""
Parametros estructurales UNICOS para el modelo OpenSeesPy 3D lineal.

FUENTE DE LA VERDAD (no inventar):
  - geometria: data/processed/building_3d_aligned.json (alta confianza)
  - secciones/materales: tomados de los planos (anotaciones MTEXT/TEXT) y del
    codigo de referencia `src/model.py` (benchmark ya validado).

Unidades SI: kN, m, s.
"""

# ---------------------------------------------------------------------------
# Materiales (referencia: src/model.py; planos => HORMIGON G35_10 fc'=35MPa)
# ---------------------------------------------------------------------------
E = 25_000_000.0     # Modulo elastico concreto [kN/m2]  (benchmark; G35 ~ E=25GPa)
NU = 0.20            # Coef. Poisson concreto
G = E / (2.0 * (1.0 + NU))   # [kN/m2]

GAMMA_CONCRETE = 25.0        # Peso especifico concreto [kN/m3]
GRAV = 9.81                  # Aceleracion de gravedad [m/s2]


# ---------------------------------------------------------------------------
# Secciones (documentadas en planos / benchmark)
# ---------------------------------------------------------------------------
# Columna  P.70x70  -> 0.70 x 0.70 m
COL_SECTION = {"name": "P.70x70", "b": 0.70, "h": 0.70}
COL_A  = 0.49            # m2
COL_IY = 0.0200083       # m4
COL_IZ = 0.0200083       # m4
COL_J  = 0.0338          # m4 (torsion)

# Viga  V.60/80 -> 0.60 x 0.80 m
BEAM_SECTION = {"name": "V.60/80", "b": 0.60, "h": 0.80}
BEAM_A  = 0.48           # m2
BEAM_IY = 0.0256         # m4
BEAM_IZ = 0.0144         # m4
BEAM_J  = 0.0308         # m4 (torsion)

# Muro  M.H.A. e=20/25/30 cm  (espesores documentados; base conservadora e=20)
# Utilizado para el "elemento lineal equivalente" de muro (seccion rectangular
# b=espesor, h=longitud equivalente nominal). TODO/INPUT_REQUIRED: la altura
# real de muro por tramo no esta en el JSON 2D; se toma H_muro_defecto por nivel.
WALL_THICKNESS = 0.20        # m (M.H.A. e=20; ver planos e=20/25/30)
WALL_H_DEFAULT = 3.00        # m (altura media piso; TODO/INPUT_REQUIRED revisar)


# ---------------------------------------------------------------------------
# Losa  (documentada: LOSA e=15; confirmada con benchmark src/model.py)
# ---------------------------------------------------------------------------
SLAB_THICKNESS = 0.15        # m            FUENTE: PLANOS/BENCHMARK (model.py:117)
SLAB_DEAD_LOAD = GAMMA_CONCRETE * SLAB_THICKNESS   # 3.75 kN/m2 (permanente)

# Terminaciones / acabados de piso: NO existe valor confirmado en planos ni en
# archivos previos. INPUT_REQUIRED. Se deja en 0.0 como escenario INCOMPLETO:
# q_G queda marcado PROVISIONAL hasta confirmar FINISHES_KN_M2.
SLAB_FINISHES_KN_M2 = 0.0        # INPUT_REQUIRED (sin confirmar -> 0 provisional)

# Carga gravitacional permanente de losa q_G [kN/m2]  (PROVISIONAL hasta
# confirmar FINISHES_KN_M2)
SLAB_QG_KN_M2 = SLAB_DEAD_LOAD + SLAB_FINISHES_KN_M2   # = 3.75 kN/m2 (PROVISIONAL)

# Carga viva: NO implementada en esta entrega.


# ---------------------------------------------------------------------------
# Solver / analisis
# ---------------------------------------------------------------------------
SYSTEM = "BandSPD"
NUMBERER = "RCM"
CONSTRAINTS = "Transformation"     # necesario para rigidDiaphragm (Plain ignora)
ALGORITHM = "Linear"
INTEGRATOR_STEP = 1.0
NUM_STEPS = 1

# Tolerancia de snap / emparejamiento [m] para armar la retícula nodal
NODE_SNAP_TOL = 0.50
COLUMN_MATCH_TOL = 0.50     # coincidencia (x,y) de pilares entre niveles


# ---------------------------------------------------------------------------
# Parametros REQUERIDOS no disponibles (no inventar) -> TODO/INPUT_REQUIRED
# ---------------------------------------------------------------------------
REQUIRED_MISSING = {
    "foundation_elevation": {
        "desc": "Cota del nivel Fundaciones (RLE-PROYECCION N.R.=-7.97..-8.42). NO confirmada.",
        "status": "INPUT_REQUIRED",
        "fallback": "Se usa P1 (z=-0.05) como base provisional documentada.",
    },
    "wall_proper_height": {
        "desc": "Altura real de muro por tramo (solo hay muros 2D por planta).",
        "status": "TODO",
        "fallback": f"Se parametriza WALL_H_DEFAULT={WALL_H_DEFAULT} m por nivel.",
    },
    "live_load": {
        "desc": "Carga viva de losas: NO se implementa en esta entrega.",
        "status": "N/A",
        "fallback": "Solo cargas permanentes (peso propio).",
    },
    "slab_finishes": {
        "desc": "Terminaciones/acabados de losa [kN/m2]: NO existe valor confirmado.",
        "status": "INPUT_REQUIRED",
        "fallback": "SLAB_FINISHES_KN_M2=0.0 -> q_G=3.75 kN/m2 PROVISIONAL.",
    },
    "P2-P3_alignment": {
        "desc": "Desfase Y entre familias de pilares P1/P2 y P3/P4 (hallazgo alineacion).",
        "status": "DOCUMENTED",
        "fallback": "Dos familias verticales independientes; cada una con base provisional documentada.",
    },
}