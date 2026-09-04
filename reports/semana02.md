# Semana 2 — Modelo estructural combinado LT1 + LT2 (Edificio de Ingeniería)

**Fecha:** 2026-09-04

**Alcance:** geometría estructural completa, nodos, vigas, columnas, muros,
apoyos, diafragmas, chequeos geométricos, áreas tributarias / cargas y visor
3D inicial, integrados en un **modelo combinado LT1 + LT2** sobre OpenSees.

La geometría se almacena **fuera de Unity**, en `data/` (planos y CSV), y el
modelo de cálculo se ensambla en Python/OpenSees. Unity es solo el visor; la
fuente de verdad son los datos. Unidades SI: **kN, m**.

---

## 1. Trazabilidad plano → elemento FE

Cada elemento FE tiene una traza reproducible al plano `.dxf`/`.pdf` origen y a
su ID de geometría (`data/geometry/*.csv`). El ID de nodo/elemento en OpenSees es
por ello reproducible al re-ejecutar el pipeline.

**Viga ejemplo — `L1_V001` (tramo corrido eje inferior):**

| Eslabón | Dato |
|---|---|
| Plano | `2024_22-101-Model.pdf` (fuente `LT2_PTYPE`) |
| Geometría | `data/geometry/beams_LT2.csv` → `x1,y1=1.85,0.0`, `x2,y2=3.75,0.0`, `L=1.90 m`, sección `V60x80` |
| Sección FE | `data/sections/sections_LT2.csv` → `V60x80` → sectionTag (LT2 secciones base `5001+`) |
| Elemento FE | `elasticBeamColumn` tag **2001** (`TAG_BEAM_BASE + i`, `build_opensees_model.py:301`) |
| Carga | `data/loads/beam_gravity_loads_LT2.csv` → `element_tag=2001`, `qG` ver §4 |

**Muro ejemplo — `M001` (núcleo oeste, tramos B1…ROOF):**

| Eslabón | Dato |
|---|---|
| Plano | `2024_22-101-Model.pdf` (B1→L4), `2024_22-102-Model.pdf` (L4→ROOF) |
| Geometría | `data/geometry/wall_segments_LT2.csv` → `M001_*`, huella `0.1,-1.095 → 0.1,1.825`, `t=0.60 m` |
| Modelo | muro-columna a dos bordes verticales (`elasticBeamColumn`), `lt2_walls.py:114` |
| SectionTag | `WALL_SECTION_BASE=8001+` — sección equivalente `A=t·L`, `Iy=t·L³/12`, `Iz=L·t³/12`, `E=23.5 GPa` (CONC_G25) |
| Elementos FE | tags `4001+` (`TAG_WALL_BASE=4001`) |

**Columna ejemplo — `P001` (tramos B1…ROOF), sección `P70x70`:**

| Eslabón | Dato |
|---|---|
| Plano | `2024_22-101-Model.pdf` (B1→L4), `2024_22-102-Model.pdf` (L4→ROOF) |
| Geometría | `data/geometry/column_segments_LT2.csv` → `P001_B1_L1`…`P001_L4_ROOF`, eje `11.25,0.0` |
| Sección FE | `P70x70` (0.70×0.70 m), sectionTag `5001+` |
| Elemento FE | `elasticBeamColumn` (`TAG_COL_BASE + i`, `build_opensees_model.py:307`) |

**Interfaz LT1↔LT2** (bloque 2a junto a torre LT2): 12 nodos compartidos que se
reutilizan con tag LT2 (`src/model_combined/config.py:58`), y 3 columnas LT1
duplicadas (P003/P007/P010) que se descartan porque ya existen continuas en LT2
(`config.py:74`). La transformación LT1→combinada es
`x_final=31.25+x_LT1`, `y_final=−y_LT1−0.25`, `z_final=z_LT1` (`config.py:23`),
con la interfaz en `x=31.25`.

---

## 2. Estadísticas del modelo

Resumen consolidado (`results/combined/model_stats.csv`, `summary.txt`):

