# Verificacion — Benchmark 3D

## 1. Geometria

Nivel superior (z = 3.96 m): 6 nodos en reticula 10.0 x 7.25 m con eje intermedio en X = 5.0 m.

| Nodo | X [m] | Y [m] | Z [m] |
|------|-------|-------|-------|
| 5 | 0.00 | 0.00 | 3.96 |
| 6 | 5.00 | 0.00 | 3.96 |
| 7 | 10.00 | 0.00 | 3.96 |
| 8 | 0.00 | 7.25 | 3.96 |
| 9 | 5.00 | 7.25 | 3.96 |
| 10 | 10.00 | 7.25 | 3.96 |

Nodos de base (z = 0): nodos 1-4, empotrados (6 DOF restringidos).

11 elementos: 4 columnas + 4 vigas paralelas a X + 3 vigas paralelas a Y.

## 2. Material y secciones

| Propiedad | Valor |
|-----------|-------|
| E | 25 000 000 kN/m2 |
| nu | 0.20 |
| G | 10 416 667 kN/m2 |

| Seccion | Dim [m] | A [m2] | Iy [m4] | Iz [m4] | J [m4] |
|---------|---------|--------|---------|---------|--------|
| Columna | 0.70 x 0.70 | 0.49 | 0.0200083 | 0.0200083 | 0.0338 |
| Viga | 0.60 x 0.80 | 0.48 | 0.0256 | 0.0144 | 0.0308 |

## 3. Carga de losa

| Parametro | Valor |
|-----------|-------|
| Espesor losa | 0.15 m |
| Peso especifico hormigon | 25 kN/m3 |
| q_losa | 3.75 kN/m2 |
| Area total losa | 72.50 m2 |
| Carga total teorica (q x A) | **271.875 kN** |

## 4. Verificacion de transferencia tributaria

Distribucion a 45 grados, carga lineal equivalente por viga.

| Elem | Tipo | Ni-Nj | L [m] | A_trib [m2] | w [kN/m] | w*L [kN] |
|------|------|-------|-------|-------------|----------|----------|
| 5 | Viga X | 5-6 | 5.00 | 6.250 | 4.6875 | 23.438 |
| 6 | Viga X | 6-7 | 5.00 | 6.250 | 4.6875 | 23.438 |
| 7 | Viga X | 8-9 | 5.00 | 6.250 | 4.6875 | 23.438 |
| 8 | Viga X | 9-10 | 5.00 | 6.250 | 4.6875 | 23.438 |
| 9 | Viga Y | 5-8 | 7.25 | 11.875 | 6.1422 | 44.531 |
| 10 | Viga Y | 6-9 | 7.25 | 23.750 | 12.2845 | 89.062 |
| 11 | Viga Y | 7-10 | 7.25 | 11.875 | 6.1422 | 44.531 |

**Suma w_i * L_i = 271.875 kN** — coincide con q x A.

## 5. Verificacion de equilibrio

Reacciones verticales en apoyos (post-analisis):

| Apoyo | Rz [kN] |
|-------|---------|
| Nodo 1 | 67.9687 |
| Nodo 2 | 67.9687 |
| Nodo 3 | 67.9687 |
| Nodo 4 | 67.9687 |

**Suma Rz = 271.875 kN**

## 6. Diferencia de equilibrio

```
Suma Rz - Carga aplicada = 271.875 - 271.875 = -3.10e-10 kN
```

La diferencia es practicamente cero (orden de redondeo numerico).

## 7. Desplazamiento vertical maximo

| Nodo | Uz [m] | Uz [mm] |
|------|--------|---------|
| 9 (centro) | -0.00095794 | -0.958 |

Nodo 9 = punto central de la reticula (X = 5.0, Y = 7.25).

Valores simetricos verificados en nodos espejo: 6 (mismo Uz que 9).

## 8. Nota sobre la verificacion del analisis

`ops.analyze(1) = 0` indica que el solver numerico convergio sin errores.
Esto **no demuestra por si solo** que el modelo sea correcto.

Una respuesta numerica exitosa puede ocultar errores de:

- Idealizacion geometrica (nodos, conectividad, apoyos)
- Asignacion incorrecta de secciones o material
- Cargas mal orientadas (ejes locales vs. globales)
- Condiciones de contorno inadecuadas
- Unidades inconsistentes

El equilibrio verificado (suma Rz = carga total) y la consistencia de
resultados con esperativas fisicas son indicadores necesarios pero no
suficientes. Se recomiendan pruebas adicionales: comparar con solucion
analitica de una viga simplemente apoyada, verificar fuerzas elementales
en nodos de empotramiento, y ejecutar el caso con factor de carga
variable para detectar comportamiento no lineal inesperado.

## 9. Fuerza axial de la columna E1

La columna E1 conecta nodo 1 (0,0,0) con nodo 5 (0,0,3.96).
Su eje local x coincide con Z global (vertical).

Metodo de extraccion: `ops.eleResponse(1, "localForce")`.
**Nota:** `ops.eleResponse(tag, "forces")` y `ops.eleForce(tag)` devuelven
fuerzas en ejes **GLOBALES**, no locales. Usar `"localForce"` explicitamente.

