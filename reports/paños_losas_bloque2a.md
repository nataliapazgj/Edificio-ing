# Paños de losa LT2 — BLOQUE 2A (geometría)

**Fecha:** 2026-09 · **Estado:** primera versión para revisión visual.

## Objetivo

Primera representación explícita y trazable de los paños de losa, compatible con los
nodos/vigas existentes, para un próximo bloque de áreas tributarias y transferencia de q_G.
**No se calculan áreas tributarias ni se distribuye q_G a vigas en este bloque.**

## Fuente geométrica

- Plantas estructurales 101/102 (láminas en repo).
- Geometría de vigas/columnas/muros ya digitalizada en `data/geometry/` (compatible con el
  modelo).
- Huecos de escalera de ROOF documentados en `reports/digitalizacion_vi_roof_pendiente.md`.

## Método

Paños derivados de la **grilla de vigas** digitalizada (líneas de viga = bordes de paño),
sobre el recinto continuo de losa x∈[0.4, 31.25], y∈[0, 16.15]:

- **Planta tipo (L1-L4, plan 101):**
  - Bloque izquierdo x[0.4,11.25], filas y{0,4.265,8.9,11.885,16.15}, columnas x{0.4,3.75,7.5,11.25} → 12 paños.
  - Bloque derecho x[11.25,31.25], filas y{0,8.9,16.15}, columnas x{11.25,16.25,21.25,26.25,31.25} → 8 paños.
  - Total **20 paños**, reutilizados idénticos en L1..L4 (plantilla `TYP`).
- **ROOF (plan 102):** mismos bloques base; los huecos de escalera confirmados se restan del
  área y se almacenan en la columna `holes` (rectángulo recortado a cada paño):
  hueco principal x[0.998,16.546] y[2.90,7.92] y 2º hueco este x[18.52,21.295] y[2.92,7.92].
  Las V.I. son miembros **adicionales de borde de hueco** (no subdividen losa sólida).

## Validación visual (plan 101, L1-L4)

Se revisaron crops de alta resolución de `review_crops/validation/` contra el plano 101:

- `LB_c0_r0` → símbolo de losa **0101/15** → **CONFIRMED_SLAB** (espesor 15 cm).
- `LB_c0_r3` → símbolo de losa **0114/15** → **CONFIRMED_SLAB** (espesor 15 cm).
- La planta completa 101 confirma múltiples paños con símbolo de losa y espesor inferior 15.
- `RB_c3_r0` → **LOSA de 15 cm con abertura(s)** delimitadas por elementos M.H.A. (NO celda
  completa SIN_LOSA):
  - **Hueco confirmado:** abertura principal del núcleo derecho, delimitada por los muros
    M.H.A. ya digitalizados M005 (x=28.205, e=25), M006 (y=3.180, e=30), M007 (x=31.250, e=25):
    rectángulo x[28.205, 31.250], y[3.180, 6.275]. (No se restó la prolongación M008 x=31.25
    y[0,3.18], que es muro, no abertura.)
  - **Hueco pendiente:** abertura rectangular alargada adyacente al núcleo, sin geometría
    determinable con seguridad → `PENDING_GEOMETRY_CONFIRMATION` (no resta área).

**Nomenclatura de estado (plan 101):**
- `CONFIRMED_SLAB` se usa **solo** donde existe evidencia visual (los tres paños anteriores,
  propagados a L1-L4 por compartir la plantilla `TYP` del plan 101).
- El resto de paños de la planta tipo se originaban solo por descomposición automática de
  grilla → ya **NO** se etiquetan `CONFIRMADO`; quedan `PENDING_VISUAL_CONFIRMATION`.

## Validación visual (plan 102, ROOF)

Se cruzaron los crops de `review_crops/validation/` (ROOF_*_d300) y los datos digitalizados de
`data/geometry/beams_LT2.csv` (vigas VI-01…VI-07) contra el plano 102:

- **Hueco principal de escalera CONFIRMADO:** x[0.998,16.546] y[2.90,7.92], perímetro
  delimitado en sus 4 lados por vigas invertidas: N = VI-01+VI-02 (y=7.92, 15/70), S = VI-03+VI-04
  (y=2.90, 15/68), O = VI-05 (x=0.998, 15/VAR), E = VI-06 (x=16.546, 15/76). Auditoría §8.0.
- **2º hueco este CONFIRMADO:** x[18.52,21.295] y[2.92,7.92]; borde N = VI-07 (y=7.92, 15/76,
  x 18.545..20.794) + rectángulo vectorial del plano 102. Auditoría §8.5 (NO es continuación del
  hueco principal).