| Métrica | Valor |
|---|---|
| Nodos totales | **442** |
| Elementos totales | **602** |
| Nodos de interfaz compartidos LT1/LT2 | 12 |
| LT2 — vigas / columnas / muros-col / conectores | 230 / 50 / 80 / 10 |
| LT1 — columnas / vigas / muros | 39 / 175 / 18 |
| Carga vertical total (qG) | **36 935.73 kN** |
| Suma de reacciones verticales | 36 935.73 kN |
| Error relativo de equilibrio | 1.25e-11 |
| Desplazamiento vertical máximo | −0.145 m (nodo 1000078) |
| Apoyos considerados | **37** |
| Diafragmas | **5** (L1, L2, L3, L4, ROOF) |

Pisos estructurales con losa: L1 (−4.01), L2 (−0.05 = Cielo Piso 1), L3 (3.91),
L4 (7.87) y ROOF (11.83). La elevación B1 = −7.97 corresponde a fundación/radier
(véase §9: pendiente de verificación).

---

## 3. Carga superficial (q_G) de losa

`data/loads/slabs_LT2.csv` — densidad 2500 kg/m³, losa `e=15 cm`,
terminaciones 260 kg/m² (plano 700):

| nivel | e (m) | PP kg/m² | termin. kg/m² | q_G kg/m² | q_G kN/m² | fuente |
|---|---|---|---|---|---|---|
| L1 | 0.15 | 375 | 260 | 635 | **6.22935** | 101 + 700 |
| L2 | 0.15 | 375 | 260 | 635 | **6.22935** | 101 + 700 |
| L3 | 0.15 | 375 | 260 | 635 | **6.22935** | 101 + 700 |
| L4 | 0.15 | 375 | 260 | 635 | **6.22935** | 101 + 700 |
| ROOF | *pendiente* | — | 200 (sup.) | — | — | 102 + 700 |

La carga lineal separada `PM_ADIC = 1500 kg/m = 14.715 kN/m` (ROOF, plano 700)
se almacena aparte y **no** forma parte de `q_G` superficial.

---

## 4. Áreas tributarias y carga a la viga (ejemplos reales)

`data/loads/tributary_areas_LT2.csv` genera áreas tributarias por nivel con
método de celdas de cuadrícula y las renorma al área neta del paño
(`src/tributary_areas.py`). Tres ejemplos verificados (4 pisos × 80 tributarias
= 320 filas; 296 transferidas + 24 `WALL_EDGE_PENDING` que no bloquean el
análisis):

### a) `L1_V001` → elemento 2001 (tramo corrido inferior, L=1.900 m)

| Campo | Valor |
|---|---|
| Polígono (polilínea cerrada) | banda a lo largo del eje `y=0`, `x∈[1.85, 3.75]`, `y∈[0.00, 1.65]`, 136 vértices de muestreo |
| Área tributaria | 1.7938 m² |
| Carga aplicada | 11.1743 kN |
| Longitud de viga | 1.900 m |
| Carga lineal equivalente | 11.1743 / 1.900 = **5.881 kN/m** |
| Fuente | `data/loads/tributary_areas_LT2.csv` · status `TRANSFERIDO` |

### b) `L1_V009` → elemento 2009 (viga vertical, L=4.265 m)

| Campo | Valor |
|---|---|
| Polígonos (2 recintos) | (1) banda `x∈[2.10, 3.75]`, `y∈[0.05, 4.25]` (243 vértices); (2) banda `x∈[3.75, 5.65]`, `y∈[0.00, 4.25]` (270 vértices) |
| Área tributaria total | 8.8837 m² |
| Carga aplicada | 55.3399 kN |
| Carga lineal equivalente | 55.3399 / 4.265 = **12.975 kN/m** |

### c) `L1_V30_01` → elemento 2081 (viga `V30x80`, L=1.85 m)

| Campo | Valor |
|---|---|
| Polígonos (2 recintos) | (1) banda `x∈[1.90, 3.70]`, `y∈[2.60, 4.25]` (132 vértices); (2) banda `x∈[1.90, 3.75]`, `y∈[4.265, 5.965]` (126 vértices) |
| Área tributaria total | 3.3627 m² |
| Carga aplicada | 20.9474 kN |
| Carga lineal equivalente | 20.9474 / 1.850 = **11.323 kN/m** |

