# Digitalización de V.I./+V.I. en ROOF — Estado intermedio

Fecha: 2026-08-30 (auditoría) · 2026-09 (implementación §9: VI-01..07 → IMPLEMENTADO_GEOMETRIA). Historial de auditoría preservado (§8). VIII-VI-08..10 permanecen PENDIENTE_VERIFICACION y NO están en el modelo.

## 1. Lo que quedó objetivamente establecido

### 1.1 Transformación de la planta ROOF (lám. 102, dibujo superior, escala 1:50)
- Escala verificada: **118.1 px/m** (150 dpi) ⇔ **56.7 pt/m** (1:50).
- Burbujas de ejes leídas (OCR de burbuja + círculos): `A'`(eje 0.00) → `A`→`B`→`C` confirmadas.
- Transformación X: `x_m = (px_x − 1098) / 118.1`  (check: A=3.75, B=11.20, C=21.29 m ✓).
- Origen Y **DOBLE-VALIDADO**: `y_m = (pt_y − 999.1) / 56.7` con `pt_y = 2384 − px_y/2.0833`.
  - Burbuja de dígitos `1A` (círculo px 656.6, 2381.4) → y = **4.265 m exacto** (Δ0.03 m, tolerancia del marcado).
  - Rótulo de columna `70x70` junto al eje D (px≈4765, 1807) → y≈9.1-9.2 m, coherente con fila 2 (8.9 m).
  - Cadena de cotas del borde izquierdo: 426.5 / 463.5 / 298.5 / 426.5 cm = grid_y **4.265 / 4.635 / 2.985 / 4.265** ✓.
  - La lectura `2A` (px 623, 2139) se **DESCARTA**: su py es incompatible con y=11.885 m bajo este sistema; pertenece a otro dibujo de la lámina.

### 1.2 Rótulos V.I./+V.I. por lámina (posiciones exactas px → pt → x_m)
| Lámina | Etiqueta | px (x,y) | pt (x, pdf_y) | x_m (m) | Nivel / Nota |
|---|---|---|---|---|---|
| 102 | +V.I. 15/76 (2ª ETAPA) | — | — | 13.6..15.5 | banda CENTRO y≈7.92, encima del tramo E (y 8.5..9.3) |
| 102 | +V.I. 15/76 (2ª ETAPA) | — | — | 18.4..19.6 | banda CENTRO, encima de la extensión E (y≈9.3) |
| 102 | +V.I. 15/70 (2ª ETAPA) | — | — | 10.6..11.8 | banda CENTRO y≈7.92 (y≈7.67) |
| 102 | +V.I. 15/70 (2ª ETAPA) | — | — | 26.6..27.9 | banda CENTRO, zona D (y≈7.2) |
| 102 | +V.I. 15/VAR (2ª ETAPA) | — | — | 8.9..8.94 | banda CENTRO y≈7.92 (y≈8.45) |
| 102 | +V.I. 15/VAR (2ª ETAPA) | — | — | 28.5..28.6 | banda CENTRO, zona D (y≈8.5) |
| 102 | **+V.I. 20/90** | — | — | **0.54** | **y≈5.94 OESTE, zona escalera/M.H.A. — único rótulo 20/90 del plano** |
| 102 | +V.I. 15/76 (2ª ETAPA) | — | — | 1.0..2.2 | y≈6.6 y y≈9.7 (borde oeste x≈1.0) |
| 102 | +V.I. 15/76 (2ª ETAPA) | — | — | 14.8 | banda SUR y≈3.52 |
| 102 | +V.I. 15/76 (2ª ETAPA) | — | — | 18.9 | banda SUR y≈3.52 |
| 102 | +V.I. 15/76 ó 15/68 (AMBIGUO) | — | — | 27.1..28.0 | banda SUR y≈3.05 (junto eje D) |
| 102 | etiqueta sin cuerpo (¿15/76? cola "(2ª ETAPA)") | — | — | 8.9 | banda SUR y≈3.4–3.7 (cuerpo sin leer) |
| 301 | +V.I. 15/70 | (4384,1922) · (2353,1929) | — | — | elevación eje 2 |
> **Corrección importante (censo OCR multi-pase, 2026-08-30):** los rótulos antes leídos como `+V.I.20/90` en la banda central NO son `20/90`: la banda y≈7.92 lleva `+V.I.15/76`, `+V.I.15/70` y `+V.I.15/VAR` (todas «2ª ETAPA») en las posiciones de la tabla. El único rótulo `+V.I.20/90` detectado en todo el plano 102 está al **OESTE** (xm≈0.54, y≈5.94, zona escalera al pie del muro M.H.A.). Los dígitos 6/7/9 y 0/8 son confusos en OCR → confirmar visualmente sobre `vi_c0_banda_centro_oeste.png` y `vi_map_rotulos.png` (§8.4).
| 302 | +V.I. 20/90 | (646,1947),(1304,1948),(2426,1947),(3615,1947) | — | — | elevaciones ejes 3/8/8A |
| 303 | +V.I. 20/90 | (1881,1841) | — | — | elevación A/A' |
| 305 | +V.I. 15/76; V.I. | (1749,1350);(6001,1295) | — | — | elevaciones C y D-D' |
| 400 | V.I. 15/24 | (6332,3484) | — | — | detalle de viga |
| 400 | +V.I. 15/VAR | (3668,4292),(3188,4295) | — | — | detalle de refuerzo |

### 1.3 Relación con el modelo actual (beams_LT2.csv, ROOF = 46 vigas V60x80/V30x80/V40x80)
- Ninguna sección V.I./+V.I. existe en el modelo.
- Las V.I. de ROOF son **adicionales** (o **sustituyen** líneas de viga existentes) — aún no distinguible por tramo sin extremos confirmados.
- 2ª ETAPA confirmada visualmente para: `+V.I. 15/70`, `+V.I. 15/68`, `+V.I. 15/76`, `V.I. 15/VAR` (todas las secciones del perímetro del hueco; §8.0). `+V.I. 20/90` (oeste) sin «2ª ETAPA» visible. Secciones confirmadas: VI15×70, VI15×68, VI15×76, VI15×VAR (altura variable), VI20×90.

