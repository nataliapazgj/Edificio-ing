# Cargas gravitacionales de losa q_G — LT2 (primera versión)

**Fecha:** 2026-09 (bloque de implementación de cargas).

## Contenido implementado

Primera versión real de la definición de cargas de losa en `data/loads/`:

- `data/loads/slabs_LT2.csv` — parámetros de carga superficial `q_G` por losa/nivel
  (definición de carga; la geometría de paños queda separada y pendiente).
- `data/loads/linear_loads_LT2.csv` — cargas **lineales** separadas (PM_ADIC = 1500 kg/m),
  fuera del `q_G` superficial.
- `data/loads/LOSAS_LOAD_VS_GEOMETRY.md` — documenta la separación
  `slab_load_definition` (hecha) vs `slab_geometry` (pendiente, sin rehacer cargas).

## Convención de niveles (estructural LT2)

B1 = -7.97 · L1 = -4.01 · L2 = -0.05 · L3 = 3.91 · L4 = 7.87 · ROOF = 11.83

## Mapeo plano → nivel (corregido)

- **Plano 101** (`PLANTA CIELO 1° SUBTERRÁNEO A CIELO PISO 3°`) cubre los niveles
  estructurales **L1, L2, L3, L4** → `e = 15 cm` confirmado.
- **Plano 102** (`PLANTA CIELO PISO 4°`) corresponde al **ROOF** → espesor pendiente.
- No existe nivel de carga adicional entre L4 y ROOF.

## Datos confirmados implementados

Densidad = 2500 kg/m³ · `PP_LOSA = e×2500` · `q_G = PP + PM_ADIC` · `qG_kN = qG_kg×9.81/1000`.

| nivel | e (m) | PP kg/m² | PM_ADIC kg/m² | q_G kg/m² | q_G kN/m² | estado | fuente |
|---|---|---|---|---|---|---|---|
| L1 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 (LOSA e=15) + 700 |
| L2 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| L3 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| L4 | 0.15 | 375 | 260 | 635 | 6.22935 | CONFIRMADO_e15 | 101 + 700 |
| ROOF | pendiente | — | 200 (sup.) | — | — | PENDING_VISUAL_CONFIRMATION | 102 + 700 |
| B1/fund | — | — | — | — | — | fuera de diafragmas | 200 |

La **SC** de cada nivel se almacena por separado (informativa, pendiente de zonificar por
hatch) y **NO** se incluye en `q_G`.

Carga lineal separada (NO en q_G): `PM_ADIC = 1500 kg/m` = `14.715 kN/m` (ROOF, plano 700).

## Checker y pruebas

- `src/check_slab_loads.py`: verifica espesores positivos, `PP=e×density`, `qG=PP+finishes`,
  conversión kg/m²→kN/m², SC no incluida, cargas lineales separadas, niveles pendientes.
  **Resultado: errors=0, warnings=0, exit 0.**
- `tests/test_slab_loads.py`: pytest sobre los datos implementados y la conversión.

## Pendiente (requiere revisión visual de símbolos circulares)

1. Espesor real de **ROOF** (plan 102 / armadura 202) → reemplazar `PENDING_VISUAL_CONFIRMATION`.
   PM_ADIC superficial = 200 kg/m² confirmado; `q_G` no definitivo sin `e`.
2. Confirmar paños / "LOSA 5/CUADRO (S.1.C.)" en plan 101.
3. Zonificar SC por hatch (separada de q_G).

## No implementado aún (bloques siguientes)

- Polígonos / áreas tributarias (`slab_geometry`).
- Aplicación de cargas a vigas.
- OpenSees / análisis.
- Unity.
- Muros.
