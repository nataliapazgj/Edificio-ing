# Auditoria dirigida - Vigas P1, muros P1-P4 y columnas P3-P4 (Semana 2)

- Fecha: 2026-09-01 | Estado: **SIN MODIFICAR** modelo FE, unity_model.json, cargas, areas tributarias ni DXF.
- Fuentes de lectura: `building_3d_aligned.json`, `unity_model.json`, DXF 101/102/103.
- Metodo: reproduccion determinista del grouping de `geometric_cleanup.py` + mapeo `physical_id` (igual que la auditoria previa).

## 1. CAUSA RAIZ: por que P1 tiene tan pocas vigas FE

El pipeline separa plantas con la VENTANA de Y CAD (`y_min..y_max` en `extract_structure.PLANTAS`), pero la SEPARACION ocurre **despues** del grouping: `load_plant` llama `group_beams(raw_viga, ...)` con las lineas del DXF completo (S1 + P1 en el 101) y solo luego filtra `mid_y` por planta. El emparejamiento de caras (`detect_face_width`) se calcula sobre TODAS las lineas.

| Metrica | DXF 101 completo (como corre el pipeline) | S1 solo | P1 solo (diagnostico) |
|---|---|---|---|
| `face_width` detectado | 20 | 20 | 60 |
| Vigas emparejadas P1 | 7 | - | 39 |
| Fragmentos P1 | 90 | - | 26 |
| Vigas emparejadas S1 | 21 | 21 | - |
| Fragmentos S1 | 17 | 17 | - |

La moda global del 101 es **20** (convencion de dibujo de S1). P1 dibuja sus vigas con ancho de cara **60 CAD**. El emparejamiento (`pair_runs_to_elements`) acepta `|d - face_width| <= width_tol` con `width_tol = 12` para vigas: un par de caras a 60 CAD da `|60 - 20| = 40 > 12` -> nunca empareja. Las vigas de P1 dibujadas con ancho ~60 quedan como fragmentos sin pareja. Las unicas 7 'hi' de P1 que casan lo hacen con ancho de cara 15-20 CAD (medido `width_cad`), es decir con la convencion de S1 y NO con la de P1: son emparejamientos sospechosos que el re-emparejamiento por planta deberia revisar.

**Resultado medido:** con el pipeline actual, las vigas P1 pasan de 7 (high-confidence) + 90 (ambiguous) a **39 vigas + 26 fragmentos** si se separa P1 antes del grouping (per-plant). Las 90 'ambiguous' de P1 son, en su mayoria, caras que no encontraron pareja por este error de ancho de cara, NO vigas inexistentes en el DXF.

Nota: el problema es exclusivo de plantas que comparten lamina con distinta convencion de ancho. S1 no cambia (21/17 global == per-plant). En el 102 (P2+P3) debe verificarse el mismo riesgo.

## 2. Estado de las 97 vigas P1

| Estado | Conteo | Detalle |
|---|---|---|
| high-confidence -> FE | 3 | vigas modeladas (elementos FE en P1) |
| high-confidence -> LOAD_ONLY | 2 | solo carga, sin rigidez |
| high-confidence -> EXCLUIDA | 2 | sin pilar soportado a <=8 m |
| ambiguous (excluidas por politica) | 90 | fragmentos sin pareja; NO entran a OpenSees |

Vigas high-confidence P1 (con estado FE/LOAD/EXCL y origen `physical_id`):

| #orig | Long. m | (x1,y1)->(x2,y2) m | Estado | Razon |
|---|---|---|---|---|
| 0 | 5.37 | (34.63,-19.11)->(40.00,-19.11) | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| 1 | 1.52 | (33.75,3.33)->(35.27,3.33) | FE | 1 elems FE |
| 2 | 6.35 | (38.90,3.33)->(45.25,3.33) | FE | 1 elems FE |
| 3 | 3.05 | (33.83,0.35)->(33.83,3.40) | FE | 1 elems FE |
| 4 | 4.41 | (34.48,-28.44)->(34.48,-24.02) | EXCLUIDA | sin pilar soportado a <=8m (d1=12.8, d2=8.8) |
| 5 | 4.41 | (34.48,-23.72)->(34.48,-19.31) | EXCLUIDA | sin pilar soportado a <=8m (d1=8.6, d2=5.3) |
| 6 | 2.24 | (37.65,-19.01)->(37.65,-16.77) | LOAD_ONLY | 1 elems de carga (sin rigidez) |

