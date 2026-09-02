# Auditoria de Geometria Final - Semana 2 (P1-P4)

- Fecha: 2026-09-01  |  Estado: **SIN MODIFICAR** modelo FE, unity_model.json, cargas, q_G ni areas tributarias.
- Fuente A (DXF procesado): `data/processed/building_3d_aligned.json`
- Fuente B (modelo FE/visual): `data/processed/unity_model.json`
- Corrimiento de registro aplicado en memoria (igual que `ops_model.load_aligned`): P3/P4 -> Y -20.52 m.
- Trazabilidad FE->DXF: `physical_id` (= indice `orig` de `build_ops_model`); columnas FE por geometria.
- Nota metodologica: la cobertura usa la proyeccion de nodos FE sobre la linea DXF; `LFE` puede superar `LDXF` porque los nodos soldados a pilares (snap <= 0.5 m) forman cuerdas ligeramente mas largas que el trazo.

**Elementos FE totales:** 241  |  columnas 48  |  vigas FE 175  |  muros FE 18  |  LOAD_ONLY 16  |  nodos 187  |  apoyos 16

## Resumen por piso

| Piso | Viga hi DXF | Viga FE (elem) | Viga phys FE | Viga LOAD | Viga excl. | Viga ambig. | Muro hi DXF | Muro FE (elem) | Muro phys FE | Muro LOAD | Muro excl. | Muro ambig. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 7 | 3 | 3 | 2 | 2 | 90 | 11 | 7 | 4 | 4 | 3 | 27 |
| P2 | 45 | 53 | 44 | 1 | 0 | 13 | 4 | 2 | 1 | 3 | 0 | 9 |
| P3 | 49 | 64 | 49 | 0 | 0 | 12 | 4 | 2 | 1 | 3 | 0 | 9 |
| P4 | 44 | 55 | 44 | 0 | 0 | 15 | 6 | 7 | 3 | 3 | 0 | 6 |

## Coincidencia geometrica FE vs DXF (elementos incorporados)

Para cada miembro DXF high-confidence incorporado se midio: (a) distancia maxima nodo-FE -> linea DXF (`d_max`), (b) cobertura de la longitud fuente por los elementos FE.

- d_max global (todos los pisos, todos los elementos FE): **0.4750 m** <= NODE_SNAP_TOL=0.5 OK
- **P1** vigas: cobertura 99.3% (LFE=10.84 / LDXF=10.91 m) | muros: cobertura 99.7% (LFE=29.08 / LDXF=28.13 m)
- **P2** vigas: cobertura 100.0% (LFE=296.93 / LDXF=276.61 m) | muros: cobertura 100.0% (LFE=6.96 / LDXF=6.95 m)
- **P3** vigas: cobertura 100.0% (LFE=337.51 / LDXF=315.86 m) | muros: cobertura 100.0% (LFE=6.96 / LDXF=6.95 m)
- **P4** vigas: cobertura 100.0% (LFE=324.15 / LDXF=302.89 m) | muros: cobertura 100.0% (LFE=11.59 / LDXF=11.45 m)

- Sin mismatches geometricos (> 0.5 m) entre FE y sus fuentes DXF de alta confianza.

## Columnas: continuidad P1->P2 / P2->P3 / P3->P4

| Par | Columnas DXF | Columnas FE | Coinciden | FE sin par DXF (reconstruidas) | DXF sin par FE (no modeladas) |
|---|---|---|---|---|---|
| P1->P2 | 16 | 16 | 16 | 0 | 0 |
| P2->P3 | 0 | 16 | - (reconstruccion) | 0 | 0 |
| P3->P4 | 18 | 16 | 16 | 0 | 2 |

- Rejilla soportada continua P1..P4: **16 pilares**; presente en todos los pisos: SI  (P1=16, P2=16, P3=16, P4=16).
- Continuidad entre pares de FE: P1->P2 con P2->P3: 16/16; P2->P3 con P3->P4: 16/16.
- P2-P3 y P3-P4 son reconstruccion por coincidencia de rejilla (el DXF solo registra P1-P2 y P3-P4).
- DXF registra P3-P4 = 18 columnas; FE modela 16 (las 2 de P2 x=40 sin pilar en P1 quedan fuera, documentado en `ops_model.py`: columna sin base continua se EXCLUYE).

## Muros: FE / LOAD_ONLY / EXCLUIDOS

| Piso | hi DXF | FE (phys) | LOAD_ONLY | Excluidos (hi, sin carga) | Ambiguous (no modelados) |
|---|---|---|---|---|---|
| P1 | 11 | 4 | 4 | 3 | 27 |
| P2 | 4 | 1 | 3 | 0 | 9 |
| P3 | 4 | 1 | 3 | 0 | 9 |
| P4 | 6 | 3 | 3 | 0 | 6 |

- Excluidos high-confidence (politica v2: sin pilar soportado a <= 8.0 m): P1-4; P1-5; P1-11; P1-12; P1-17.

## Vigas/elementos que sobresalen de la huella de pilares

