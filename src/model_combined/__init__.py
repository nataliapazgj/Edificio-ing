"""
Paquete `model_combined`.

Modelo estructural combinado LT1 + LT2 en UNA instancia OpenSeesPy.

CONTRATO (no modificar los builders originales):
  - src/ops_model.py, src/build_opensees_model.py, src/gravity.py,
    src/gravity_loads.py y src/run_gravity_analysis.py permanecen intactos.
  - Este paquete reutiliza/encapsula la logica de LT1 y LT2 SIN tocarlos:
      * LT2: se instancia `build_opensees_model.ModelBuilder` y se invocan
        sus METODOS privados (que NO llaman a ops.wipe()) en el orden que el
        propio builder ejecuta dentro de `run()`. Solo `ModelBuilder.run()`
        llama a ops.wipe(); se evita a proposito y el ops.wipe() unico corre
        aqui, en el arranque del orquestador.
      * LT1: se usa una COPIA adaptada del constructor `ops_model.build_ops_model`
        (todas sus llamadas a element/node/remove quedan encapsuladas) con
        offsets de tags, transformacion geometrica confirmada e interfaz.
      * Cargas LT2: se reutilizan `gravity_loads` (eleLoad -beamPoint, pattern 1).
      * Cargas LT1: se encapsula la logica de gravedad de `gravity.py`
        (ops.load nodales) con timeSeries 5000 / pattern 6000.

Decisiones confirmadas / congeladas:
  - Posicion: x_final = 31.25 + x_LT1 ; y_final = -y_LT1 - 0.25 ; z_final = z_LT1.
  - Union de los 12 pares de nodos de interfaz: NODO COMPARTIDO (se reutiliza
    el tag LT2; NO se crea nodo duplicado).
  - 9 columnas LT1 de la interfaz (3 lineas x=31.25, tramos L2-L4) se DESCARTAN:
    ya existen en LT2 como P003/P007/P010 (duplicarian rigidez).
  - Un solo rigidDiaphragm por nivel comun, master LT2 (1002..1005).
  - Cargas separadas por torre: LT2 pattern 1 / tiempo 1; LT1 pattern 6000 /
    tiempo 5000.
"""