| Fuente | Valor |
|--------|-------|
| localForce Ni (extremo i, nodo 1) | **+67.9687 kN** |
| localForce Nj (extremo j, nodo 5) | **-67.9687 kN** |
| nodeReaction(1, 3) = Rz nodo 1 | **+67.9687 kN** |

Diferencia: **0.00 kN** (ambas representan la misma cantidad fisica).

## 10. Desplazamiento vertical del nodo 5 — verificacion manual

El desplazamiento vertical del nodo 5 se puede estimar como el
acortamiento axial de la columna E1 (nodo 1 -> nodo 5):

```
delta_manual = N * L / (E * A)
```

| Parametro | Valor |
|-----------|-------|
| N (fuerza axial E1) | 67.9687 kN |
| L (longitud columna) | 3.96 m |
| E (modulo elastico) | 25 000 000 kN/m2 |
| A (area seccion) | 0.49 m2 |

```
delta_manual = 67.9687 * 3.96 / (25 000 000 * 0.49)
             = 0.00002197 m
             = 0.02197 mm
```

Lectura de OpenSees (results/displacements.csv, nodo 5):

```
Uz_OpenSees = -2.1972e-05 m = -0.02197 mm
```

| Magnitud | Valor [m] | Valor [mm] |
|----------|-----------|------------|
| delta_manual | 2.1972e-05 | 0.02197 |
| abs(Uz_OpenSees) | 2.1972e-05 | 0.02197 |
| Diferencia absoluta | < 1e-09 | < 1e-06 |
| Error porcentual | ~0% | ~0% |

**Nota sobre signo:** Uz_OpenSees es negativo (-Z = hacia abajo) porque
OpenSees usa convencion de desplazamiento global. delta_manual es positivo
porque representa magnitud de acortamiento. Las magnitudes coinciden.

**Conclusion:** La comparacion es razonable. El nodo 5 se desplaza
verticalmente la misma cantidad que el acortamiento axial de la columna E1.
Esto confirma que el desplazamiento vertical es dominado por la deformacion
axial de la columna, y que las vigas en la zona de esquina tienen rigidez
suficiente para no transferir momentos significativos al nodo 5.

## 11. Momento de extremo de la viga E10

La viga E10 conecta nodo 6 (5,0,3.96) con nodo 9 (5,7.25,3.96),
paralela a Y global. Carga uniforme vertical w = 12.2845 kN/m.

| Parametro | Valor |
|-----------|-------|
| L | 7.25 m |
| w | 12.2844827586 kN/m |
| E | 25 000 000 kN/m2 |
| Iy | 0.0256 m4 |
| G | 10 416 667 kN/m2 |
| J (vigas X) | 0.0308 m4 |
| Lx (vigas X) | 5.00 m |

### 11.1 Casos limite

**Articulacion perfecta:**

```
M_end = 0 kN·m
```

**Empotramiento perfecto:**

```
M_fixed = w * L^2 / 12
        = 12.2845 × 7.25^2 / 12
        = 53.503 kN·m
```

**Verificacion de limites:**

```
0 < |My_OpenSees| = 18.638 < 53.503  ✓
```

Los extremos de E10 no son articulados ni perfectamente empotrados:
estan parcialmente restringidos por la rigidez del marco.

### 11.2 Estimacion con resortes rotacionales

Se reemplaza la rigidez del marco en los nodos 6 y 9 por un resortes
rotacionales equivalentes, considerando que en cada nodo dos vigas X
aportan rigidez torsional en paralelo:

```
k_theta = 2 * G * J / Lx
        = 2 × 10 416 667 × 0.0308 / 5.00
        = 128 333.33 kN·m/rad
```

Rigidez flexional de la propia viga:

```
2 * E * Iy / L = 2 × 25 000 000 × 0.0256 / 7.25
               = 176 551.72 kN·m/rad
```

Momento de extremo estimado:

```
M_est = M_fixed × k_theta / (k_theta + 2*E*Iy/L)
      = 53.503 × 128 333.33 / (128 333.33 + 176 551.72)
      = 53.503 × 0.4209
      = 22.528 kN·m
```

### 11.3 Comparacion

| Cantidad | Valor [kN·m] |
|----------|--------------|
| M_fixed (empotramiento) | 53.503 |
| M_est (modelo resortes) | 22.528 |
| \|My_OpenSees\| | 18.638 |
| Diferencia (M_est - OpenSees) | 3.890 |
| Error porcentual | 20.9% |

### 11.4 Nota

Esta estimacion es una **aproximacion manual simplificada**, no una
solucion exacta del marco. La discrepancia del 20.9% se debe a que el
modelo de resortes reemplaza la rigidez completa del sistema por un
sustituto unidimensional. Las principales simplificaciones son:

- Solo considera rigidez torsional (G×J) de las vigas X, ignorando
  su rigidez flexional (E×Iy) que tambien contribuye a la restriccion
  rotacional.
- Ignora la rigidez de las columnas conectadas a los nodos 6 y 9.
- Asume que el factor de distribucion de rigideces es identico en
  ambos extremos, cuando en realidad la simetria del marco lo
  justifica parcialmente.