## 3. Vigas P1 potencialmente recuperables

Criterio de conectividad (politica v2 de `ops_model`): nodo FE a <= 8 m de un pilar soportado P1..P4. Aplicado a los extremos de cada viga ambiguous de P1 con la rejilla soportada:

- Vigas ambiguous con AMBOS extremos a <= 8 m de rejilla soportada: **90 de 90** (criterio 8 m es generoso con rejilla de 5 m).
- Vigas ambiguous centradas sobre una fila de rejilla (|y_centro - y_rejilla| <= 0.35 m): **43**.
- Vigas ambiguous ancladas Y sobre fila de rejilla ('recuperables estructurales'): **43**.
- Re-emparejando por planta (diagnostico): 39 pares, de las cuales 39 nuevas respecto de las 7 hi actuales.

Estas cifras son el **techo de recuperacion** si se corrige la separacion por planta. La decision de reincorporarlas (y su estado FE/LOAD_ONLY) requiere revisar cada candidato contra el DXF y la politica de modelo; NO se reincorpora nada automaticamente en esta auditoria.

## 4. Trazabilidad de muros P1-P4

| Piso | hi DXF | FE (phys) | LOAD_ONLY | EXCLUIDOS (hi) | Ambiguous |
|---|---|---|---|---|---|
| P1 | 11 | 4 | 4 | 3 | 27 |
| P2 | 4 | 1 | 3 | 0 | 9 |
| P3 | 4 | 1 | 3 | 0 | 9 |
| P4 | 6 | 3 | 3 | 0 | 6 |

Detalle por muro high-confidence (numero = `physical_id` del nivel):

| Piso | #orig | Long. m | Estado | Razon |
|---|---|---|---|---|
| P1 | 7 | 3.70 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P1 | 8 | 6.95 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P1 | 9 | 14.90 | FE | 4 elems FE |
| P1 | 10 | 3.63 | FE | 1 elems FE |
| P1 | 11 | 7.45 | EXCLUIDO | sin pilar soportado a <=8m (d1=8.2, d2=6.6) |
| P1 | 12 | 2.55 | EXCLUIDO | sin pilar soportado a <=8m (d1=10.9, d2=10.7) |
| P1 | 13 | 6.55 | FE | 1 elems FE |
| P1 | 14 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P1 | 15 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P1 | 16 | 3.05 | FE | 1 elems FE |
| P1 | 17 | 1.41 | EXCLUIDO | sin pilar soportado a <=8m (d1=10.3, d2=11.7) |
| P2 | 45 | 3.70 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P2 | 46 | 6.95 | FE | 2 elems FE |
| P2 | 47 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P2 | 48 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P3 | 49 | 3.70 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P3 | 50 | 6.95 | FE | 2 elems FE |
| P3 | 51 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P3 | 52 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P4 | 44 | 3.70 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P4 | 45 | 6.95 | FE | 4 elems FE |
| P4 | 46 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |
| P4 | 47 | 2.15 | FE | 1 elems FE |
| P4 | 48 | 2.35 | FE | 2 elems FE |
| P4 | 49 | 1.68 | LOAD_ONLY | 1 elems de carga (sin rigidez) |

## 5. Las 2 columnas DXF P3-P4 que no llegan a P1

| Nivel | Columnas en rejilla DXF | Columnas FE |
|---|---|---|
| P1 | 16 | 16 |
| P2 | 18 | 16 |
| P3 | 18 | 16 |
| P4 | 18 | 0 |

- Rejillas: P1=16, P2=18, P3=18, P4=18; interseccion soportada = 16.
- Nota tabla: los elementos FE de columna guardan `level` = extremo inferior, por eso P4 muestra 0; hay 16 columnas FE continuas P1->P2 ->P3 -> P4.
- Posiciones de P2 sin base en P1: (X=40, Y=-9.15) y (X=40, Y=-0.25) m. Estado del trazado RLE-PILAR del 101 (P1, y<5100) en esas posiciones CAD:

| Posicion m | CAD (x,y) | Caras H en P1 (long. CAD) | Caras V en P1 (long. CAD) | Votos centro | Columna P1? |
|---|---|---|---|---|---|
| (40.0, -9.15) | (5061,2668) | 4 caras [35.0, 5.0, 5.0, 35.0] | 2 caras [70.0, 70.0] | 0+2 = 2 (se requieren >=3) | NO - seccion incompleta |
| (40.0, -0.25) | (5061,3558) | 3 caras [70.0, 5.0, 35.0] | 2 caras [40.0, 40.0] | 1+0 = 1 (se requieren >=3) | NO - seccion incompleta |

- `group_columns` (`geometric_cleanup.py`) filtra caras de 55-85 CAD y exige **>=3 votos** al centro: cada cara 70 da 1 voto central. En (40,-9.15) el 101 dibuja las 2 caras verticales (70 c/u) **pero el borde superior/inferior esta partido** en trozos de 35/5/5/35 CAD (< 55 -> 0 votos): total 2 votos -> descartado. En (40,-0.25) las verticales miden 40 CAD (< 55, 0 votos) y solo el borde superior (70) vota -> 1 voto: descartado. Por eso la rejilla P1 tiene 16 columnas y el pipeline no genera base continua en esas 2 posiciones.

- DXF 102: P2 (y>=5100) = 18 pilares completos, P3 (y<5100) = 18 pilares completos; tras el corrimiento -20.52 ambas rejillas coinciden -> 18 columnas P2-P3-P4.

**Conclusion:** las 2 columnas en (X=40, Y=-9.15) y (X=40, Y=-0.25) SON completas y reales en P2/P3/P4 (18 pilares), pero en P1 el DXF no cierra su seccion (caras parciales) y el pipeline no emite base; el FE exige columna continua hasta P1, por lo que quedan EXCLUIDAS (politica de `ops_model.py`).

Decision humana requerida: (a) completar la seccion de esos 2 pilares en P1 (2 caras faltantes) y revisar si corresponden estructuralmente, (b) apoyarlas en viga de transferencia desde P2, o (c) mantenerlas fuera y verificar que la estabilidad no dependa de ellas.

## 6. Elementos que sobresalen de la huella de pilares (origen DXF)

- **73 nodos de 46 elementos FE** sobresalen > 0.5 m del rectangulo de pilares soportados del piso. Cada elemento es un miembro DXF high-confidence documentado en `building_3d_aligned.json` (capa + `length_m` + coords), trazado abajo.

