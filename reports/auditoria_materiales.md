# Auditoría de materiales y convención de muros — Edificio de Ingeniería LT2

**Fecha:** 2026-08-29 · **Tipo:** solo lectura · **Sin cambios de geometría ni código de análisis.**

## Objetivo
Determinar si el repositorio contiene propiedades elásticas del hormigón (E, nu, G) con valor y
unidades trazables, y si existe una convención explícita para modelar los muros M.H.A. como
elementos lineales equivalentes, antes de definir materiales o implementar elementos en OpenSees.

## Archivos y fuentes revisados
- `README.md`, `AGENTS.md`, `requirements.txt`, `.gitignore` (todo el contenido).
- `src/*.py` (todos): `wall_digitizer_lt2.py`, `check_wall_geometry.py`, `check_beam_geometry.py`,
  `check_geometry.py`, `check_vertical_connectivity.py`, `check_supports_diaphragms.py`,
  `plan_view_lt2.py`, `viewer_lt2.py`, `viewer_lt2_interactive.py`,
  `build_opensees_model.py`, `check_opensees_model.py`.
- `tests/test_wall_digitizer_lt2.py`.
- `data/geometry/*.csv` y `data/sections/sections_LT2.csv` (todos).
- Planos en el repo: `2024_22-101-Model.pdf` y `2024_22-102-Model.pdf` (texto extraído con pypdf).
- Historial git completo (15 commits), incluidos contenidos de cada commit
  (`git log -S "f'c"`, `-S "modulus"`, `-S "elasticBeamColumn"`).
- Directorios `reports/`, `results/`, `unity/` (presentes pero vacíos).

## Conclusión 1 — No hay propiedades de material definidas
No existe en el repositorio un valor explícito y trazable de **E**, **nu** ni **G**, y no se ha
declarado ningún **sistema de unidades de fuerza** para el análisis. No hay f'c, MPa, kg/cm²,
kN/carga ni módulos en textos, CSV, código, planos ni historial git. La única unidad consistente
usada en la geometría es el **metro (m)**.

## Conclusión 2 — No hay convención de muro lineal equivalente
No existe en el repositorio una convención explícita para modelar los muros M.H.A. como elementos
lineales equivalentes en un modelo de análisis. La etiqueta "(idealizacion)" que aparece en
`wall_digitization_log_LT2.csv:6-9` se refiere a la idealización **en planta** del núcleo derecho
(línea de eje con espesor), no a un elemento estructural de OpenSees. No está decidido el tipo de
elemento, sección equivalente, ancho efectivo, tratamiento del eje no-centroidal ni criterios de
rigidez/fisuración.

## Datos geométricos de muros que sí existen
- `data/geometry/walls_LT2.csv`: 8 muros M.H.A. como línea de eje (x1,y1,x2,y2) con
  `thickness_m`: M001/M003 e=0.60 ("M.H.A. e=60; eje A' con caras a −0.20/+0.40 m"),
  M002/M004 e=0.30, M005/M007/M008 e=0.25 y M006 e=0.30 (núcleo derecho, idealización en planta).
- `data/geometry/wall_segments_LT2.csv`: 40 segmentos (8 muros × 5 franjas verticales
  B1→L1→L2→L3→L4→ROOF), espesor constante por segmento, con planos fuente por tramo
  (101 para B1–L4, 102 para L4–ROOF).
- Longitudes en planta (del log): L≈2.92–3.18 m.
- Solo geometría y espesores; sin propiedades de material asociadas.

## Estado de `build_opensees_model.py`
- Esqueleto OpenSees **validado y funcional**: 262 nodos estructurales + 5 master, 22 apoyos
  empotrados en B1, 3 geomTransf (columnas Z, vigas X/Y), 5 diafragmas rígidos (48 esclavos por
  nivel L1–ROOF), handler Transformation. Sin cargas, masas ni análisis.
- La **materialización de elementos está bloqueada a propósito**: `elasticBeamColumn` requiere E
  (y G/nu) que no existen; por decisión de proyecto el módulo no inventa valores y reporta el
  parámetro faltante. Los muros quedan también pendientes por falta de idealización definida.
- `check_opensees_model.py` verifica la topología contra los CSVs y **falla (exit≠0)** mientras
  no se materialicen vigas/columnas/muros, reportando exactamente qué falta.

## Información que falta para continuar
1. **f'c del hormigón o E directo**, y unidades de presión (MPa, kg/cm²).
2. **nu** (o justificación de un valor asumido) y **unidad de fuerza** del modelo (kN, tonf…).
3. **Convención de modelación de muros M.H.A.**: tipo de elemento lineal equivalente, sección
   (L_eff × t), tratamiento del eje no-centroidal (M001/M003) y criterios de rigidez/fisuración.
4. **Planos E300–E305**: están referenciados en `data/geometry/sources_LT2.csv`
   (elevaciones) pero **no están disponibles en el repositorio**; podrían contener notas útiles
   (rótulos o especificaciones de materiales) y conviene solicitarlos o confirmar su inexistencia.

## Decisión de proyecto
No inventar parámetros ni materializar elementos hasta disponer de información respaldada por el
curso/docente. Ningún valor de E, nu o G será adoptado de otros proyectos, ejemplos o benchmarks.
Todo cambio posterior en materiales o muros se acompañará de su verificación y del archivo fuente.