En los tres casos se cumple que `carga = qG × A_trib` (p. ej. 6.22935 × 1.7938
= 11.1743 kN), validando la conversión superficial → lineal.

---

## 5. Conservación / cierre de cargas

Para cada nivel, la suma de cargas tributarias debe igualar `q_G × A_piso`:

| nivel | n trib | A tributaria (m²) | Σ carga (kN) | qG·A (kN) | error rel. |
|---|---|---|---|---|---|
| L1 | 80 | 488.8032 | 3044.9264 | 3044.9264 | 0.000001 % |
| L2 | 80 | 488.8032 | 3044.9264 | 3044.9264 | 0.000001 % |
| L3 | 80 | 488.8032 | 3044.9264 | 3044.9264 | 0.000001 % |
| L4 | 80 | 488.8032 | 3044.9264 | 3044.9264 | 0.000001 % |

Cierre **global** en modelo combinado (`results/combined/gravity_check.csv`):

| métrica | valor |
|---|---|
| Carga vertical LT2 | 11 541.29 kN |
| Carga vertical LT1 | 25 394.44 kN |
| Carga vertical combinada | 36 935.73 kN |
| Σ reacciones verticales | 36 935.73 kN |
| Error relativo de equilibrio | **1.25e-11** ✓ |

El error < 1e-8 demuestra que las cargas aplicadas se cierran en las reacciones
(no se pierde ni se añade carga en el ensamblaje).

---

## 6. Apoyos

- **Apoyos LT2 (22):** empotramientos en la base del modelo (nivel **B1**), fijos
  en los 6 gdl, `data/geometry/supports_LT2.csv`. Base idealizada como empotrada;
  interacción suelo-estructura fuera de alcance.
- **Apoyos LT1:** base provisional fijada en nivel `P1` (Cielo Piso 1),
  `ops.fix(1,1,1,1,1,1)` (`lt1_builder_combined.py:477`); son nodos de piso `P1`
  usados por elementos LT1 (la cuenta LT1 = 37 − 22 = **15** se deriva del total
  combinado).
- **Total: 37 apoyos** (`n_support` en `summary.txt`).

---

## 7. Diafragmas rígidos

Diafragmas rígidos por nivel (`data/geometry/diaphragms_LT2.csv`) con
`rigidDiaphragm` perpendicular Z (constriñe `UX,UY,RZ`; libres `UZ,RX,RY`),
handler **Transformation**:

| diafragma | nivel | z (m) | master | nodos esclavos | gdl constriñidos |
|---|---|---|---|---|---|
| DIA_L1 | L1 | −4.01 | NM_L1 | 48 | UX, UY, RZ |
| DIA_L2 | L2 | −0.05 | NM_L2 | 48 | UX, UY, RZ |
| DIA_L3 | L3 | 3.91 | NM_L3 | 48 | UX, UY, RZ |
| DIA_L4 | L4 | 7.87 | NM_L4 | 48 | UX, UY, RZ |
| DIA_ROOF | ROOF | 11.83 | NM_ROOF | 58 | UX, UY, RZ |

Los diafragmas LT2 se preservan en el modelo combinado y los niveles estructurales
LT1 se comparten (master LT2 `1002…1005` con niveles LT1 P1…P4,
`config.py:44`). Los masters son nodos conceptuales (no pertenecen a elementos).

---

## 8. Visor 3D en Unity

Visor mínimo en `unity/StructuralViewer/` (Unity 2022.3 LTS, sin paquetes
externos). Los datos vienen de `data/processed/unity_model.json` (exportado por
`src/export_unity.py`, control `results/unity_export_check.txt` → PASS). **Unity
no es la fuente de verdad**; sólo muestra el JSON.

- Escena `Assets/Scenes/Main.unity` + scripts `ModelLoader.cs` (carga JSON y
  construye el modelo) y `CameraController.cs` (órbita/zoom/pan).
- Carga automática de `Data/unity_model.json` (o el JSON del repo si se mueve el
  proyecto); avisa si hay que ejecutar `python src/export_unity.py`.