| Piso | Tipo | tag FE | nodo | (x,y) m | saliente | origen DXF | L dxf m |
|---|---|---|---|---|---|---|---|
| P1 | beam | 51 | 74 | (33.75,3.33) | 3.57 | 2017_67-101.dxf | 1.52 |
| P1 | beam | 51 | 75 | (35.27,3.33) | 3.57 | 2017_67-101.dxf | 1.52 |
| P1 | beam | 52 | 76 | (38.90,3.33) | 3.57 | 2017_67-101.dxf | 6.35 |
| P1 | beam | 52 | 77 | (45.24,3.33) | 3.57 | 2017_67-101.dxf | 6.35 |
| P1 | beam | 53 | 78 | (33.83,0.35) | 0.60 | 2017_67-101.dxf | 3.05 |
| P1 | beam | 53 | 74 | (33.75,3.33) | 3.57 | 2017_67-101.dxf | 3.05 |
| P1 | wall | 59 | 78 | (33.83,0.35) | 0.60 | 2017_67-101.dxf | 14.90 |
| P1 | wall | 60 | 78 | (33.83,0.35) | 0.60 | 2017_67-101.dxf | 14.90 |
| P1 | wall | 60 | 91 | (38.83,0.35) | 0.60 | 2017_67-101.dxf | 14.90 |
| P1 | wall | 61 | 91 | (38.83,0.35) | 0.60 | 2017_67-101.dxf | 14.90 |
| P1 | wall | 63 | 75 | (35.27,3.33) | 3.57 | 2017_67-101.dxf | 3.63 |
| P1 | wall | 63 | 76 | (38.90,3.33) | 3.57 | 2017_67-101.dxf | 3.63 |
| P1 | wall | 69 | 91 | (38.83,0.35) | 0.60 | 2017_67-101.dxf | 3.05 |
| P1 | wall | 69 | 76 | (38.90,3.33) | 3.57 | 2017_67-101.dxf | 3.05 |
| P2 | beam | 70 | 101 | (10.30,-20.52) | 4.12 | 2017_67-102.dxf | 7.49 |
| P2 | beam | 70 | 102 | (17.49,-20.22) | 3.82 | 2017_67-102.dxf | 7.49 |
| P2 | beam | 71 | 102 | (17.49,-20.22) | 3.82 | 2017_67-102.dxf | 7.49 |
| P2 | beam | 71 | 103 | (17.79,-20.52) | 4.12 | 2017_67-102.dxf | 7.49 |
| P2 | beam | 101 | 121 | (10.00,-20.82) | 4.42 | 2017_67-102.dxf | 4.07 |
| P2 | beam | 101 | 101 | (10.30,-20.52) | 4.12 | 2017_67-102.dxf | 4.07 |
| P2 | beam | 102 | 101 | (10.30,-20.52) | 4.12 | 2017_67-102.dxf | 4.07 |
| P2 | beam | 107 | 102 | (17.49,-20.22) | 3.82 | 2017_67-102.dxf | 3.52 |
| P2 | beam | 109 | 126 | (20.00,-19.01) | 2.61 | 2017_67-102.dxf | 2.31 |
| P2 | beam | 112 | 127 | (25.00,-18.71) | 2.31 | 2017_67-102.dxf | 2.01 |
| P2 | beam | 115 | 131 | (30.00,-18.71) | 2.31 | 2017_67-102.dxf | 1.96 |
| P3 | beam | 133 | 142 | (19.70,-20.52) | 4.12 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 133 | 143 | (20.00,-20.22) | 3.82 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 134 | 143 | (20.00,-20.22) | 3.82 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 134 | 144 | (30.00,-20.82) | 4.42 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 135 | 144 | (30.00,-20.82) | 4.42 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 135 | 145 | (30.30,-20.52) | 4.12 | 2017_67-102.dxf | 10.60 |
| P3 | beam | 136 | 146 | (9.70,-19.01) | 2.61 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 136 | 147 | (10.00,-18.71) | 2.31 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 137 | 147 | (10.00,-18.71) | 2.31 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 137 | 148 | (12.20,-18.71) | 2.31 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 138 | 148 | (12.20,-18.71) | 2.31 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 138 | 149 | (12.50,-19.01) | 2.61 | 2017_67-102.dxf | 2.80 |
| P3 | beam | 148 | 156 | (49.60,-16.40) | 4.60 | 2017_67-102.dxf | 4.25 |
| P3 | beam | 158 | 164 | (49.60,-9.15) | 4.60 | 2017_67-102.dxf | 4.25 |
| P3 | beam | 167 | 168 | (49.60,-0.25) | 4.60 | 2017_67-102.dxf | 4.25 |
| P3 | beam | 171 | 147 | (10.00,-18.71) | 2.31 | 2017_67-102.dxf | 1.96 |
| P3 | beam | 174 | 148 | (12.20,-18.71) | 2.31 | 2017_67-102.dxf | 2.01 |
| P3 | beam | 178 | 143 | (20.00,-20.22) | 3.82 | 2017_67-102.dxf | 3.47 |
| P3 | beam | 183 | 144 | (30.00,-20.82) | 4.42 | 2017_67-102.dxf | 4.12 |
| P3 | beam | 183 | 145 | (30.30,-20.52) | 4.12 | 2017_67-102.dxf | 4.12 |
| P3 | beam | 184 | 145 | (30.30,-20.52) | 4.12 | 2017_67-102.dxf | 4.12 |
| P3 | beam | 193 | 179 | (49.90,-16.70) | 4.90 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 193 | 156 | (49.60,-16.40) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 194 | 156 | (49.60,-16.40) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 194 | 164 | (49.60,-9.15) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 195 | 164 | (49.60,-9.15) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 195 | 168 | (49.60,-0.25) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 196 | 168 | (49.60,-0.25) | 4.60 | 2017_67-102.dxf | 16.75 |
| P3 | beam | 196 | 180 | (49.90,0.05) | 4.90 | 2017_67-102.dxf | 16.75 |
| P4 | beam | 206 | 189 | (19.70,-20.52) | 4.12 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 206 | 190 | (20.00,-20.22) | 3.82 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 207 | 190 | (20.00,-20.22) | 3.82 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 207 | 191 | (30.00,-20.22) | 3.82 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 208 | 191 | (30.00,-20.22) | 3.82 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 208 | 192 | (30.30,-20.52) | 4.12 | 2017_67-103.dxf | 10.60 |
| P4 | beam | 217 | 196 | (49.60,-16.40) | 4.60 | 2017_67-103.dxf | 4.25 |
| P4 | beam | 226 | 203 | (49.60,-9.15) | 4.60 | 2017_67-103.dxf | 4.25 |
| P4 | beam | 235 | 207 | (49.60,-0.25) | 4.60 | 2017_67-103.dxf | 4.25 |
| P4 | beam | 243 | 190 | (20.00,-20.22) | 3.82 | 2017_67-103.dxf | 3.47 |
| P4 | beam | 248 | 191 | (30.00,-20.22) | 3.82 | 2017_67-103.dxf | 3.47 |
| P4 | beam | 257 | 216 | (49.90,-16.70) | 4.90 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 257 | 196 | (49.60,-16.40) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 258 | 196 | (49.60,-16.40) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 258 | 203 | (49.60,-9.15) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 259 | 203 | (49.60,-9.15) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 259 | 207 | (49.60,-0.25) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 260 | 207 | (49.60,-0.25) | 4.60 | 2017_67-103.dxf | 16.75 |
| P4 | beam | 260 | 217 | (49.90,0.05) | 4.90 | 2017_67-103.dxf | 16.75 |

