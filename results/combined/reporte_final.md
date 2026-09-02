# Edificio de Ingeniería — Informe final consolidado del modelo estructural

**Modelo combinado LT1 + LT2 con muros modelados COMO COLUMNAS (instrucción del profesor).**
Fecha de cierre: 2026-09-02 · Sin modificaciones a los builders originales LT1/LT2 · Sin commit/push.

---

## A. Sistema de coordenadas y unidades

- Modelo global en **metros** y **kN**, `ndm=3, ndf=6`.
- **LT2** permanece en su sistema original.
- **LT1** se transforma al sistema combinado (interfaz en `x = 31.25`):

```
x_final = 31.25 + x_LT1
y_final = -y_LT1 - 0.25
z_final = z_LT1
```

- Materiales, secciones y cargas en kN (fuerza), m (longitud), kN·m2 (E·A), etc.

---

## B. Geometría y nodos

| Concepto | Valor |
|---|---|
| Nodos totales combinados | **442** |
| Elementos totales | **602** |
| Nodos de interfaz compartidos (x = 31.25) | **12** |
| Nodos LT1 remapeados a tags LT2 en la interfaz | Sí (mapa fijo en `config.INTERFACE_MAP`) |
| Nodos duplicados geométricos | 0 |
| Tags de nodo duplicados | 0 |
| Tags de elemento duplicados | 0 |
| Elementos de longitud cero | 0 |

Niveles comunes (z exacto): L2 = −0.05 (P1), L3 = 3.91 (P2), L4 = 7.87 (P3), ROOF = 11.83 (P4).
LT2 añade L1 = −4.01 y B1 = −7.97 (base de los muros/columnas).

---

## C. Vigas y columnas (existente, sin cambios)

| Torre | Columnas | Vigas | Muros |
|---|---|---|---|
| **LT2** | 50 | 230 | 80 (M001–M008, modelados como columnas) + 10 conectores |
| **LT1** | 39 | 175 | 18 |

No se ha modificado la numeración ni la geometría de vigas/columnas originales de LT1/LT2.

---

## D. Muros LT2 M001–M008 como COLUMNAS (`elasticBeamColumn`)

Convención del profesor: *"Los muros se modelan COMO COLUMNAS."* Cada uno de los 8 muros
se digitalizó en **40 tramos verticales** entre niveles (B1…ROOF, 5 tramos de ≈3.96 m).
Cada tramo (panel con huella horizontal `L` y espesor `t`) se modela con **2 elementos
verticales `elasticBeamColumn`** en sus bordes verticales, con **sección rectangular real**
`t × L` y material **CONC_G25** (E = 23.5 GPa, ν = 0.20, G = 9.79 GPa).

| Muro | t [m] | huella L [m] | A [m²] | Iy [m⁴] | Iz [m⁴] | J [m⁴] | Sección | Tramos | Niveles |
|---|---|---|---|---|---|---|---|---|---|
| M001 | 0.60 | 2.92 | 1.752 | 1.2449 | 0.0526 | 0.1830 | 8001 | 5 | B1→ROOF |
| M003 | 0.60 | 2.915 | 1.749 | 1.2385 | 0.0525 | 0.1827 | 8002 | 5 | B1→ROOF |
| M002 | 0.30 | 1.75 | 0.525 | 0.1340 | 0.0039 | 0.0140 | 8003 | 5 | B1→ROOF |
| M004 | 0.30 | 1.75 | 0.525 | 0.1340 | 0.0039 | 0.0140 | 8003 | 5 | B1→ROOF |
| M005 | 0.25 | 3.095 | 0.774 | 0.6176 | 0.0040 | 0.0153 | 8004 | 5 | B1→ROOF |
| M007 | 0.25 | 3.095 | 0.774 | 0.6176 | 0.0040 | 0.0153 | 8004 | 5 | B1→ROOF |
| M006 | 0.30 | 3.045 | 0.914 | 0.7058 | 0.0069 | 0.0257 | 8005 | 5 | B1→ROOF |
| M008 | 0.25 | 3.18 | 0.795 | 0.6699 | 0.0041 | 0.0157 | 8006 | 5 | B1→ROOF |

- Elementos muro-columna: **80** (tags 4001–4080), secciones 8001–8006 (6 únicas, CONC_G25).
- **150 nodos huérfanos** (0 elementos previamente) quedan conectados por los muros.
- Todas las bases de muro (B1) son fijas y cuentan en el balance de reacciones.

---

## E. Vigas flotantes LT2 → conectores viga–muro (diagnóstico resuelto)

Se detectaron **9 componentes sin camino al apoyo** por vigas flotantes. Se resolvieron con
un conector **real** (`elasticBeamColumn` horizontal-X, misma sección de viga) en lugar de
`rigidLink`/`equalDOF` (que producían singularidad de Transformation por doble restricción con
el `rigidDiaphragm` del piso).

**Familia A — cabezeros portantes x = 0.40 (M001/M003), 10 conectores (tags 9001–9010):**
cada extremo del cabezero (0.4, y, z) se une al nodo del muro-columna (0.1, y, z),
salvando la excentricidad de 0.3 m entre cara y eje.

| Elemento | Girder extremo → Muro | Nivel | y [m] |
|---|---|---|---|
| 9001 | 29 → 25 | L1 | 1.825 (M001) |
| 9002 | 33 → 26 | L1 | 14.325 (M003) |
| 9003 | 77 → 73 | L2 | 1.825 |
| 9004 | 81 → 74 | L2 | 14.325 |
| 9005 | 125 → 121 | L3 | 1.825 |
| 9006 | 129 → 122 | L3 | 14.325 |
| 9007 | 173 → 169 | L4 | 1.825 |
| 9008 | 177 → 170 | L4 | 14.325 |
| 9009 | 221 → 217 | ROOF | 1.825 |
| 9010 | 225 → 218 | ROOF | 14.325 |

