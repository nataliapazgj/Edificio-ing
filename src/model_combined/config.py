"""Constantes y mapa de interfaz para el modelo combinado LT1 + LT2.

Toda la numeracion / offsets / transformacion confirmados se centralizan aqui
para reproducibilidad. Configurado tras el REVISION de LT2 (272 nodos):
los tags reales de los 12 nodos de interfaz del modelo LT2 actual quedan
fijados explicitamente.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # raiz del repo
GEOM = ROOT / "data" / "geometry"
PROC = ROOT / "data" / "processed"
RESULTS = ROOT / "results" / "combined"

# ---------------------------------------------------------------------------
# Transformacion geométrica confirmada (LT1 -> sistema combinado)
#   x_final = 31.25 + x_LT1
#   y_final = -y_LT1 - 0.25
#   z_final = z_LT1
# LT2 permanece en su sistema actual. Interfaz en x = 31.25.
# ---------------------------------------------------------------------------
X_SHIFT = 31.25
Y_SHIFT = -0.25     # y_final = -y + Y_SHIFT

def transform_lt1(x, y, z):
    """Aplica la transformación confirmada a una coordenada LT1."""
    return (X_SHIFT + x, -y + Y_SHIFT, z)


# ---------------------------------------------------------------------------
# Offsets de tags LT1 (LT2 conserva sus tags originales)
# ---------------------------------------------------------------------------
NODE_BASE_LT1 = 1_000_000
ELEM_BASE_LT1 = 2_000_000
TRANS_LT1 = 3001, 3002, 3003      # columnas, vigas X, vigas Y (reflexión Y)
TIME_SERIES_LT1 = 5000
PATTERN_LT1 = 6000

# ---------------------------------------------------------------------------
# Niveles comunes (z exacto) y master LT2 por nivel
# ---------------------------------------------------------------------------
COMMON_LEVELS = {
    "L2":   {"z": -0.05, "lt1_level": "P1", "master": 1002},
    "L3":   {"z": 3.91,  "lt1_level": "P2", "master": 1003},
    "L4":   {"z": 7.87,  "lt1_level": "P3", "master": 1004},
    "ROOF": {"z": 11.83, "lt1_level": "P4", "master": 1005},
}
LT2_LEVELS = ["L1", "L2", "L3", "L4", "ROOF"]   # diafragmas LT2 a preservar (incl. L1)
LT1_FRAME_LEVELS = ("P1", "P2", "P3", "P4")     # niveles estructurales LT1

# ---------------------------------------------------------------------------
# Nodos de interfaz LT2 en el modelo LT2 ACTUAL (272 nodos estructurales).
#   LT1tag -> LT2tag   (nodo COMPARTIDO; se reutiliza el tag LT2)
# El pareado físico coincide con el mapa confirmado (misma coordenada); solo
# cambia el número de tag LT2 respecto de la numeración antigua (224).
# ---------------------------------------------------------------------------
INTERFACE_MAP = {
    # P1 / L2  (z = -0.05)
    5: 114, 4: 117, 6: 118,
    # P2 / L3  (z = 3.91)
    21: 162, 20: 165, 22: 166,
    # P3 / L4  (z = 7.87)
    39: 210, 38: 213, 40: 214,
    # P4 / ROOF (z = 11.83)
    57: 268, 56: 271, 58: 272,
}

# ---------------------------------------------------------------------------
# Columnas LT1 de la interfaz que se DESCARTAN (existen en LT2 como
# P003 / P007 / P010, continuas a B1). Son elementos LT1 cuyos DOS extremos
# caen en nodos de interfaz. = 3 líneas x 3 tramos (L2-L4).
# ---------------------------------------------------------------------------
INTERFACE_COLUMN_LINES = {
    # (nodo bajo, nodo alto) en tags LT1 : pertenece a la línea compartida
    "yp0":   {(5, 21), (21, 39), (39, 57)},
    "yp8":   {(4, 20), (20, 38), (38, 56)},
    "yp16":  {(6, 22), (22, 40), (40, 58)},
}
INTERFACE_COLUMN_SPANS = set().union(
    *[(5, 21), (21, 39), (39, 57),
      (4, 20), (20, 38), (38, 56),
      (6, 22), (22, 40), (40, 58)])

# Nodos de interfaz (tags LT2 compartidos) agrupados por nivel estructural LT1.
# Estos nodos Son columnas CONTINUAS de LT2 (P003/P007/P010, B1..ROOF); por eso
# cuentan como SOPORTE para vigas/muros de LT1 que anclan en la interfaz, aunque
# las columnas LT1 duplicadas se DESCARTEN.
INTERFACE_LT2_PER_LEVEL = {
    "P1": {114, 117, 118},
    "P2": {162, 165, 166},
    "P3": {210, 213, 214},
    "P4": {268, 271, 272},
}
INTERFACE_LT2_TAGS = set().union(*INTERFACE_LT2_PER_LEVEL.values())


# Secciones LT1 (mismas que structure_params, para los elementos LT1).
COL = dict(A=0.49, IY=0.0200083, IZ=0.0200083, J=0.0338)
BEAM = dict(A=0.48, IY=0.0256, IZ=0.0144, J=0.0308)
WALL = dict(t=0.20, h=3.00)
E_KN_M2 = 25_000_000.0
NU = 0.20
G_KN_M2 = E_KN_M2 / (2.0 * (1.0 + NU))