Verificacion en DXF: estos trazos existen como vigas reales (p.ej. banda y=-20.8..-18.7 y borde este x>45 en P2/P3/P4 pertenecen al 102; franja y~3.3 en P1 al 101). Son distancias de diseño (voladizos/fachada), no ruido del FE: `d_max nodo->linea <= 0.5 m` los mantiene sobre su linea DXF de origen.

## 7. Elementos/acciones recomendadas (trazables al DXF)

1. [PIPELINE] En `extract_structure.load_plant`, separar `raw_viga`/`raw_muro`/pilares por ventana ANTES de `group_beams`/`group_walls` (face-width por planta). Efecto medido en 101-P1: 7 -> 39 vigas, 90 -> 26 fragmentos.
2. [MODELO] Tras corregir el grouping, re-evaluar las 43 vigas P1 ambiguous ancladas Y sobre fila de rejilla y las 39 pares nuevas del per-plant; decidir FE/LOAD_ONLY caso a caso.
3. [MODELO] Muros: FE 9, LOAD_ONLY 13, EXCLUIDOS 3 (en P1-P4: P1: 11, 12, 17); 25 muros hi trazados; 51 muros ambiguous excluidos por politica hasta validacion.
4. [ESTRUCTURA] Las 2 columnas P2-P4 (X=40) sin base en P1 requieren decision humana (fundir en P1, transfer, o excluir). No se toca el modelo.
5. [GEOMETRIA] Los 46 elementos sobresalientes son DXF reales; se conservan tal cual. Nada que eliminar.
6. [S1/FDN] No modelados (base fija en P1, 16 apoyos); fuera del alcance de esta auditoria.

Todo lo anterior queda SIN MODIFICAR a la espera de revision humana. No se reincorporan elementos automaticamente ni se tocan cargas/areas tributarias/Unity.

## Archivos generados

- `results/audit_P1_muros_semana2.md`
- `figures/audit_P1_vigas.png`
- `figures/audit_muros_P1.png`
- `figures/audit_muros_P2.png`
- `figures/audit_muros_P3.png`
- `figures/audit_muros_P4.png`