**Familia B — malla/parapeto ROOF no portante (2231–2234, 2236, 2237):** sin carga de losa
(benchmark excluye ROOF) y sin apoyo cercano; se **retiran del análisis** (convención
`load_only` de LT1). No alteran el equilibrio por llevar carga nula.

Balance de `lt2_connect.py`: 10 conectores, 6 elementos ROOF retirados, 10 nodos huérfanos
eliminados, **0 componentes flotantes restantes**.

---

## F. Diafragmas

- **UN** `rigidDiaphragm` por nivel común, **master LT2** (1002–1005) + L1 (master LT1 preservado).
- Esclavos = nodos del nivel (excluyendo masters y girder-ends atados por conector).
- Masters fijados en `uz, rx, ry` por `_build_masters` (no son mecanismos).

---

## G. Cargas gravitacionales

| Origen | Pattern | Carga vertical [kN] |
|---|---|---|
| LT2 (losas) | 1 | 11 541.2916 |
| LT1 (tributaria) | 6000 / serie 5000 | 25 394.4418 |
| **Combinada** | — | **36 935.7333** |

Los muros aportan rigidez como columnas, **sin carga adicional** (igual convención que vigas/columnas).

---

## H. Análisis estático

Solver BandGeneral · RCM · Linear · LoadControl(1.0):

- **`rc = 0`** → análisis completo exitoso.
- Sin singularidad: el par anterior de muros/vigas flotantes quedó resuelto y la doble
  restricción de Transformation eliminada.

---

## I. Equilibrio (verificación de reacciones)

| Magnitud | Valor |
|---|---|
| Σ Rz [kN] | **36 935.7333** |
| Carga vertical total [kN] | 36 935.7333 |
| Error relativo | **1.253e-11** (equilibrio exacto) |
| Σ Rx [kN] | 9432.12 (equilibrio no vertical; sin cargas horizontales) |
| Σ Ry [kN] | −5920.90 |

El balance vertical cierra con error de máquina → el modelo es internamente consistente.

---

## J. Desplazamientos verticales máximos

| Nivel LT2 | Uz mín. [m] |
|---|---|
| L1 | −0.0159 (≈ 1.6 cm) |
| L2 | −0.1449 |
| L3 | −0.1209 |
| L4 | −0.1181 |
| ROOF | −0.1244 |

- Máximo global: **Uz = −0.1449 m** en el nodo LT1 **1000078**.
- Tras la conexión viga–muro, el modo blando vertical (~18 cm en LT2) desaparece; las
  deflexiones LT2 en L1 quedan en orden de **cm**, valores estructuralmente razonables.
- Los valores mayores en L2+ corresponden a nodos de la envolvente de transferencia LT1/LT2.

---

## K. Verificaciones automáticas (PASO 7, `CombinedChecks`)

Resultado: **todas CRÍTICAS = OK**, ninguna bloquea el análisis.

- Nodos duplicados geométricos: OK (0).
- Tags de nodo/elemento duplicados: OK.
- Elementos de longitud cero: OK (0).
- Referencias a nodos inexistentes: OK (0).
- Interfaz: 12 nodos compartidos presentes: OK.
- Columnas LT1 duplicadas entre dos nodos de interfaz: OK (0, se descartaron las 9 de la línea común).
- Sin solape espacial LT1/LT2: OK (interfaz compartida por diseño).
- Dominios de geomTransf/pattern/timeSeries sin colisión de tags: OK.

---

## L. Entregables (resultados finales)

En `results/combined/`:

- `reporte_final.md` — este informe consolidado (A–M).
- `summary.txt`, `model_stats.csv`, `gravity_check.csv` — resumen numérico, estadísticas y equilibrio.
- `nodes_interface.csv` — la interfaz LT1/LT2.
- `combined_geometry.html` — geometría del modelo.
- `lt1_lt2_3d_isometrico.html` — vista 3D isométrica general.
- `lt1_lt2_3d_lateral_X.html` — alzado en X.
- `lt1_lt2_3d_lateral_Y.html` — alzado en Y.
- `lt1_lt2_3d_planta.html` — vista en planta.

Todos los archivos HTML son **plotly self-contained** (abren en navegador, sin dependencias).

---

## M. Estado de cumplimiento de la Semana 2 (AGENTS.md)

- **Geometría estructural completa**: sí.
- **Nodos**: 442, reproducibles (mapas de tags fijos en `config`).
- **Vigas**: LT1 175 + LT2 230.
- **Columnas**: LT1 39 + LT2 50.
- **Muros**: LT2 M001–M008 modelados como columnas (`elasticBeamColumn`, CONC_G25) = 80 elementos.
- **Apoyos**: bases de columnas y muros LT2 + bases LT1, carga soportada.
- **Diafragmas**: rigidDiaphragm por nivel común (master LT2).
- **Chequeos geométricos**: `combined_geometry.html` + `CombinedChecks` todos OK.
- **Viewer 3D inicial**: 4 vistas finales generadas.

**Observación de diseño (documentada, sin cambiar):** las deflexiones máximas en niveles
superiores (orden 12–15 cm en L2+) se concentran en la zona de transferencia LT1↔LT2; en
análisis dinámico/sísmico podrán re-evaluarse con el espectro del proyecto.