**73 nodos de 46 elementos** FE quedan a mas de 0.5 m del rectangulo que encierran los pilares soportados (22 en eje X -borde este x>45-, 51 en eje Y -bandas y=-20.8..-18.7 y y=0.3..3.3-). Son parte de los miembros DXF high-confidence incorporados (no artefactos del FE): d_max <= 0.475 m los mantiene sobre su linea.

| Piso | Tipo | tag FE | nodo | (x,y) m | saliente m | eje |
|---|---|---|---|---|---|---|
| P1 | beam | 51 | 74 | (33.75, 3.33) | 3.58 | y |
| P1 | beam | 51 | 75 | (35.27, 3.33) | 3.58 | y |
| P1 | beam | 52 | 76 | (38.90, 3.33) | 3.58 | y |
| P1 | beam | 52 | 77 | (45.24, 3.33) | 3.58 | y |
| P1 | beam | 53 | 78 | (33.83, 0.35) | 0.60 | y |
| P1 | beam | 53 | 74 | (33.75, 3.33) | 3.58 | y |
| P1 | wall | 59 | 78 | (33.83, 0.35) | 0.60 | y |
| P1 | wall | 60 | 78 | (33.83, 0.35) | 0.60 | y |
| P1 | wall | 60 | 91 | (38.83, 0.35) | 0.60 | y |
| P1 | wall | 61 | 91 | (38.83, 0.35) | 0.60 | y |
| P1 | wall | 63 | 75 | (35.27, 3.33) | 3.58 | y |
| P1 | wall | 63 | 76 | (38.90, 3.33) | 3.58 | y |
| P1 | wall | 69 | 91 | (38.83, 0.35) | 0.60 | y |
| P1 | wall | 69 | 76 | (38.90, 3.33) | 3.58 | y |
| P2 | beam | 70 | 101 | (10.30, -20.52) | 4.12 | y |
| P2 | beam | 70 | 102 | (17.49, -20.22) | 3.82 | y |
| P2 | beam | 71 | 102 | (17.49, -20.22) | 3.82 | y |
| P2 | beam | 71 | 103 | (17.79, -20.52) | 4.12 | y |
| P2 | beam | 101 | 121 | (10.00, -20.82) | 4.42 | y |
| P2 | beam | 101 | 101 | (10.30, -20.52) | 4.12 | y |
| P2 | beam | 102 | 101 | (10.30, -20.52) | 4.12 | y |
| P2 | beam | 107 | 102 | (17.49, -20.22) | 3.82 | y |
| P2 | beam | 109 | 126 | (20.00, -19.01) | 2.61 | y |
| P2 | beam | 112 | 127 | (25.00, -18.71) | 2.31 | y |
| P2 | beam | 115 | 131 | (30.00, -18.71) | 2.31 | y |
| P3 | beam | 133 | 142 | (19.70, -20.52) | 4.12 | y |
| P3 | beam | 133 | 143 | (20.00, -20.22) | 3.82 | y |
| P3 | beam | 134 | 143 | (20.00, -20.22) | 3.82 | y |
| P3 | beam | 134 | 144 | (30.00, -20.82) | 4.42 | y |
| P3 | beam | 135 | 144 | (30.00, -20.82) | 4.42 | y |
| P3 | beam | 135 | 145 | (30.30, -20.52) | 4.12 | y |
| P3 | beam | 136 | 146 | (9.70, -19.01) | 2.61 | y |
| P3 | beam | 136 | 147 | (10.00, -18.71) | 2.31 | y |
| P3 | beam | 137 | 147 | (10.00, -18.71) | 2.31 | y |
| P3 | beam | 137 | 148 | (12.20, -18.71) | 2.31 | y |
| P3 | beam | 138 | 148 | (12.20, -18.71) | 2.31 | y |
| P3 | beam | 138 | 149 | (12.50, -19.01) | 2.61 | y |
| P3 | beam | 148 | 156 | (49.60, -16.40) | 4.60 | x |
| P3 | beam | 158 | 164 | (49.60, -9.15) | 4.60 | x |
| P3 | beam | 167 | 168 | (49.60, -0.25) | 4.60 | x |
| P3 | beam | 171 | 147 | (10.00, -18.71) | 2.31 | y |
| P3 | beam | 174 | 148 | (12.20, -18.71) | 2.31 | y |
| P3 | beam | 178 | 143 | (20.00, -20.22) | 3.82 | y |
| P3 | beam | 183 | 144 | (30.00, -20.82) | 4.42 | y |
| P3 | beam | 183 | 145 | (30.30, -20.52) | 4.12 | y |
| P3 | beam | 184 | 145 | (30.30, -20.52) | 4.12 | y |
| P3 | beam | 193 | 179 | (49.90, -16.70) | 4.90 | x |
| P3 | beam | 193 | 156 | (49.60, -16.40) | 4.60 | x |
| P3 | beam | 194 | 156 | (49.60, -16.40) | 4.60 | x |
| P3 | beam | 194 | 164 | (49.60, -9.15) | 4.60 | x |
| P3 | beam | 195 | 164 | (49.60, -9.15) | 4.60 | x |
| P3 | beam | 195 | 168 | (49.60, -0.25) | 4.60 | x |
| P3 | beam | 196 | 168 | (49.60, -0.25) | 4.60 | x |
| P3 | beam | 196 | 180 | (49.90, 0.05) | 4.90 | x |
| P4 | beam | 206 | 189 | (19.70, -20.52) | 4.12 | y |
| P4 | beam | 206 | 190 | (20.00, -20.22) | 3.82 | y |
| P4 | beam | 207 | 190 | (20.00, -20.22) | 3.82 | y |
| P4 | beam | 207 | 191 | (30.00, -20.22) | 3.82 | y |
| P4 | beam | 208 | 191 | (30.00, -20.22) | 3.82 | y |
| P4 | beam | 208 | 192 | (30.30, -20.52) | 4.12 | y |
| P4 | beam | 217 | 196 | (49.60, -16.40) | 4.60 | x |
| P4 | beam | 226 | 203 | (49.60, -9.15) | 4.60 | x |
| P4 | beam | 235 | 207 | (49.60, -0.25) | 4.60 | x |
| P4 | beam | 243 | 190 | (20.00, -20.22) | 3.82 | y |
| P4 | beam | 248 | 191 | (30.00, -20.22) | 3.82 | y |
| P4 | beam | 257 | 216 | (49.90, -16.70) | 4.90 | x |
| P4 | beam | 257 | 196 | (49.60, -16.40) | 4.60 | x |
| P4 | beam | 258 | 196 | (49.60, -16.40) | 4.60 | x |
| P4 | beam | 258 | 203 | (49.60, -9.15) | 4.60 | x |
| P4 | beam | 259 | 203 | (49.60, -9.15) | 4.60 | x |
| P4 | beam | 259 | 207 | (49.60, -0.25) | 4.60 | x |
| P4 | beam | 260 | 207 | (49.60, -0.25) | 4.60 | x |
| P4 | beam | 260 | 217 | (49.90, 0.05) | 4.90 | x |

