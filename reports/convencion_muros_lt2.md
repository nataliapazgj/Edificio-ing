# Convención de modelación de muros M.H.A. como elementos lineales equivalentes — LT2

**Fecha:** 2026-08-31 · **Tipo:** solo lectura · **Sin cambios de geometría, código ni análisis.**

## Objetivo
Determinar, a partir de los documentos del curso y del repositorio, la convención exigida para
representar los muros de hormigón armado (M.H.A.) del Edificio de Ingeniería (LT2) mediante
**elementos lineales equivalentes** en el modelo global OpenSees.

## Fuentes revisadas
- `Proyecto 2/Enunciado general.txt` (completo, 660 líneas).
- `Proyecto 2/Tutorial mínimo de OpenSeesPy para análisis estructural 3D.txt`.
- `Proyecto 2/Recursos técnicos y estrategia de trabajo con IA.txt`.
- `Proyecto 2/Honors Track .txt`, `Proyecto 2/P1 - Tutorial de Unity.txt`, `Proyecto 2/Sidequests del proyecto.txt`.
- `Proyecto 1/P1L1.txt` (Semana 1 — benchmark 3D), `P1L0.txt`, `P1A1.txt`.
- `Proyecto 1/README.md`, `Proyecto 1/AGENTS.md`.
- `P1 benchmark/README.md`, `P1 benchmark/verification/verification.md`.
- `Edificio-ing/README.md`, `Edificio-ing/AGENTS.md`, `Edificio-ing/reports/*.md`, `Edificio-ing/src/*.py`, `Edificio-ing/data/*`.
- Historial git de `P1 benchmark` y `Edificio-ing` (búsqueda `-S "convencion"`, `-S "equivalent wall"`).

## Base autoritativa del curso

**`Enunciado general.txt` L46 (repetido en L376):**
> muros representados mediante **elementos lineales equivalentes** de acuerdo con la
> **convención entregada en el curso**

Este es el único mandato explícito sobre muros: se modelan como elementos lineales (no losa con
elementos finitos, no automáticamente como columna rectangular). Todos los parámetros concretos
quedan delegados a "*la convención entregada en el curso*".

---

## CONFIRMADO_CURSO

| Parámetro | Convención | Fuente / evidencia |
|---|---|---|
| Representación del muro en el modelo global | Elemento **lineal equivalente** (obligatorio) | `Enunciado general.txt` L46 y L376 |
| Tipo de modelo global | Sistema lineal elástico 3D con nodos 6 GDL | `Enunciado general.txt` L42–49 |
| Elemento base esperado | `elasticBeamColumn` (recurso oficial del curso para vigas/columnas/muros lineales) | `Enunciado general.txt` L602; `Tutorial…3D.txt` L258/464/683/1223 |

---

## CONFIRMADO_PROYECTO

| Parámetro | Convención | Fuente / evidencia |
|---|---|---|
| Elementos lineales usados en el repo | `elasticBeamColumn` para vigas y columnas | `Edificio-ing/src/build_opensees_model.py` (`_materialize`) |
| Geometría de muros disponible (línea de eje) | 8 muros M.H.A. como (x1,y1)-(x2,y2) con espesor | `data/geometry/walls_LT2.csv` |
| Subdivisión vertical por tramos | 40 segmentos = 8 muros × 5 franjas (B1→L1→L2→L3→L4→ROOF) | `data/geometry/wall_segments_LT2.csv` |
| Muros M.H.A. con eje no-centroidal | M001/M003 (e=0.60) con "*eje A' con caras a −0.20/+0.40 m*" | `walls_LT2.csv` notas; `reports/auditoria_materiales.md` L60 |
| Estado de la materialización | Muros **no** materializados a propósito; solo vigas + columnas | `reports/auditoria_materiales.md`; `src/build_opensees_model.py` blocker |

---

## NO_ENCONTRADO

| Parámetro | Estado | Evidencia |
|---|---|---|
| Área A del elemento equivalente | No aparece en ningún documento/curso | — |
| Inercia Iy e Iz del elemento equivalente | No aparece (no se autoriza asumir rectángulo→columna) | — |
| Torsión J | No aparece | — |
| Sección bruta vs rigidez reducida | No aparece | — |
| Factor de fisuración (0.35EI / 0.5EI / 0.7EI …) | No aparece; no respaldado por el curso | — |
| Brazos rígidos / rigid offsets | No aparece | — |
| Criterio de orientación de ejes locales del muro | Solo requisito genérico "*muro mal orientado*" como error a detectar | `Tutorial…3D.txt` L1018 |

---

## REQUIERE_DECISION

| Parámetro | Estado | Nota |
|---|---|---|
| Ubicación de la línea equivalente del muro | Decisión pendiente | M001/M003 tienen eje **no-centroidal** (caras a −0.20/+0.40 m respecto del eje A'); no se debe asumir colocación automática |
| Orientación de ejes locales (Iy vs Iz / eje fuerte) | Decisión pendiente | No hay regla del curso |
| Acople muro–diafragma | Decisión pendiente | Diafragmas rígidos existen (L1–ROOF), pero sin convención de conexión del muro (master/slave) |
| Tramo por piso vs muro continuo | Decisión pendiente | `wall_segments_LT2.csv` sugiere 1 elemento por tramo (40), pero no está confirmado como decisión |

---

## Conclusión

1. **Deben modelarse como elementos lineales equivalentes**: el curso lo exige (elemento
   `elasticBeamColumn`), conforme a `Enunciado general.txt` L46/L376.
2. **La convención concreta NO está disponible**: A, Iy, Iz, J, orientación de ejes locales,
   rigidez efectiva/fisuración, brazos rígidos/offsets y conexión al diafragma no figuran en
   ningún archivo del curso ni del repositorio. El enunciado las remite a "*la convención
   entregada en el curso*", que no se encuentra entre los archivos disponibles.
3. **Por tanto, los 40 muros permanecen en estado `PENDING_WALL_CONVENTION`**.
4. **No se debe materializar ningún muro** hasta recibir o aprobar una convención de modelación
   resolviendo los parámetros de la sección equivalente.

### Decisión de no-actuación
Esta auditoría no modifica código, CSV ni modelo. No se crearon secciones, no se materializaron
los 40 muros, no se aplicaron cargas ni análisis. Sin commit.
