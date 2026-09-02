# Benchmark Estructural 3D — OpenSeesPy

## 1. Objetivo

Benchmark reproducible de un marco estructural 3D para el laboratorio de
la asignatura P0MCOC. El modelo completo (geometria, cargas, analisis y
verificaciones) se genera con un solo comando Python.

## 2. Estructura modelada

| Concepto | Valor |
|----------|-------|
| Tipo | Marco 3D de un solo nivel |
| Planta | 10.00 m (X) x 7.25 m (Y) |
| Altura | 3.96 m (Z) |
| Nodos | 10 (4 base + 6 nivel superior) |
| Columnas | 4 (verticales, empotradas en base) |
| Vigas ∥ X | 4 (elementos 5-8) |
| Vigas ∥ Y | 3 (elementos 9-11) |
| Paños de losa | 2 (carga tributaria a 45°) |

Nodos de base: 1(0,0,0) 2(10,0,0) 3(0,7.25,0) 4(10,7.25,0)
Nodos superiores: 5(0,0,3.96) 6(5,0,3.96) 7(10,0,3.96)
                   8(0,7.25,3.96) 9(5,7.25,3.96) 10(10,7.25,3.96)

## 3. Sistema de unidades

| Magnitud | Unidad |
|----------|--------|
| Longitud | m |
| Fuerza | kN |
| Presion / Esfuerzo | kN/m2 |
| Momento | kN·m |

## 4. Material y secciones

| Propiedad | Valor |
|-----------|-------|
| E (modulo elastico) | 25 000 000 kN/m2 |
| nu (Poisson) | 0.20 |
| G (modulo cortante) | 10 416 667 kN/m2 |

**Columna 0.70 x 0.70 m (cuadrada):**

| A [m2] | Iy [m4] | Iz [m4] | J [m4] |
|--------|---------|---------|--------|
| 0.49 | 0.0200083 | 0.0200083 | 0.0338 |

**Viga 0.60 x 0.80 m (b x h):**

| A [m2] | Iy [m4] | Iz [m4] | J [m4] |
|--------|---------|---------|--------|
| 0.48 | 0.0256 | 0.0144 | 0.0308 |

## 5. Supuestos

- Material elástico lineal (no se considera plastificacion).
- Secciones rectangulares macizas de hormigon.
- Apoyos empotrados en los 4 nodos de base (6 DOF restringidos).
- Se considera el peso propio de la losa de 15 cm mediante una carga
  superficial equivalente. No se considera el peso propio de vigas
  ni columnas.
- La losa se modela como carga uniforme distribuida sobre las vigas
  mediante areas tributarias a 45 grados.
- No se consideran efectos de segundo orden (P-delta).

## 6. Carga de losa y areas tributarias

| Parametro | Valor |
|-----------|-------|
| Espesor losa | 0.15 m |
| Peso especifico hormigon | 25 kN/m3 |
| q_losa | 3.75 kN/m2 |
| Area total | 72.50 m2 |
| **Carga total** | **271.875 kN** |

Distribucion a 45 grados sobre las vigas del nivel superior:

| Elemento | Tipo | L [m] | A_trib [m2] | w [kN/m] |
|----------|------|-------|-------------|----------|
| 5 | Viga X | 5.00 | 6.250 | 4.6875 |
| 6 | Viga X | 5.00 | 6.250 | 4.6875 |
| 7 | Viga X | 5.00 | 6.250 | 4.6875 |
| 8 | Viga X | 5.00 | 6.250 | 4.6875 |
| 9 | Viga Y | 7.25 | 11.875 | 6.1422 |
| 10 | Viga Y | 7.25 | 23.750 | 12.2845 |
| 11 | Viga Y | 7.25 | 11.875 | 6.1422 |

Las cargas se aplican como `eleLoad` en ejes locales del elemento
(z-local negativo = hacia abajo).

## 7. Estructura del repositorio

```
P1 benchmark/
  src/
    model.py                    # Modelo completo + analisis + CSV
    visualization.py            # Grafica estatica 3D (matplotlib)
    visualization_interactive.py # Grafica interactiva 3D (plotly)
  results/
    reactions.csv               # Reacciones en apoyos
    displacements.csv           # Desplazamientos nodos 5-10
    element_forces.csv          # Fuerzas locales 11 elementos
  figures/
    nodes_3d.png                # Nodos (solo geometria)
    frame_3d.png                # Frame completo (matplotlib)
    frame_interactive.html      # Frame interactivo (plotly)
  verification/
    verification.md             # Verificaciones manuales del laboratorio
  README.md
```

## 8. Dependencias

- Python >= 3.10
- openseespy
- numpy
- matplotlib
- plotly

Instalar con:

```bash
pip install openseespy numpy matplotlib plotly
```

## 9. Ejecucion

### Modelo + analisis + resultados CSV

```bash
python src/model.py
```

Este comando reconstruye el modelo completo, ejecuta el analisis
estatico lineal, imprime todos los resultados en consola y genera
los tres archivos CSV en `results/`.

### Visualizacion estatica (PNG)

```bash
python src/visualization.py
```

Genera `figures/frame_3d.png` y muestra la grafica durante 2 segundos.

### Visualizacion interactiva (HTML)

```bash
python src/visualization_interactive.py
```

Genera `figures/frame_interactive.html` y lo abre en el navegador.
Se puede rotar, hacer zoom y ver informacion al pasar el cursor.

## 10. Archivos de resultados

| Archivo | Contenido |
|---------|-----------|
| `results/reactions.csv` | Rx, Ry, Rz en nodos 1-4 |
| `results/displacements.csv` | Ux, Uy, Uz, Rx, Ry, Rz en nodos 5-10 |
| `results/element_forces.csv` | Ni, Vyi, Vzi, Ti, Myi, Mzi, Nj, Vyj, Vzj, Tj, Myj, Mzj (ejes locales) |

## 11. Verificaciones

Las verificaciones manuales documentadas en `verification/verification.md`
incluyen:

1. Equilibrio vertical: suma Rz = 271.875 kN = carga total.
2. Transferencia tributaria: suma w·L = 271.875 kN.
3. Fuerza axial columna E1: localForce Ni = 67.97 kN = Rz nodo 1.
4. Desplazamiento vertical nodo 5: acortamiento axial NL/(EA) = 0.022 mm
   = |Uz_OpenSees|.
5. Momento de extremo viga E10: limites [0, 53.5] kN·m, estimacion por
   resortes 22.5 kN·m, OpenSees 18.6 kN·m.
6. Nota sobre `analyze(1)=0`: convergencia numerica no garantiza
   correccion del modelo.
7. Diferencia entre `localForce`, `globalForce` y `eleForce`.

Ver detalle completo en: [verification/verification.md](verification/verification.md)