Nota: un voladizo/antear por encima del eje X>45 (p.ej. vierteaguas o balcon) seria coherente, pero las bandas Y por debajo de -16.4 y por encima de -0.25 sin fila de pilares cercanos merecen revision manual contra los DXF 101/102.

## S1 (subsuelo) y fundaciones

- El modelo FE/Unity es de **superestructura P1..P4**: S1 (z=-4.01 m) y FDN (sin elevacion) **no se modelan** (`frame_levels=('P1','P2','P3','P4')`); la base se fija en P1 (16 apoyos fijos).
- DXF S1 -> vigas hi 21 + ambiguous 17; muros hi 12 + ambiguous 42.
- DXF FDN -> vigas hi 18 + ambiguous 5; muros hi 21 + ambiguous 95.
- No hay elementos FE en S1/FDN (confirmado: 0 en `unity_model.json`).

## Checks automaticos

- [PASS] elementTag unicos: 0 duplicados
- [PASS] longitud cero: 0 elementos
- [PASS] z de nodos FE de viga/muro == elevacion del piso: 0 anomalias
- [PASS] d_max nodo->linea DXF <= 0.5 m: 0.4750 m
- [PASS] todos los nodos FE conectados a base P1: 0 nodos aislados
- [PASS] nodos FE de viga/muro con pilar soportado a <= 8 m: 0 nodos sin apoyo (ej: [])
- [PASS] elementos FE exportados sin fuente (por diseno): 0 con source_dxf/source_id
- [PASS] columnas FE P1-P2 coinciden con DXF P1-P2: M=16/16
- [PASS] continuidad de 16 pilares P1..P4: rejillas iguales=True, P1P2->P2P3 16/16, P2P3->P3P4 16/16
- [PASS] rango de coordenadas en metros: x[-0.35,49.90] y[-20.82,3.33] z[-0.05,11.83]

- [WARNING] elementos LOAD_ONLY presentes (16): solo carga, sin rigidez
- [WARNING] vigas/muros 'ambiguous' excluidos por politica: 130/51 en P1-P4
- [WARNING] 2 columnas DXF P3-P4 sin modelo (P2 x=40 sin base continua en P1)
- [WARNING] S1 y FDN no modelados; base fija en P1 (16 apoyos)
- [WARNING] 73 puntos FE sobresalen > 0.5 m de la huella de pilares

## VEREDICTO DE GEOMETRIA: WARNING (con advertencias documentadas)

- Advertencias documentadas: 5.
- La geometria FE (nodos, longitudes, topologia) coincide con los miembros DXF high-confidence incorporados dentro de tolerancia; las diferencias reportadas son de POLITICA (exclusiones ambiguous, weak-base, S1/FDN, LOAD_ONLY) y quedan registradas sin corregir.

## Archivos nuevos de esta auditoria

- `results/qa_geometria_semana2.md`
- `figures/qa_geometria_P1.png`
- `figures/qa_geometria_P2.png`
- `figures/qa_geometria_P3.png`
- `figures/qa_geometria_P4.png`

## Siguiente paso

Revision humana de este reporte y de las imagenes de planta (el modelo no puede inspeccionar PNG). No se corrige nada por decision propia del asistente.