### 1.4 Detalle 400
- `V.I. 15/24` (detalle 6332,3484) y `+V.I. 15/VAR` (3668,4292/3188,4295): confirmadas su existencia; el significado exacto de **VAR** y modelabilidad prismática **pendientes** (requiere leer el detalle completo).

## 2. Bloqueo que impide completar extremos (x1,y1,x2,y2) con CONFIANZA
- Los rótulos `+V.I. 20/90` de 102 están en la banda y≈1920px de la **zona de escalera** del plano ROOF. El rectángulo vectorial hallado junto al rótulo (2698,1920) mide **~0.6 m** de ancho transversal — incongruente con `V.I. e=20` (esperable 0.20 m) y cae en `y_m≈7.9 m` (fuera de ejes de columnas). Puede tratarse de un muro/linea de escalera, no de la viga.
- Consecuencia: **no se pueden fijar extremos ni clasificar adicional/sustituye por tramo sin validación visual** del plano 102 (zona escalera) y su relación planta-elevación (301/302/303/305).

## 3. Estado de confianza por celda
*(\[superado por §8 / §8.2\]: la banda y≈7.92 es borde N del hueco = 15/70, no 20/90; la banda norte 12.90 NO es V.I.)*
| Celda | Estado |
|---|---|
| etiqueta / sección / 2ª etapa / fuentes | **CONFIRMADO** (OCR + detalle 400) |
| nivel (ROOF) | **CONFIRMADO** (burbujas + rótulos elevación) |
| orientación | **CONFIRMADO** (bandas horizontales vectoriales en 102; y transform validada §1.1) |
| x1,y1,x2,y2 | **PENDIENTE_VERIFICACION** (y real=7.92 y hueco §7; extremos a confirmar con plano e elevación) |
| relación_con_modelo_actual | **PENDIENTE** (candidata ADICIONAL para y=7.92 / banda norte; SIN confirmar) |
| ¿seguro implementar? | **NO** hasta validación visual |

## 4. Próximo paso a decidir con el usuario
- (a) Que un humano valide visualmente la zona escalera del plano 102 e indique el tramo de cada rótulo (rápido y seguro).
- (b) Continuar extracción vectorial viga por viga (costosa, riesgo de error de asociación rótulo→viga).
- (c) Otra lámina/elevación (302/303) que permita fijar extremos con burbujas de ejes ya leídas.

