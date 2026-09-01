# Analisis gravitacional LT2 (BLOQUE 3)

## Resumen

- return_code (ops.analyze): **-3**  -> NO convergió (posible inestabilidad real; revise mecanismos sin muros)
- Carga total aplicada (vigas L1-L4, areas tributarias): **11541.291565 kN**
- Carga esperada (beam_gravity_loads_LT2.csv): **11541.291608 kN**
- Reacciones/desplazamientos no disponibles (análisis falló).

## Diagnostico de no convergencia

- El sistema es **singular** (return_code = -3): el modelo sin muros no es autoportante en la direccion vertical fuera del plano.
- Nodos estructurales sin camino al empotramiento B1 por el portico (solo via muros): **95** de 272.
- Estos nodos corresponden al bloque OESTE/nucleo (bordes x=0.4 y lineas V40/V30) y la malla del ala norte/sur, resistida por muros M001..M004 que **no estan materializados** (pendiente definido en el proyecto).
- Ejemplos: (0.1, -1.095, -4.01), (0.1, -1.095, -0.05) ...
- No se anadieron restricciones ni muros arbitrarios: se reporta la inestabilidad tal como esta, sin ocultar el mecanismo.

## Cargas aplicadas

- Fuente: `data/loads/tributary_areas_LT2.csv` (receiver_type=BEAM, L1-L4).
- Representación: `eleLoad -beamPoint`, franjas de 0.05 m a lo largo de cada viga; fuerza total y primer momento conservados exactamente (`results/gravity_loads_applied_LT2.csv`).
- Vigas con carga: 184; puntos de carga: 27160.
- Excluidas: ROOF, carga lineal ROOF 1500 kg/m, WALL_EDGE_PENDING (24 áreas de muro, 638.4139 kN), SC.

## Modelo

- Nodos: 277 (estructurales 272, masters 5).
- Elementos: vigas materializadas 236, columnas 50; muros pendientes (40).
- Diafragmas rígidos (UX,UY,RZ) con Transformation: {'L1': 48, 'L2': 48, 'L3': 48, 'L4': 48, 'ROOF': 58}.
- Material: CONC_G25 E=2.35e+07 kN/m², nu=0.2, G=9.79e+06 kN/m²

## Reacciones por apoyo


## Desplazamientos de masters

- NM_L1 (tag None): ux=nan m, uy=nan m, uz=nan m
- NM_L2 (tag None): ux=nan m, uy=nan m, uz=nan m
- NM_L3 (tag None): ux=nan m, uy=nan m, uz=nan m
- NM_L4 (tag None): ux=nan m, uy=nan m, uz=nan m
- NM_ROOF (tag None): ux=nan m, uy=nan m, uz=nan m

## Archivos

- `results/gravity_loads_applied_LT2.csv`
- `results/gravity_loads_beam_summary_LT2.csv`
- `results/gravity_reactions_LT2.csv`
- `results/gravity_displacements_LT2.csv`
- `figures/gravity_loads_L1.png`

