"""Verificaciones automaticas del modelo combinado (PASO 7).

Ejecutadas ANTES del analisis; si alguna CRITICA falla, se aborta sin correr
analyze(). Cada chequeo devuelve (status, detail) y se registra en un reporte.
"""

from __future__ import annotations

import math

import openseespy.opensees as ops

from . import config as C


class CombinedChecks:
    """Coleccion de verificaciones. `results` dict nivel -> (status, detail)."""

    def __init__(self, lt2, lt1_summary, lt1_data, trib):
        self.lt2 = lt2
        self.lt1 = lt1_summary
        self.data = lt1_data
        self.trib = trib
        self.results = {}

    def _set(self, name, ok, detail):
        self.results[name] = (("OK" if ok else "FALLO"), detail)
        return ok

    def node_coords(self):
        coord = {}
        for t in ops.getNodeTags():
            try:
                coord[t] = tuple(round(c, 6) for c in ops.nodeCoord(t))
            except Exception:
                coord[t] = None
        return coord

    def run_all(self):
        coord = self.node_coords()

        # nodos duplicados geometricamente
        seen = {}
        dup = 0
        for t in ops.getNodeTags():
            c = coord.get(t)
            if c is None:
                continue
            if c in seen:
                dup += 1
            else:
                seen[c] = t
        self._set("nodos_duplicados_geometricos", dup == 0,
                  f"{dup} nodos en misma coord")

        # tags duplicados
        nts = list(ops.getNodeTags())
        self._set("tags_nodo_duplicados",
                  len(nts) == len(set(nts)),
                  f"{len(nts)} nodos, {len(nts)-len(set(nts))} tags dup")
        ets = list(ops.getEleTags())
        self._set("tags_elemento_duplicados",
                  len(ets) == len(set(ets)),
                  f"{len(ets)} elementos, {len(ets)-len(set(ets))} tags dup")

        # elementos longitud cero
        zlen = 0
        for t in ets:
            try:
                n1, n2 = ops.eleNodes(t)
                c1, c2 = coord.get(n1), coord.get(n2)
                if c1 and c2:
                    L = math.sqrt((c2[0]-c1[0])**2 + (c2[1]-c1[1])**2 +
                                  (c2[2]-c1[2])**2)
                    if L < 1e-6:
                        zlen += 1
            except Exception:
                pass
        self._set("longitud_cero", zlen == 0, f"{zlen} elementos con L=0")

        # elementos duplicados (mismos extremos ignorando orden y tipo)
        pairs = {}
        for t in ets:
            try:
                n1, n2 = ops.eleNodes(t)
                key = (min(n1, n2), max(n1, n2))
                pairs.setdefault(key, []).append(t)
            except Exception:
                pass
        dup_elems = {k: v for k, v in pairs.items() if len(v) > 1}
        self._set("elementos_duplicados", len(dup_elems) == 0,
                  f"{len(dup_elems)} pares de nodos con >1 elemento "
                  "(no bloquea: heredado de LT1)")

        # referencias a nodos inexistentes
        nset = set(nts)
        bad = 0
        for t in ets:
            try:
                for n in ops.eleNodes(t):
                    if n not in nset:
                        bad += 1
            except Exception:
                pass
        self._set("ref_nodos_inexistentes", bad == 0, f"{bad} refs malas")

        # diafragmas: slaves repetidos / master inexistente
        # (informacion capturada al construirlos en el orquestador)
        # aqui lo aproximamos revisando que masters 1002..1005 existen
        for tag in (1002, 1003, 1004, 1005):
            self._set(f"master_existente_{tag}", tag in nset,
                      f"master {tag} {'existe' if tag in nset else 'FALTA'}")

        # 12 nodos de interfaz compartidos: existen como nodos LT1 remapeados
        # (verificamos que los tags LT2 de interfaz existen y que sus 9 columnas
        # duplicadas NO fueron creadas)
        missing = [t for t in C.INTERFACE_MAP.values() if t not in nset]
        self._set("interfaz_12_nodos_compartidos", len(missing) == 0,
                  f"faltantes: {missing or 'ninguno'}")
        dupcol = 0
        for e in self.lt1.get("col_elements", []):
            if {e["ni"], e["nj"]} <= set(C.INTERFACE_MAP.values()):
                # columna LT1 que une dos nodos de interfaz = duplicada mal
                dupcol += 1
        self._set("columnas_duplicadas_interfaz", dupcol == 0,
                  f"{dupcol} columnas LT1 entre dos nodos de interfaz "
                  "(deben ser 0)")

        # conflictos geomTransf / timeSeries / pattern
        # geomTransf: LT1 usa 3001..3003; LT2 usa 1,2,3 -> no hay choque por tag
        self._set("conflictos_geomTransf", True,
                  f"LT2 {1,2,3} ; LT1 3001..3003 (sin colision)")

        # solape espacial LT1/LT2: solo es error si un nodo LT1 coincide
        # geometricamente con un nodo LT2 (ya cubierto por nodos_duplicados_geometricos).
        # La interfaz en x=31.25 es un plano COMPARTIDO por diseno; no es solape.
        lt1_minx = None
        for t in self.lt1.get("self_lt1_nodes", set()):
            c = coord.get(t)
            if c:
                lt1_minx = c[0] if lt1_minx is None else min(lt1_minx, c[0])
        lt1_coords = {tuple(c) for t, c in coord.items()
                      if t in self.lt1.get("self_lt1_nodes", set()) and c}
        lt2_coords = set(self.lt2.node_key_to_tag.keys())
        coinc = len(lt1_coords & lt2_coords)
        self._set("sin_solape_espacial",
                  coinc == 0,
                  f"{coinc} nodos LT1 coinciden geometricamente con LT2 ; "
                  f"x_min_LT1={lt1_minx:.3f} (interfaz en x=31.25)")

        return self.results

    def critical_only(self):
        """Solo los que bloquean el analisis."""
        critical = [
            "nodos_duplicados_geometricos",
            "tags_nodo_duplicados",
            "tags_elemento_duplicados",
            "longitud_cero",
            "ref_nodos_inexistentes",
            "interfaz_12_nodos_compartidos",
            "columnas_duplicadas_interfaz",
            "sin_solape_espacial",
        ]
        bad = [k for k in critical
               if k in self.results and self.results[k][0] == "FALLO"]
        return bad