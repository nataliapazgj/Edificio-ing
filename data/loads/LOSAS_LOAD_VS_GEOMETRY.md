# Losas LT2 — definiciones de carga y estado de geometría

**Fecha:** 2026-09 (bloque de implementación de cargas gravitacionales q_G).

## Separación estructural

Se separa explícitamente:

- **`slab_load_definition`** → `data/loads/slabs_LT2.csv`: parámetros de carga de cada losa
  (espesor, densidad, PP, terminaciones, q_G). Sin polígonos todavía.
- **`slab_geometry`** → PENDIENTE de un próximo bloque: contorno, paños, huecos y zonas sin
  losa por nivel, a partir de la lectura manual de los símbolos circulares de los planos
  (101 / 201 para L1-L4, 102 / 202 para ROOF).

La geometría se incorporará en el siguiente bloque **sin rehacer** la definición de cargas.

## Fuentes de carga (plano 700)

- Plantas **cielo 1° subterráneo a cielo piso 3°**:
  - `PP_LOSA = e(m) × 2500 kg/m³`
  - `PM_ADIC = 260 kg/m²`
  - `q_G = PP_LOSA + 260` (SC separada, NO incluida en q_G)
- **Cielo piso 4°**:
  - `PP_LOSA = e(m) × 2500 kg/m³`
  - `PM_ADIC superficial = 200 kg/m²`
  - `q_G = PP_LOSA + 200` (SC separada, NO incluida en q_G)
- Zona "**CARGAS DE DISEÑO (CARGA LINEAL)**" (ROOF):
  - `PM_ADIC = 1500 kg/m` como **carga lineal separada**
  - NO se convierte ni se suma al q_G superficial (ver `linear_loads_LT2.csv`).

Conversión: `qG_kN_m2 = qG_kg_m2 × 9.81 / 1000`.

## Espesores

Mapeo plano → nivel (corregido; convención estructural LT2):

- **Plano 101** (`PLANTA CIELO 1° SUBTERRÁNEO A CIELO PISO 3°`) cubre **L1, L2, L3, L4**.
  - `e = 15 cm = 0.15 m` confirmado (anotación explícita "LOSA e=15").
  - `PP_LOSA = 0.15 × 2500 = 375 kg/m²`
  - `q_G = 375 + 260 = 635 kg/m² = 6.22935 kN/m²`.
- **Plano 102** (`PLANTA CIELO PISO 4°`) corresponde al **ROOF**.
  - Espesor por confirmar → `PENDING_VISUAL_CONFIRMATION`. No asumir 15 cm.
  - PM_ADIC superficial = 200 kg/m² confirmado, pero `q_G` no definitivo sin `e`.
- No existe nivel de carga adicional entre L4 y ROOF.
- **B1 / fundaciones (plan 200):** fuera de los diafragmas del modelo (B1 usa apoyos fijos);
  no se define losa de carga para vigas en este bloque.

## Estado por nivel

| nivel | e | PP kg/m² | PM_ADIC kg/m² | q_G kg/m² | q_G kN/m² | estado | fuente |
|---|---|---|---|---|---|---|---|
| L1 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 (LOSA e=15) + 700 |
| L2 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| L3 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| L4 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| ROOF | pendiente | — | 200 (sup.) | — | — | PENDING_VISUAL_CONFIRMATION | 102 + 700 |

## Pendiente visual (no bloqueado, requiere lectura de símbolos)

1. Leer espesor real de **ROOF** en plan 102 / armadura 202.
2. Confirmar paños / "LOSA 5/CUADRO (S.1.C.)" en plan 101.
3. Zonificar SC por hatch (separada, fuera de q_G).