- **Vigas VI = ADICIONALES de borde de hueco:** ninguna coincide con los ejes de grilla
  (y∈{0,4.265,8.9}, x∈{11.25,16.25,21.25}) → no subdividen losa sólida; delimitan únicamente los
  vanos vacíos. Los paños quedan como losa real con hueco interior (`holes`), no SU divididos en
  dos paños.
- **Paños intersectados** → `CONFIRMED_SLAB` con `holes` (rectángulo de hueco recortado) y
  `hole_status=CONFIRMED`: `LB_c0_r0`, `LB_c0_r1`, `LB_c1_r0`, `LB_c1_r1`, `LB_c2_r0`, `LB_c2_r1`,
  `RB_c0_r0`, `RB_c1_r0` (2 huecos), `RB_c2_r0`.
- **Resto de paños ROOF** (sin hueco) → `CONFIRMED_SLAB` (losa real del plan 102).
- **Espesor/e de ROOF NO leído** en el plano 102 (símbolo circular no determinable con evidencia
  visual disponible) → `thickness_m` y `qG` permanecen **None/PENDING** en ROOF. NO se asume e=15.

**Relación paños ↔ V.I.:**

| panel (ROOF) | V.I. que lo cruzan | lectura |
|---|---|---|
| LB_c0_r0 | VI-03, VI-05 | borde S y O del hueco principal |
| LB_c0_r1 | VI-01 | borde N del hueco principal |
| LB_c1_r0 | VI-03 | borde S del hueco principal |
| LB_c1_r1 | VI-01 | borde N del hueco principal |
| RB_c0_r0 | VI-02, VI-04 | borde N/S del hueco principal |
| RB_c1_r0 | VI-02, VI-04, VI-06, VI-07 | N/S principal + borde E principal + borde N 2º hueco |
| RB_c2_r0 | — | borde E estrecho del 2º hueco este |

## Resultado

Área neta = área exterior del paño − huecos confirmados. Por nivel:

| nivel | paños | área total losa (m²) | CONFIRMED_SLAB | PENDING | errores |
|---|---|---|---|---|---|
| L1 | 20 | 488.803 | 3 | 17 | 0 |
| L2 | 20 | 488.803 | 3 | 17 | 0 |
| L3 | 20 | 488.803 | 3 | 17 | 0 |
| L4 | 20 | 488.803 | 3 | 17 | 0 |
| ROOF | 20 | 406.302 | 20 | 0 | 0 |

- L1-L4 `CONFIRMED_SLAB`: `LB_c0_r0`, `LB_c0_r3`, `RB_c3_r0`.
- L1-L4 `RB_c3_r0`: `holes`=núcleo confirmado, `hole_status`=`CONFIRMED;PENDING_GEOMETRY_CONFIRMATION`.
- ROOF: **20 paños CONFIRMED_SLAB** (losa real); 9 paños con `holes` de escalera confirmados;
  espesor/e y qG siguen pendientes (NO seteado e=15).

## Archivos

- `data/loads/slab_panels_LT2.csv` — geometría (panel_id, level, source_plan, slab_id, polygon,
  area_m2, **holes**, **hole_status**, thickness_m, qG_kN_m2, status, template, notes).
- `src/gen_slab_panels.py` — generador reproducible.
- `src/check_slab_panels.py` — checker geométrico (solapes, duplicados, área≤0, fuera de dominio,
  niveles sin paños, qG pendiente, huecos dentro del paño y área consistente).
- `src/plot_slab_panels.py` — visualización QA (incluye huecos).
- `tests/test_slab_panels.py` — pytest.
- `figures/slab_panels_L1.png`, `figures/slab_panels_ROOF.png` — figuras QA.

## Verificación

- `check_slab_loads.py`: errors=0, warnings=0.
- `check_slab_panels.py`: **errors=0**, warnings=21 (ROOF qG pendiente; comportamiento esperado).
- pytest: **27 passed** (10 nuevos + 17 existentes).

## Pendiente (revisión visual / bloque siguiente)

1. `PENDING_GEOMETRY_CONFIRMATION` en `RB_c3_r0`: confirmar y digitalizar la abertura
   rectangular alargada adyacente al núcleo (plan 101) para restar su área.
2. Confirmar visualmente el resto de paños de planta tipo (hoy `PENDING_VISUAL_CONFIRMATION`).
3. **espesor/e de ROOF** para completar `qG` (símbolo circular de losa del plan 102 aún no leído;
   el 2º hueco este y VI-07b borde sur quedan anotados en la auditoría de V.I.).
4. Subdivisión de paños por vigas parciales (V30 en filas 4.265/11.885 cubren x 1.9→7.5) —
   verificado si es necesaria refinación.
5. Bloques posteriores: áreas tributarias y transferencia de q_G a vigas.
