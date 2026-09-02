# StructuralViewer — QA visual del modelo estructural (Semana 2)

Visor Unity mínimo para inspeccionar el modelo estructural aprobado
(nodos, elementos, apoyos, diafragmas y áreas tributarias). **Unity NO es
la fuente de verdad**: todos los datos vienen de `data/processed/unity_model.json`,
exportado desde Python/OpenSees. Si hay discrepancias, manda en los datos, no en el visor.

## Contenido del proyecto

```
unity/StructuralViewer/
├── Assets/
│   ├── Scenes/Main.unity          Escena lista para reproducir
│   └── Scripts/
│       ├── ModelLoader.cs         Carga JSON y construye el modelo 3D
│       └── CameraController.cs    Cámara de órbita/zoom/pan
├── Data/unity_model.json          Copia del modelo exportado
├── Packages/manifest.json
└── ProjectSettings/ProjectVersion.txt   (Unity 2022.3 LTS)
```

## Requisitos

- Unity **2022.3.x LTS** (mínimo para abrir el proyecto). Sin paquetes externos.

## Cómo abrirlo (pasos muy simples)

1. Abre Unity Hub → **Add** → selecciona la carpeta
   `unity/StructuralViewer/` (esta carpeta es el proyecto completo).
2. Cuando se abra el proyecto, entra a **Assets/Scenes** y abre `Main.unity`.
3. Pulsa **Play** (triángulo ▶️). El visor carga solo `Data/unity_model.json`
   y encuadra el modelo automáticamente.

Si mueves el proyecto a otra ruta, el visor también busca
`data/processed/unity_model.json` relativo al proyecto; si no existe, muestra
el aviso de ejecutar `python src/export_unity.py`.

## Controles

| Acción | Mando |
|--------|-------|
| Seleccionar nodo/elemento | Botón izquierdo |
| Orbitar | Botón derecho + arrastrar |
| Zoom | Rueda del ratón |
| Pan / desplazamiento | Botón medio + arrastrar |
| Vista general | Tecla **F** o botón `Vista general (F)` |

## Funciones del panel izquierdo

- **Toggles**: Nodos, Vigas, Columnas, Muros, Apoyos, Diafragmas,
  Áreas tributarias, IDS, Ejes locales.
- **IDs**: etiqueta en pantalla de cada vigas (elementTag),
  columnas (`C`+elementTag) y muros (`M`+elementTag).
- **Colores**: columnas gris, vigas azul, muros naranja, elementos
  **solo-carga** en magenta, apoyos amarillo, diafragmas cian
  semitransparente, áreas tributarias naranja semitransparentes.
- Al seleccionar una **viga FE** con área tributaria, se resalta su área
  y el panel **Tributary Area Inspector** muestra slab, área, q_G, carga
  total y carga lineal equivalente. Si la viga no recibe área tributaria,
  muestra "Sin área tributaria asignada".
- Al seleccionar un elemento, el panel inferior muestra sus datos y (si los
  toggles están activos) sus **ejes locales** (X rojo, Y verde, Z azul).
- Al seleccionar un nodo, se muestra nodeTag, nivel y posición.

## Datos y regeneración

- Export: `python src/export_unity.py` genera `data/processed/unity_model.json`,
  lo copia a `Data/unity_model.json` y escribe el control de calidad en
  `results/unity_export_check.txt` (debe salir `VEREDICTO: PASS`).
- Qué contiene: 187 nodos, 241 elementos FE (48 columnas, 175 vigas,
  18 muros) + 16 elementos solo-carga, 16 apoyos, 4 diafragmas, 4 losas y
  175 áreas tributarias.