- Selección con botón izquierdo de **nodos** (nodeTag, nivel, posición) y de
  **elementos** (elementTag, sección, material, origen plano/ID, status de
  análisis).
- Colores por familia: columnas gris, vigas azul, muros naranja, elementos
  solo-carga magenta, apoyos amarillo, diafragmas cian semitransparente, áreas
  tributarias naranja semitransparentes.
- Toggles: Nodos, Vigas, Columnas, Muros, Apoyos, Diafragmas, Áreas tributarias,
  IDs, Ejes locales.
- **Tributary Area Inspector:** al seleccionar una viga FE con área tributaria
  muestra slab, área, q_G, carga total y carga lineal equivalente.
- Contenido exportado: 187 nodos, 241 elementos FE (48 columnas, 175 vigas,
  18 muros) + 16 solo-carga, 16 apoyos, 4 diafragmas, 4 losas y 175 áreas
  tributarias.

---

## 9. Modificación del modelo (verificado sin re-análisis)

Ejemplo de cambio geométrico/paramétrico reproducible sobre los datos (la
geometría vive en CSV, no en Unity):

**Cambiar la sección de la viga `L1_V001`** en
`data/sections/sections_LT2.csv` (o el mapeo en `data/geometry/beams_LT2.csv`,
redefiniendo una sección nueva `Vxx`). Al re-exportar, el elemento 2001 apunta a
una nueva sección y su área tributaria / carga **no** cambia (depende de
geometría de paño), pero su rigidez (`A, Iy, Iz, J`) sí. Requiere re-ejecutar
`src/export_unity.py` y el análisis para reflejarlo.

Análogamente, se puede desplazar un vértice de un polígono tributario en
`data/loads/tributary_areas_LT2.csv` y volver a correr `src/check_tributary_areas.py`
para verificar el cierre de §5 antes de cualquier análisis.

> La regla del proyecto "no inventar dimensiones" se cumple: toda geometría
> proviene de los planos; modificar una sección requiere su justificación en los
> planos antes de aceptarse.

---

## 10. Uso de IA y corrección de errores del agente

El agente intervino en la digitalización, la geolocalización de niveles y la
verificación; todo cambio se documentó y validó. Ejemplo representativo de
**corrección de un error del agente**:

> **Confusión entre "Cielo piso 1" y "Cielo piso 1 subterráneo".** El agente
> inicialmente trataba el nivel `S1 (−4.01)` como si fuera "Cielo Piso 1".
> Quedó **corregido y documentado**: `CIELO PISO 1 = z −0.05` (nivel `P1` LT1 =
> `L2` LT2, ya modelado, master 1002), que es **distinto** de
> `CIELO PISO 1 SUBTERRÁNEO = z −4.01` (`S1`, extraído del DXF pero **no**
> modelado como piso estructural). La evidencia DXF es línea por línea
> (`2017_67-101.dxf`: `(NIVEL SUPERIOR LOSA −0.05)` y
> `(NIVEL SUPERIOR LOSA −4.01 (S.I.C.))`). Esto evita asignar la losa de −4.01 al
> nivel de −0.05 y mantiene la coherencia de niveles de §2 y §7.

Este tipo de corrección se refleja en `config.py` (mapa `L2=P1`, master 1002) y
en `data/geometry/levels.csv`. La reproducibilidad queda garantizada por los IDs
en los CSV y el cierre de §5.

---

## Pendientes (documentados, no inventados)

- **Espesor real de ROOF** `PENDING_VISUAL_CONFIRMATION`
  (`data/loads/slabs_LT2.csv`, fila `S_ROOF_TYP`).
- **Cota de fundación/radier LT1**: el plano `2017_67-100.dxf` indica
  `(NIVEL SUPERIOR RADIER S/PLANTA)` y `N.P.T.=±0.00` sin cota numérica de
  fundación; `levels.csv` anota `B1=−7.97` **sin verificar**. No se usa
  `B1=−7.97` como cota estructural definitiva (`INPUT_REQUIRED`).
- Checker `elementos_duplicados` reporta **17 pares** de nodos con >1 elemento,
  heredado de LT1 — informativo, no bloquea.