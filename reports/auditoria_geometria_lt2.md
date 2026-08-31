# Auditoría de geometría — Edificio de Ingeniería LT2 (preliminar)

**Fecha:** 2026-08-30 · **Tipo:** solo lectura · **Sin cambios de geometría, CSV ni código.**
**Estado:** preliminar — la detección de rótulos proviene de **OCR** sobre láminas renderizadas y
requiere verificación visual por lámina antes de digitalizar cualquier elemento.

## Objetivo
Inventariar la familia de vigas inversas **V.I. / +V.I.** (y elementos asociados) a partir de los
planos LT2, cruzar cada rótulo contra el modelo actual (`beams_LT2.csv`, `walls_LT2.csv`, columnas,
soportes) y re-verificar la esquina **D–3 / P010**, sin modificar ningún artefacto.

## Método y limitaciones
- Los PDF vectoriales CAD (~todos sin capa de texto) fueron renderizados (150 dpi) y leídos con
  OCR (`rapidocr-onnxruntime`). Las coordenadas citadas son **píxeles de la lámina completa**
  (`sheet_XXX.png`, A0 a 150 dpi).
- El OCR no garantiza lectura del 100% de los rótulos (texto OMITIDO posible). Por eso todo rótulo
  encontrado se clasifica como pendiente de **revisión visual por lámina** antes de digitalizar.
- No se modificó ni se debe modificar `walls_LT2.csv` ni ningún CSV/código hasta verificar
  visualmente cada elemento.

## Nomenclatura confirmada (lámina 000)
`V.` viga · `V. e/h` · **`V.I.` = viga invertida** · `V.S.I.` = viga semi-invertida ·
`M.H.A.` = muro de hormigón armado · `M.I.`/`M.S.I.` = muros invertidos ·
`M.N.E.H.` = muro no estructural de hormigón · `V.F.` = viga de fundación.
Formato de rótulo de vigas en planos: `V.I. e/h` (espesor/altura), p. ej. `V.I. 20/90`.

## 1) Vigas V.I. / +V.I. detectadas en planos
Las +V.I. (símbolo "+" = vigas adicionales) aparecen asociadas a la **2ª etapa** (pisos
4 / techo). **Ninguna sección V.I. existe en `beams_LT2.csv`** (solo `V60x80`, `V30x80`, `V40x80`).

| Sección | Láminas | Evidencia (OCR) |
|---|---|---|
| **+V.I. 20/90** | 102, 302, 303 | 102: banda Y≈1920 px, ≥6 rótulos; 302: 4 (elev.), 303: 1 (elev.) |
| **+V.I. 15/70 (2° ETAPA)** | 102, 301 | 102: (4209,2920); 301: 2 (elev. eje 2) |
| **+V.I. 15/76 (2° ETAPA)** | 102, 305 | 102: ≥3; 305: 1 (elev. D-D') |
| **V.I. 15/VAR (2° ETAPA)** | 102, 400 | 102: (2133,2476); 400: 2 (detalle de refuerzo) |
| **V.I. 15/24** | 400 | (6332,3484), detalle de viga |

**Clasificación:** `FALTANTE_GEOMETRIA_PENDIENTE_DE_DIGITALIZACION`.
Su existencia está **respaldada por los planos**, pero los tramos y endpoints X/Y todavía
requieren revisión visual de las láminas 102, 301, 302, 303, 305 y 400 para digitalizar
coordenadas y número exacto de tramos.

## 2) Esquina D–3 / P010 — `CONFIRMADO_CORRECTO`
- `grid_x.csv`: eje **D** = x 31.250 · `grid_y.csv`: eje **3** = y 16.150.
- `vertical_elements_LT2.csv`: **P010** = columna `P70x70`, D&3, de B1 a ROOF.
- `column_segments_LT2.csv`: P010 en 5 segmentos B1→L1→L2→L3→L4→ROOF, `P70x70`.
- `supports_LT2.csv`: **SUP_B1_22** = apeo fijo en (31.250, 16.150), B1 (-7.97).
- No hay M.H.A. en esa esquina (muros en x=0.1–1.85 e=30/60 y núcleo e=25/30; ninguno en D&3).
- Elevaciones EJE 3 (lám. 302) y EJE D-D' (lám. 305): no muestran elementos adicionales en la esquina.

**Resultado:** solo P010, sin M.H.A. ni elementos especiales. (Confirmado por cruce de planos/OCR
y CSVs; recomendado cotejo visual final por lámina.)

## 3) Muros M.H.A. en lámina 101 — verificación visual humana (DESCARTADO)
El OCR había detectado cuatro rótulos `M.H.A. e=20` en 101: (4156,448), (4804,453), (4187,968),
(4669,967). **La verificación visual humana del plano 2024_22-101 confirmó que la detección fue un
falso positivo.** En la planta 101 se observan únicamente:

- **M.H.A. e=60** en los muros verticales del extremo A';
- **M.H.A. e=30** en sus brazos horizontales;
- **M.H.A. e=25** en los muros verticales del núcleo derecho;
- **M.H.A. e=30** en el muro horizontal del núcleo derecho.

Estos espesores son consistentes con los muros **M001–M008** actualmente registrados en
`walls_LT2.csv`. **No deben agregarse muros nuevos por este hallazgo.**
- Clasificación: `DESCARTADO_FALSO_POSITIVO_OCR`.

## 4) Vigas de fundación V.F. — `PENDIENTE_DECISION_MODELO`
- Rótulos en láminas 301–305 y 400: **V.F. 20/120, 20/141, 20/150.5, 20/160, 20/180**.
- `beams_LT2.csv` parte en nivel L1 (no existe nivel B1 de vigas).
- El modelo actual idealiza **B1 mediante apoyos empotrados** (22 apoyos fijos en B1) y todavía no
  se ha decidido si incorporar explícitamente vigas/fundaciones.
- **No es una discrepancia automática:** queda a decisión de modelación.
- Clasificación: `PENDIENTE_DECISION_MODELO`.

## 5) Rótulo V.20/VAR (lámina 101) — `PENDIENTE_VERIFICACION_VISUAL`
- Detección OCR en 101: (5094,963). Viga con altura variable (`VAR`), contexto a confirmar
  visualmente (nivel, tramo y sección real) antes de digitalizar.

## 6) Fuente documental E.T.O.G.
- La nomenclatura de lámina 000 referencia la **E.T.O.G.** (p. ej. para `M.N.E.H.`).
- `LT2_CAL_E.T.O.G_25-10-24.pdf` es una **fuente documental externa disponible**, pero **no está
  presente actualmente dentro del repositorio**.

## Anexo — artefactos de esta auditoría (fuera del repo, temporales)
- Renderizados: `C:\Users\natig\AppData\Local\Temp\opencode\lt2_audit\sheet_*.png` (150 dpi).
- OCR por lámina: `C:\Users\natig\AppData\Local\Temp\opencode\lt2_audit\ocr_*.txt`.
- Los planos fuente 000–700 residen en la carpeta padre del proyecto (fuera del repo); 101/102
  están en el repo.

## Próximos pasos sugeridos (fuera del alcance de esta auditoría)
1. Revisión visual de láminas 102, 301, 302, 303, 305 y 400 para digitalizar tramos y endpoints
   de las V.I./+V.I.
2. Revisión visual de `V.20/VAR` en lámina 101 antes de tocar `walls_LT2.csv`.
3. Decisión de modelo sobre vigas/fundaciones en B1 (apoyos empotrados vs. V.F. explícitas).
4. Incorporar la E.T.O.G. al repositorio si procede para validar M.N.E.H. y criterios.