## 5. Kit de validación visual (recortes de alta resolución)
**Decisión tomada: validación visual humana primero.** Recortes generados en `C:\Users\natig\AppData\Local\Temp\opencode\lt2_audit\`:

| Recorte | Contenido | Para validar |
|---|---|---|
| `crop_102_banda_20-90.png` (5089×327) | banda de rótulos **+V.I.20/90** (x px 1550–4200, y 1870–2040) | tramo que abarca cada rótulo (qué ejes/columnas toca); 5 rótulos a imagen-x ≈ 892, 2268, 4592, 7004, 9244 |
| `crop_102_pasadas2.png` | franja de pasadas/escalones bajo la banda | relación viga–escalera (¿borde de vacío de escalera?) |
| `crop_102_15-76_var.png` | rótulos **+V.I.15/76 (2ª ETAPA)** y **V.I.15/VAR (2ª ETAPA)** (y≈2470–2520) | tramos de estas 3 vigas |
| `crop_102_15-76_low.png` | rótulos +V.I.15/76 y refs bajas (y≈2190–2320) | refuerzos/detalles asociados |
| `crop_102_escalera_full.png` | contexto completo zona escalera (x 1500–4400, y 1880–2620) | visión general |
| `crop_102_detalle_viga_2etapa.png` | detalle +V.I. 2ª ETAPA (ESCALA 1:20) arriba-derecha | sección y significado de VAR |
| `crop_301_banda15-70.png`, `crop_302_banda20-90.png`, `crop_303_banda20-90.png`, `crop_305_banda15-76.png`, `crop_305_VLI.png` | elevaciones 301/302/303/305 con rótulos V.I. | cruce planta–elevación (tramos y niveles) |

**Transformación final (lám. 102, escala 1:50, ver §1.1 y §7.0):** `x_m = (px_x − 1098)/118.1` ⇔ `x_m = (pt_x − 526.6)/56.7`; `y_m = (pt_y − 999.1)/56.7` con `pt_y = 2384 − px_y/2.0833`. (Burbujas validadas: A'=0, A=3.75, B=11.25, C=21.25 m; '1A'=4.265 m.)

## 6. Tabla candidata v1 (interpretación visual aplicada; SIN modificar modelo)

> **⚠ SUPERSEDIDA por la validación visual §8.0 (2026-08-30).** Las secciones 6 y 7 recogen la hipótesis **anterior** que etiquetaba la banda central y≈7.92 como `+V.I.20/90`. Dicha hipótesis fue **DESCARTADA**: la banda y≈7.92 es el **borde norte del hueco de escalera = `+V.I.15/70` (2ªETAPA)**; el borde sur = `+V.I.15/68`; bordes verticales = `15/VAR` (oeste) y `15/76` (este). El inventario VIGENTE está en **§8.2** (tabla VI-01..VI-10) y §8.3.

### 6.0 Lo que extrajeron las líneas vectoriales reales (lám. 102, planta ROOF)
- **Línea candidata +V.I.20/90** (banda y_px≈1914–1984, pt y≈1431–1465): doble línea sólida en `xm 1.0..7.6` y `xm 8.2..16.5` + línea de centro discontinua `xm −0.2..17.8` con marca cada **3.75 m** (periodicidad exacta, offset sistemático **−0.58 m** vs. grilla de burbujas A/B/C; los huecos NO coinciden con columnas/nodos a <0.1 m). Rótulos a `xm 5.72, 8.63, 13.55, 18.65, 23.39` → prolongación de la línea al este (hasta ~D).
- **Línea candidata (banda norte, pt y≈1732):** segmentos `xm −0.2..21.3`, misma periodicidad; «franja estructural horizontal» paralela al borde superior, consistente con la interpretación visual.
- Rótulos `+V.I.15/76 (2ª ETAPA)` a `xm 13.79 / 17.90`, `V.I.15/VAR (2ª ETAPA)` a `xm 8.76` (perímetro del hueco de escalera; tramos H/V a digitalizar por separado).

### 6.1 +V.I. 20/90 — línea continua, cortes en columnas/nodos
Hipótesis de fila: coincide con una franja estructural horizontal del plano; la fila exacta (1/2/3) **PENDIENTE** (origen Y no doblemente anclado). Coordenadas X: escala y origen de burbujas A/B/C **CONFIRMADO**, pero los extremos dibujados **NO** coinciden con nodos/grid a <0.1 m → **PENDIENTE_VERIFICACION** en x1,x2. Niveles: ROOF (cruce 302/303).

| temp_id | etiqueta | orientación | eje/línea | nodo inicial | nodo final | x1 | y1 | x2 | y2 | relación con viga convencional |
|---|---|---|---|---|---|---|---|---|---|---|
| C-VI20-01 | +V.I. 20/90 | Horizontal (E-O) | franja est. horizontal | col 0.4/1.85-A | A | 0.40 | * | 3.75 | * | **REEMPLAZA** si coincide c/V60x80 de esa fila (ver 6.2) |
| C-VI20-02 | +V.I. 20/90 | Horizontal (E-O) | ídem | A | nodo 7.5 | 3.75 | * | 7.50 | * | **REEMPLAZA** (coincide con ROOF_V0xx en esa fila) |
| C-VI20-03 | +V.I. 20/90 | Horizontal (E-O) | ídem | nodo 7.5 | B | 7.50 | * | 11.25 | * | **REEMPLAZA** |
| C-VI20-04 | +V.I. 20/90 | Horizontal (E-O) | ídem | B | nodo 16.25 | 11.25 | * | 16.25 | * | **REEMPLAZA** (coincide ROOF_BD_V60_0x fila 2) |
| C-VI20-05 | +V.I. 20/90 | Horizontal (E-O) | ídem | nodo 16.25 | C | 16.25 | * | 21.25 | * | **REEMPLAZA** |
| C-VI20-06 | +V.I. 20/90 | Horizontal (E-O) | ídem | C | nodo 26.25 | 21.25 | * | 26.25 | * | **REEMPLAZA** |
| C-VI20-07 | +V.I. 20/90 | Horizontal (E-O) | ídem | nodo 26.25 | D | 26.25 | * | 31.25 | * | **REEMPLAZA** |

`*` = y pendiente de confirmar (la fila). **PENDIENTE_VERIFICACION** en x1,x2 (los extremos dibujados no caen sobre nodos/grid a <0.1 m; el offset sistemático −0.58 m y el extremo oeste ·1.0 vs 0.4/1.85· impiden CONFIRMADO_GEOMETRIA). y1,y2 pendientes (fila).

### 6.2 Relación con vigas convencionales del modelo (ROOF, beams_LT2.csv)
Las 46 vigas ROOF en filas y=0/8.9/16.15 incluyen tramos horizontales `[3.75–7.5]`, `[7.5–11.25]` (V0xx) y `[11.25–16.25]`, `[16.25–21.25]`, `[21.25–26.25]`, `[26.25–31.25]` (BD_V60_0x). Si la V.I.20/90 se ubica en alguna de esas filas → **COINCIDENTE → REEMPLAZA** (cambiar sección a V.I.20/90 en esos tramos). Si la fila no tuviera viga convencional → **ADICIONAL**. Fila objetivo aún PENDIENTE.

### 6.3 +V.I. 15/76 (2ª ETAPA) y V.I. 15/VAR (2ª ETAPA) — perímetro hueco de escalera
Reconocidas a `xm 13.79 / 17.90` y `xm 8.76` (lám. 102) + elev. 305. **PENDIENTE_VERIFICACION** para extremos: requiere delimitar el rectángulo del hueco con líneas vectoriales del dibujo (tramos H y V por separado, cortados en cada intersección estructural). No se entrega aún en tabla hasta confirmar el perímetro del hueco.

### 6.4 Notas de confianza
- **CONFIRMADO**: existencia de la línea +V.I.20/90 en 102 (franja estructural horizontal), rótulos, escala 1:50, origen X (burbujas A'/A/B/C), nivel ROOF (cruce 302/303), secciones V.I.15/76 y V.I.15/VAR (2ª ETAPA).
- **PENDIENTE_VERIFICACION**: fila (y) de la V.I.20/90; extremos x1,x2 (offset −0.58 m y bordes oeste/este sin nodo inequívoco); perímetro del hueco de escalera (tramos H/V de las 15/76); significado de **VAR** (detalle 400).
- **VAR** (V.I.15/VAR): no se convierte en altura fija aún.
- NO implementar todavía. Sin cambios en CSVs/código; sin commit.

## 7. Resultados con transformación Y validada (extracción vectorial; todo PENDIENTE_VERIFICACION)

### 7.0 Transformación final (lám. 102, planta ROOF)
- `x_m = (pt_x − 526.6)/56.7`, `pt_x = px_x/2.08333` (burbujas A'=0, A=3.75, B=11.25, C=21.25 m ✓).
- `y_m = (pt_y − 999.1)/56.7`, `pt_y = 2384 − px_y/2.08333` (validado en §1.1).
- Banda centro (y≈7.92) = **borde norte del hueco de escalera**, rotulado `+V.I.15/70 (2ªETAPA)` (§8.0). Banda sur (y≈2.90) = borde sur, rotulado `+V.I.15/68 (2ªETAPA)`. Bordes verticales: `+V.I.15/VAR` (oeste) y `+V.I.15/76` (este). La banda norte (y≈12.90) NO es V.I. (N.S.P.12.29 + V.60×80).

### 7.1 Hueco / perímetro de la zona de escalera — bordes candidatos
Los vectores en la franja y_m 1.07..9.19 cierran dos rectángulos sólidos e=0.60 m en y **2.62..3.22** (x **1.05..7.60** y x **8.30..16.49**; abertura 7.60..8.30 en la que corre una línea vertical continua x≈7.95) y el cinturón +V.I.20/90 (dobles líneas) en y **7.62..8.22** (x 1.00..16.55).

| borde | orientación | coordenada | desde | hasta | fuente | confianza |
|---|---|---|---|---|---|---|
| Sur | Horizontal | y = 2.92 (2.62..3.22, e=0.60 m) | x = 1.05 | x = 16.49 | 2 rect cerrados vectoriales; rótulos 15/76 y 15/VAR a y 3.39 sobre la banda | PENDIENTE_VERIFICACION |
| Norte | Horizontal | y = 7.92 (7.62..8.22, e=0.60 m; banda 20/90) | x = 1.00 | x = 16.55 | dobles polilíneas sólidas + rótulo M.H.A. | PENDIENTE_VERIFICACION |
| Oeste | Vertical | x ≈ 1.05 | y = 2.62 | indeterminado (verticales 0.35/0.40/0.55/0.70/1.00 cortadas en segmentos) | verticales seccionadas | PENDIENTE_VERIFICACION |
| Este | Vertical | x = 16.55 (rect termina 16.49) | y = 3.27 | y = 7.62 | vertical larga (246.7 pt) + esquina con franja sur. Alternativa: vertical continua x=18.00 (y 1.07..9.19) al este del rótulo 15/76 | PENDIENTE_VERIFICACION |

### 7.2 V.I. → borde del hueco (tramos H/V por separado)
| V.I. | borde del hueco asociado | extremos candidatos | sección | confianza |
|---|---|---|---|---|
| +V.I. 15/76 (2ª ETAPA) @ xm 13.79 | Sur (y=2.92), rect 8.30..16.49 | [x ≈ 7.95 .. 16.49] (col x≈7.95 → esquina este) | 15×76 | PENDIENTE_VERIFICACION |
| +V.I. 15/76 (2ª ETAPA) @ xm 17.90 | Este (x≈16.55 ó 18.00) — tramo vertical | [y ≈ 3.3 .. 7.6] | 15×76 | PENDIENTE_VERIFICACION |
| V.I. 15/VAR (2ª ETAPA) @ xm 8.76 | Sur (y=2.92), rect 8.30..16.49 | [x ≈ 7.95 .. 16.49] (sobre el mismo rect) | 15×VAR (altura según detalle 400) | PENDIENTE_VERIFICACION |

### 7.3 +V.I. 20/90 — línea longitudinal real  *(SUPERSEDIDO por §8.0: la banda central es el borde N del hueco = 15/70; ver §8.2 para el inventario vigente)*
- La banda de doble línea sólida (y 7.62 / 8.22) y su centro discontinuo (y 7.92) delimitan la franja estructural → **y real = 7.92 m** (constante). **NO** cae sobre ejes de columnas.

| línea candidata | y_real | eje más cercano | offset al eje | x_inicio | x_fin | intersecciones reales | confianza |
|---|---|---|---|---|---|---|---|
| Franja sólida 1 (doble línea) | 7.92 | eje 2 (y=8.9) | **−0.98 m** | 1.00 | 7.65 | verticales cortadas en x 1.00 y 7.65 | PENDIENTE_VERIFICACION |
| Franja sólida 2 (doble línea) | 7.92 | eje 2 (y=8.9) | **−0.98 m** | 8.25 | 16.55 | verticales x 8.25 y 16.55 (y 3.27..7.62); columna vertical x≈7.95 en el gap | PENDIENTE_VERIFICACION |
| Prolongación discontinua (marcas) | 7.92 | eje 2 | −0.98 m | −0.2 | 20.8 | marcas 3.75 m = anotaciones auxiliares (NO usar) | PENDIENTE_VERIFICACION |

- **Uno o varios tramos:** al menos **2 tramos sólidos independientes** [1.00..7.65] y [8.25..16.55], separados 0.60 m (abertura x 7.65..8.25 con línea vertical en x≈7.95), más prolongación discontinua al oeste (−0.2) y este (20.8). Existe también una banda norte paralela en y≈12.9 (pt 1732), etiquetada y relación pendientes.
- **Relación con el modelo:** en y=7.92 **no existe viga convencional** (filas 0/8.9/16.15 y V30x80 en 4.265/11.885) → si se confirma esta geometría, los tramos de la V.I.20/90 son **ADICIONALES** (no REEMPLAZAN), con nodos nuevos en 1.00 / 7.65 / 8.25 / 16.55 / 7.92 fuera de la grilla A/B/C/D.

### 7.4 Cruce planta–elevación (302/303/305/400)
- El texto de las elevaciones está dibujado como curvas (`get_text()` ≈ 0-86 chars → no usable). El OCR de los recortes es insuficiente (`13.91` en 302; rótulos ilegibles en 303/305; 400 solo el cuadro de contrafl echas). **Se requiere inspección humana** de `crop_302_banda20-90.png`, `crop_303_banda20-90.png`, `crop_305_banda15-76.png` y `crop_305_VLI.png` para confirmar/refutar el nivel ROOF y la continuidad de los tramos.
- Hasta entonces: y=7.92, el perímetro del hueco y los extremos quedan **PENDIENTE_VERIFICACION**. No se modifica ningún CSV/código; no se hace commit.

## 8. Validación visual de elevaciones y cierre de geometría (SOLO LECTURA)

### 8.0 Validación visual humana (recibida 2026-08-30)

**Banda centro y≈7.92 → NO es +V.I.20/90.** Es el **borde norte del hueco de escalera**. Los rótulos visuales confirmados sobre ese borde son:
- **+V.I.15/70 (2ª ETAPA)** en el borde horizontal superior (norte del hueco).
- **+V.I.15/VAR (2ª ETAPA)** en el borde vertical izquierdo (oeste del hueco).
- **+V.I.15/68 (2ª ETAPA)** en el borde horizontal inferior (sur del hueco).
- **+V.I.15/76 (2ª ETAPA)** en el borde vertical derecho (este del hueco) y en la continuación horizontal hacia el Este.

El recorte oriental (CASE 4) confirma: horizontal superior = 15/70; verticales = 15/VAR (donde rotuladas); horizontal hacia Oeste = 15/76.

→ **DESCARTAR** la interpretación `+V.I.20/90` para la banda y≈7.92 y cualquier búsqueda de su supuesto extremo este.

**Banda norte y≈12.90 → NO es V.I.** Los rótulos corresponden a N.S.P.=12.29, P.H.I 20×20, cotas 20/230; debajo existe V.60×80 convencional.
→ **DESCARTADO_NO_ES_VI** para C-VI-08 y C-VI-09.

**+V.I.20/90** se mantiene como candidato independiente **solo al OESTE** del plano (xm≈0.54, y≈5.94, zona escalera/M.H.A.).

**VAR** continúa como sección de **altura variable** (confirmado por detalle 400 con secciones 1 y 3); no convertir a prismática.

### 8.1 Geometría vectorial cerrada (lám. 102, planta ROOF; transform. §1.1 validada)
Se identifican **tres bandas horizontales paralelas** e=0.60 m a y_m ≈ **2.90 / 7.92 / 12.90** (espaciado 5.0 m). Tras validación visual §8.0, las bandas 2.90 y 7.92 son **bordes del hueco de escalera** (sur y norte), y la banda 12.90 **NO es V.I.**:

| Banda | y1 | y2 | y_centro | tramo OESTE | tramo ESTE | columna/gap central |
|---|---|---|---|---|---|---|
| Sur (= borde S del hueco, +V.I.15/68) | 2.575 | 3.224 | **2.90** | [1.047 .. 7.596] (6.55 m) | [8.296 .. 16.495] (8.20 m) | verticales 7.596..8.296 (col 7.947); cols en 0.348..1.047 y 16.495..17.195 |
| Centro (= borde N del hueco, +V.I.15/70) | 7.624 | 8.224 | **7.92** | [0.998 .. 7.646] (6.65 m) | [8.246 .. 16.546] (8.30 m) | gap 7.646..8.246 (col 7.947 y muros 7.646/8.246) |
| Norte (= N.S.P.12.29, **NO V.I.**) | 12.574 | 13.221 | **12.90** | [1.047 .. 7.596] (6.55 m) | [8.296 .. 16.495] (8.20 m) | ídem banda sur |

- **Hueco de escalera (perímetro real con rótulos visuales):** Norte = `+V.I.15/70` (y≈7.92); Sur = `+V.I.15/68` (y≈2.90); Oeste = `+V.I.15/VAR` (x≈0.998); Este = `+V.I.15/76` (x≈16.546) + continuación horizontal `15/76` hacia el Este. Alternativas de borde este: columna x≈17.146, muro largo x≈17.995 → **PENDIENTE**.
- **Pilastra interior:** x 7.646..8.246 (col x 7.947) atraviesa bandas y divide cada borde en dos tramos.

### 8.2 Inventario candidato de V.I. de ROOF — desde cero (validación visual §8.0)

Ninguna sección V.I. coincide con filas/nodos del modelo (beams_LT2.csv: filas 0/4.265/8.9/11.885/16.15; nodos 3.75/7.5/11.25/16.25/21.25…). **Todas ADICIONALES. 0 REEMPLAZA.**

#### 8.2.1 Perímetro del hueco de escalera (6 tramos confirmados por sección)

Cada borde tiene una sección propia; la pilastra x≈7.95 divide los bordes horizontales en dos tramos.

| ID | Etiqueta visual | Ori | x1 | y1 | x2 | y2 | Tramo (m) | Sección | Relación modelo | Confianza |
|---|---|---|---|---|---|---|---|---|---|---|
| VI-01 | +V.I.15/70 (2ª ETAPA) | H (E-O) | 0.998 | 7.92 | 7.646 | 7.92 | 6.65 | VI15×70 | ADICIONAL | CONFIRMADO_GEOMETRIA |
| VI-02 | +V.I.15/70 (2ª ETAPA) | H (E-O) | 8.246 | 7.92 | 16.546 | 7.92 | 8.30 | VI15×70 | ADICIONAL | CONFIRMADO_GEOMETRIA |
| VI-03 | +V.I.15/68 (2ª ETAPA) | H (E-O) | 1.047 | 2.90 | 7.596 | 2.90 | 6.55 | VI15×68 | ADICIONAL | CONFIRMADO_GEOMETRIA |
| VI-04 | +V.I.15/68 (2ª ETAPA) | H (E-O) | 8.296 | 2.90 | 16.495 | 2.90 | 8.20 | VI15×68 | ADICIONAL | CONFIRMADO_GEOMETRIA |
| VI-05 | +V.I.15/VAR (2ª ETAPA) | V (N-S) | 0.998 | 2.90 | 0.998 | 7.92 | 5.02 | VI15×VAR (altura variable) | ADICIONAL | CONFIRMADO_GEOMETRIA |
| VI-06 | +V.I.15/76 (2ª ETAPA) | V (N-S) | 16.546 | 2.90 | 16.546 | 7.92 | 5.02 | VI15×76 | ADICIONAL | CONFIRMADO_GEOMETRIA |

**Geom. confirmada: 6 tramos.** Extremos en intersecciones vectoriales reales (verticales de columnas/pilastra).

#### 8.2.2 Extensión este del perímetro (PENDIENTE_VERIFICACION)

El recorte CASE 4 confirma que más allá de x≈16.5 existen elementos adicionales: horizontal superior = 15/70, verticales = 15/VAR, horizontal hacia Oeste = 15/76. Extremos este sin cerrar por intersecciones vectoriales.

| ID | Etiqueta visual | Ori | x1 | y1 | x2 | y2 | Tramo | Sección | Relación | Confianza |
|---|---|---|---|---|---|---|---|---|---|---|
| VI-07 | +V.I.15/76 (2ª ETAPA) | H | 16.546 | 7.92 | ~21–28 (?) | 7.92 | ~4.5–11.5 | VI15×76 | ADICIONAL | PENDIENTE_VERIFICACION (rótulo 15/76 @xm≈18.9; fin no determinado por vectores) |
| VI-08 | +V.I.15/70 (2ª ETAPA) ext | H | 16.546 | 7.92 | ~27.6 (?) | 7.92 | ~11 | VI15×70 | ADICIONAL | PENDIENTE_VERIFICACION (rótulo 15/70(2ªETAPA) @xm≈27.6 en CASE 4) |
| VI-09 | +V.I.15/VAR (2ª ETAPA) ext | V | ~28.6 | ? | ~28.6 | ? | ? | VI15×VAR | ADICIONAL | PENDIENTE_VERIFICACION (rótulo 15/VAR(2ªETAPA) @xm≈28.6 en CASE 4) |

> **Nota:** VI-07 y VI-08 parten del mismo punto (16.546, 7.92) y pueden ser la misma línea con cambio de sección o líneas a distinta cota y; se requiere validación adicional del plano 102 zona este.

#### 8.2.3 Candidato +V.I.20/90 (otra zona del plano)

| ID | Etiqueta visual | Ori | x1 | y1 | x2 | y2 | Sección | Relación | Confianza |
|---|---|---|---|---|---|---|---|---|---|
| VI-10 | +V.I.20/90 | ? | ~0.54 | ~5.94 | ? | ? | VI20×90 | ADICIONAL | PENDIENTE_VERIFICACION (único rótulo 20/90 del plano, al oeste; orientación y extremos sin determinar) |

**Total candidato: 10 elementos V.I. de ROOF; 0 REEMPLAZA; todos ADICIONALES.**
Secciones: VI15×70, VI15×68, VI15×VAR (altura variable), VI15×76, VI20×90. La sección VI15×VAR no se convierte a prismática aún.

### 8.3 Resumen cuantitativo (rev. 2026-08-30, validación visual §8.0 + auditoría §8.5)

- **CONFIRMADO_GEOMETRIA (7 tramos):** perímetro del hueco de escalera principal con extremos en intersecciones vectoriales reales — VI-01/02 (borde N =15/70), VI-03/04 (borde S =15/68), VI-05 (borde O =15/VAR), VI-06 (borde E =15/76) — **más VI-07** (borde N del 2º hueco este =15/76, x 18.545..20.794, y 7.92; auditoría §8.5).
- **PENDIENTE_VERIFICACION (3 elementos):** VI-08 (15/70 este), VI-09 (15/VAR este), VI-10 (20/90 oeste). Extremos no determinables con la lectura vectorial actual (ver §8.5) → se dejan pendientes, **no se infiere por simetría**.
- **DESCARTADO:** la interpretación `+V.I.20/90` para la banda central y≈7.92 (era el borde N del hueco = 15/70). Banda N y=12.90 = N.S.P.12.29 + V.60×80 convencional → **NO es V.I.**
- **Total candidato: 10 elementos V.I. de ROOF; 0 REEMPLAZA; todos ADICIONALES** (ninguna fila/nodo del modelo coincide con 2.90/7.92 ni con x 1.0/16.55).
- **Conteo actualizado:** confirmadas = **7**, pendientes = **3**, descartadas = **0** (la banda N y el supuesto 20/90 de la banda central no eran V.I. y no se cuentan).

**Estado de implementación en el modelo (2026-09):** VI-01..VI-07 → **IMPLEMENTADO_GEOMETRIA** (ver §9); VI-05 → además **PENDING_VARIABLE_SECTION_ANALYSIS**; VI-08..VI-10 → siguen **PENDIENTE_VERIFICACION** (NO incorporadas). Ver §9.

## 9. Implementación en el modelo (IMPLEMENTADO_GEOMETRIA)

Estado de las V.I. de ROOF digitalizadas e incorporadas a `beams_LT2.csv` (historial de auditoría preservado en §8).

| ID | Estado geométrico | Estado análisis | Sección | Coords (x1,y1)->(x2,y2) (analíticas) |
|---|---|---|---|---|
| VI-01 | IMPLEMENTADO_GEOMETRIA | READY | VI15x70 | 0.998,7.92 -> 7.646,7.92 |
| VI-02 | IMPLEMENTADO_GEOMETRIA | READY | VI15x70 | 8.246,7.92 -> 16.546,7.92 |
| VI-03 | IMPLEMENTADO_GEOMETRIA | READY | VI15x68 | **0.998**,2.90 -> 7.596,2.90 |
| VI-04 | IMPLEMENTADO_GEOMETRIA | READY | VI15x68 | 8.296,2.90 -> **16.546**,2.90 |
| VI-05 | IMPLEMENTADO_GEOMETRIA | **PENDING_VARIABLE_SECTION_ANALYSIS** | VI15xVAR | 0.998,2.90 -> 0.998,7.92 |
| VI-06 | IMPLEMENTADO_GEOMETRIA | READY | VI15x76 | 16.546,2.90 -> 16.546,7.92 |
| VI-07 | IMPLEMENTADO_GEOMETRIA | READY | VI15x76 | 18.545,7.92 -> 20.794,7.92 |
| VI-08 | PENDIENTE_VERIFICACION | — | — | no incorporada |
| VI-09 | PENDIENTE_VERIFICACION | — | — | no incorporada |
| VI-10 | PENDIENTE_VERIFICACION | — | — | no incorporada |

> **Decisión de modelación aprobada (conectividad a eje de miembro, 2026-09):**
> El modelo OpenSees lineal usa la convención de **conectividad a eje de miembro**. La auditoría (§8.5 + auditoría de conectividad) confirmó que los desfases de **0.049/0.051 m** en los extremos sur de VI-03/VI-04 (cara interior en x=1.047 / x=16.495) frente a los ejes de los verticales VI-05/VI-06 (x=0.998 / x=16.546) corresponden a la geometría **real** del bloque de esquina y NO a un error de digitalización. Como el modelo global idealiza los miembros mediante elementos lineales, esos encuentros se representan con un **nodo común** en el eje, ajustando las coordenadas analíticas:
> - **VI-03**: extremo oeste (1.047, 2.90) → (**0.998**, 2.90) — ajuste **+0.049 m** (implicitamente incluye el grosor); se documenta como `centroide_ajustado=true;ajuste_m=0.049` en `notes`.
> - **VI-04**: extremo este (16.495, 2.90) → (**16.546**, 2.90) — ajuste **+0.051 m**; documentado como `ajuste_m=0.051` en `notes`.
> - VI-05 (x=0.998) y VI-06 (x=16.546) permanecen sin cambios.
> - **Las coordenadas originales dibujadas NO se borran**: quedan registradas en §8.2.1 y en el diagnóstico de auditoría, y el ajuste se preserva explícitamente en la columna `notes` de `beams_LT2.csv`.
> Resultado de conectividad (nodo común): VI-03↔VI-05 en (0.998,2.90); VI-04↔VI-06 en (16.546,2.90); ya compartían VI-01↔VI-05 en (0.998,7.92) y VI-02↔VI-06 en (16.546,7.92). **Nodos VI únicos: 12 → 10** (8 del marco principal + 2 de VI-07, 2º hueco aislado).

Detalles de la implementación:

- **Secciones agregadas** en `data/sections/sections_LT2.csv`: VI15x70, VI15x68, VI15x76 (b/h prismáticas). **VI15xVAR** se registra con b/h vacíos y `analysis_status=PENDING_VARIABLE_SECTION`; NO se crea sección prismática y el generador NO la materializa.
- **Vigas agregadas** en `data/geometry/beams_LT2.csv`: `ROOF_VI_01`..`ROOF_VI_07`, todas `stage=VI`(family VI), `source=2024_22-102-Model.pdf`, `notes` con `family=VI;stage=2;audit_id=VI-0x`. NO se modificó ninguna de las 46 vigas convencionales de ROOF (L1..L4 tampoco).
- **Nodos nuevos** en coordenadas reales de los extremos de cada V.I. (sin snapping a 3.75/7.50/8.90): inicialmente 12 extremos nuevos; tras la convención de conectividad a eje (2026-09), VI-03/VI-04 extremos sur se alinean a los ejes de VI-05/VI-06 → **10 nodos VI únicos** en ROOF (8 del marco principal + 2 de VI-07). Ningún extremo coincide con la grilla.
- **Conectividad verificada:** VI-01/02 limitan en la pilastra central x≈7.95 (0.998..7.646 y 8.246..16.546, gap 7.646..8.246); VI-03/04 en el gap sur (0.998..7.596 y 8.296..16.546); VI-05 comparte nodo con VI-01/03 en (0.998,7.92)/(0.998,2.90); VI-06 con VI-02/04 en (16.546,7.92)/(16.546,2.90); VI-07 es del 2º hueco este (independiente, no conecta con VI-02/06). **Sin extremos VI desconectados en los 4 encuentros de esquina** (verificado por `check_vertical_connectivity.py` y por duplicación de puntos).
- **ROOF** = 53 vigas geométricas (46 conv + 7 VI); **LT2** = 237 geométricas. **analysis_ready** = 236 (excluye VI-05 por sección variable).
- **Diafragma ROOF:** slave_count 48 -> 60 -> **58** (12 nodos VI → 10 tras conectividad a eje; el master 15.675/8.0725 no coincide con ningún nodo estructural, por lo que no se resta).
- **Conteo final de nodos:** B1=22, L1=L2=L3=L4=48, **ROOF=58**; total estructurales **272** (más 5 masters = 277). Esclavos ROOF = **58**.

Código actualizado: `build_opensees_model.py` (excluye PENDING_VARIABLE_SECTION, reporta materializable), `check_geometry.py` (bloque V.I., geometric vs analysis_ready, conteos), `check_opensees_model.py` (compara actual vs materializable), `viewer_lt2.py` (categoría visual V.I. + leyenda). Sin cargas, sin análisis.

Estado (registro de auditoría, previo a la implementación §9): **CONFIRMADO_GEOMETRIA** para los 7 tramos confirmados (§8.2.1 + VI-07, §8.5); **PENDIENTE_VERIFICACION** para VI-08, VI-09 (este) y VI-10 (oeste) (§8.5). Banda N (12.90) descartada. La implementación en el modelo se documenta en §9 (ahora SÍ se modificaron CSV/código); no se hizo commit.

## 8.5 Auditoría SOLO LECTURA VI-07..VI-10 (2026-08-30)

Lectura de la **planta 102 completa** (no solo recortes) + elevaciones 302/303. No se modificaron CSV ni código.

### 8.5.1 Hallazgos estructurales

**a) La «extensión este» no es una prolongación continua de VI-02/VI-06; hay un SEGUNDO hueco de escalera.**
- Vectorial: rectángulo sólido en x **18.52..21.295** (y 2.92, bordes sur) y x **18.545..20.794** (y 7.92, borde norte), con columnas reales x≈20.55 (y 3.07..7.77 y 8.07..12.77) y muro x≈21.0 (31 m). Acompañado de `N.S.P.=12.29` (≈22.5,10.4) + `P.H.120x20` + pasadas `45/30` → **segunda caja de escalera**, NO continuación del hueco principal.
- Rótulos `+V.I.15/76 (2ª ETAPA)`: borde norte del 2º hueco en (≈18.6,9.31) y (≈19.65,9.31); borde sur en (≈18.92,3.52). **No conecta con VI-02 (borde N del 1er hueco, x≤16.546) ni con VI-06 (borde E del 1er hueco, x=16.546).** Es un conjunto independiente (2º hueco).

**b) Tercera zona este (x≈27–28.6): rótulos sin línea física recuperable en la banda muestreada.**
- Rótulos detectados: `+V.I.15/70 (2ª ETAPA)` en (≈27.4,5.71) y (≈27.4,7.20); `+V.I.15/VAR (2ª ETAPA)` en (≈26.3,8.29) y (≈28.6,8.55); `15/68 (2°` en (≈27.2,9.78); `.25/90`/`V.1.` en (≈31.15,5.5-5.9).
- En x 21.2..32, y 2..10.5 **no hay polilíneas horizontales/verticales largas (≥8 m)** → las líneas físicas de estos rótulos NO se localizan en ese cajón. No se puede fijar extremos; **no se infiere por simetría.** (Posible sub-plano/cota distinta o detalle en planos 500 — la zona es de escalera.)

**c) VI-10 (+V.I.20/90 oeste, x≈0.54, y≈5.94):** rótulo en la **zona de escalera/oeste** («VER DETALLE (serie planos 500)», «DE ESCALERA»). Fragmentos `06/20/`, `(2ª ETAPA)` y `+V.` leídos. Vectorial solo hay tramos cortos (y 5.914: x 0.398..0.998 y 1.517..2.218; verticales x 0.397/0.697/0.998/1.598). **El 20/90 SÍ es una V.I. real de ROOF** (confirmado en elevaciones 302 ×4 y 303 ×1, a nivel cubierta), pero su trazo/orientación y extremos en la planta **no son determinables** con la lectura actual (zona detallada en planos 500). Se deja PENDIENTE.

### 8.5.2 Tabla de auditoría (resultado)

| ID | Etiqueta | Ori | x1 | y1 | x2 | y2 | Conecta con | Relación modelo actual | Fuente | Confianza |
|---|---|---|---|---|---|---|---|---|---|---|
| VI-07 | +V.I.15/76 (2ª ETAPA) — borde N 2º hueco este (y con su borde S paralelo 15/76) | H | 18.545 | 7.92 | 20.794 | 7.92 | columnas x≈20.55 · muro x≈21.0 (2º hueco; **no** VI-02/06) | ADICIONAL | vectores 102 + rótulo @9.31 | CONFIRMADO |
| VI-08 | +V.I.15/70 (2ª ETAPA) — zona x≈27–28.6 | ? | ? | ? | ? | ? | sin línea física recuperada | ADICIONAL | rótulos 102 @(27.4,5.7)/(27.4,7.2) | PENDIENTE |
| VI-09 | +V.I.15/VAR (2ª ETAPA) — zona x≈26.3–28.6 | ? | ? | ? | ? | ? | sin línea física recuperada (VAR, altura variable) | ADICIONAL | rótulos 102 @(26.3,8.3)/(28.6,8.55) | PENDIENTE |
| VI-10 | +V.I.20/90 — oeste, zona escalera (x≈0.54, y≈5.94) | ? | ? | ? | ? | ? | tramos cortos y 5.914 x0.4..1.0; no se fija conexión con hueco principal | ADICIONAL | rótulo 102 + elev. 302/303 (nivel ROOF) | PENDIENTE |

> Notas:
> - **VI-07 CONFIRMADO solo como 2º hueco este** (borde norte y, en paralelo, borde sur). No es continuación de VI-02/VI-06. Se observa que el 2º hueco tiene **dos** bordes horizontales 15/76 (N y S); el inventario podría requerir un VI-07b (borde sur, x 18.52..21.295, y 2.92) — se deja anotado, no se multiplican IDs sin validación.
> - **VI-08/09/10**: lectura visual/vectorial NO permite definir extremos → **PENDIENTE** (regla: no inferir).
> - **Secciones:** VI15×70, VI15×68, VI15×76, VI15×VAR (altura variable, detalle 400 secciones 1 y 3), VI20×90 (oeste). VAR no se convierte a prismática.

## 8.4 Recortes de validación visual (generados 2026-08-30)

Ruta: `C:\Users\natig\AppData\Local\Temp\opencode\lt2_audit\`

| Recorte | Caso | Contenido | Para validar |
|---|---|---|---|
| `vi_c1_b_sur_e_conflicto.png` | 1 | banda Sur-E completa (x 6.5–19 m, y 1.9–4.5 m, zoom 3) + rótulos sobre el tramo | ¿`+V.I.15/76` y `15/VAR` son 1 o 2 elementos? OCR: rótulos `+V.I.15/76 (2ª ETAPA)` a x≈14.8 y ≈18.9; rótulo sin cuerpo @8.9 con cola `(2ª ETAPA)` |
| `vi_c1_detalle_400_var.png` (+`_HI`) | 1 | detalle 400 de `+V.I.15/VAR (2ª ETAPA)` (recorte x px 2950–4120, y 4060–4800 a 180/300 dpi) | sección/refuerzo del VAR a lo largo del tramo; OCR detectó marcas de sección `1` y `3` |
| `vi_c2_borde_este_ABC.png` | 2 | x 15.2–19.2 m, y 1.7–8.9 m, zoom 4; líneas punteadas **A**=x16.546 (rojo), **B**=x17.146 (azul), **C**=x17.995 (naranja) sobre copia PNG (el PDF no se altera) | cuál vertical es el borde Este real del hueco |
| `vi_c3_banda_norte_12_90.png` | 3 | banda Norte (x 0.4–18 m, y 11.9–14.1) | identidad de la banda y=12.90 sin rótulo; OCR: `N.S.P.=12.29`, `45/30` (pasadas), `H120x20` (perfil de malla/contrahuella) → probablemente descanso/contrahuella, NO viga V.I. |
| `vi_c4_ext_este_2090.png` | 4 | x 15–31.9 m, y 6.8–9.4 m | extensión este de la banda centro: OCR halló rótulos `+V.I.15/70 (2ª ETAPA)`@~27.6 y `15/VAR(2°`@28.6, `+V.I.15/76(2°`@~18.6 y `?/76-(2°`@21.2 — ¿hasta dónde corre la línea dibujada? |
| `vi_c0_banda_centro_oeste.png` | (nuevo) | banda centro tramo oeste + tramo E parcial (x 3.2–16.6 m, y 6.5–10.0 m, zoom 3.5) con textos OCR etiquetados | leer cada rótulo de la banda centro y confirmar si hay algún `+V.I.20/90` ahí (el único detectado está a x 0.54, y 5.94 oeste) |
| `vi_map_rotulos.png` | general | plano ROOF completo con todos los rótulos V.I./+V.I. detectados etiquetados en su posición | censo global de rótulos (15/76, 15/70, 15/VAR, 20/90) — discriminar visualmente dígitos 6/7/9 y 0/8 que confunde el OCR |
| `sheet_400_150.png` | general | lámina 400 completa a 150 dpi | contexto del detalle VAR |

**Hallazgos OCR de esta pasada (dependen de confirmación visual):**
- Banda centro y≈7.92: rótulos `+V.I.15/70 (2ª ETAPA)` (xm≈11 y 27.6), `+V.I.15/76 (2ª ETAPA)` (xm≈14.5 y 18.9), `+V.I.15/VAR (2ª ETAPA)` (xm≈8.9 y 28.6). Ningún `20/90` en esa banda.
- `+V.I.20/90` solo en xm≈0.54 y 5.94 (oeste, zona escalera bajo muro M.H.A. e=30 cm).
- Banda sur y≈2.90: `+V.I.15/76 (2ª ETAPA)` a xm≈14.8 y 18.9; rótulo incompleto @8.9; `15/68` ambiguo @27.1 junto al eje D.
- Detalle 400 `+V.I.15/VAR`: marcado con secciones `1` y `3` (corte variable a lo largo del tramo) — confirma el carácter **variable** (no modelable con sección prismática única).
- Elevación 301 (eje 2): `+V.I.15/70`; elevaciones 302/303: `+V.I.20/90` (varias); elevación 305: `+V.I.15/76`, `V.I.` — pendiente de establecer el trazo completo por plano (casa de rótulos con OCR débil).

**Estado de la validación (2026-08-30):** las respuestas visuales confirman el perímetro del hueco con 4 secciones (15/70 N, 15/68 S, 15/VAR O, 15/76 E); descartan 20/90 en la banda central y la banda N como V.I. La auditoría §8.5 confirma **VI-07** (2º hueco este, 15/76) y deja **VI-08, VI-09, VI-10** PENDIENTES (extremos no determinables).