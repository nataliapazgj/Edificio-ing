using System.Collections.Generic;
using UnityEngine;

namespace EdificioIng.Viewer
{
    // Punto de entrada de la escena: crea el loader, la camara, la seleccion
    // y la UI; calcula y expone las bounds (ROI) para Frame All.
    public sealed class ViewerBoot : MonoBehaviour
    {
        public static ViewerBoot Instance;

        public ModelLoader Loader { get; private set; }
        public OrbitCamera Orbit { get; private set; }
        public SelectionManager Selection { get; private set; }
        public ViewerUI UI { get; private set; }

        public static Bounds? RoiBounds;

        void Awake()
        {
            Instance = this;

            if (Camera.main == null)
            {
                var c = new GameObject("Main Camera");
                c.tag = "MainCamera";
                var cam = c.AddComponent<Camera>();
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.12f, 0.12f, 0.14f);
                c.AddComponent<AudioListener>();
                Orbit = c.AddComponent<OrbitCamera>();
            }
            else
            {
                Orbit = Camera.main.GetComponent<OrbitCamera>();
                if (Orbit == null) Orbit = Camera.main.gameObject.AddComponent<OrbitCamera>();
            }

            var loaderGo = new GameObject("Model");
            Loader = loaderGo.AddComponent<ModelLoader>();

            var selGo = new GameObject("Selection");
            Selection = selGo.AddComponent<SelectionManager>();
            Selection.viewCamera = Camera.main;
            Selection.loader = Loader;
            Selection.localAxesRoot = Loader.localAxesContainer;

            var uiGo = new GameObject("ViewerUI");
            UI = uiGo.AddComponent<ViewerUI>();
            UI.Setup(Loader, Selection, Orbit);

            LoadAndFrame();
        }

        void LoadAndFrame()
        {
            RoiBounds = null;
            Loader.LoadAndBuild();
            if (Loader.Model == null) return;

            // bounds del modelo completo para Frame All
            var bounds = ComputeBounds();
            RoiBounds = bounds;
            if (bounds.size.sqrMagnitude > 1e-6f)
            {
                Orbit.FrameAll(bounds);
            }
        }

        Bounds ComputeBounds()
        {
            var acc = new Bounds();
            bool set = false;
            foreach (var go in AllNodePositions())
            {
                if (!set) { acc = new Bounds(go, Vector3.one); set = true; }
                else acc.Encapsulate(go);
            }
            if (!set) acc = new Bounds(Vector3.zero, Vector3.one * 10f);
            acc.Encapsulate(BoundsOfContainer(Loader.beamContainer));
            acc.Encapsulate(BoundsOfContainer(Loader.columnContainer));
            acc.Encapsulate(BoundsOfContainer(Loader.wallContainer));
            return acc;
        }

        IEnumerable<Vector3> AllNodePositions()
        {
            foreach (Transform ch in Loader.nodeContainer.transform)
                yield return ch.position;
        }

        static Bounds BoundsOfContainer(GameObject container)
        {
            if (container == null) return new Bounds();
            var r = new Bounds(container.transform.position, Vector3.zero);
            bool set = false;
            foreach (Transform ch in container.transform)
            {
                var mr = ch.GetComponentInChildren<MeshRenderer>();
                if (mr == null) continue;
                if (!set) { r = mr.bounds; set = true; }
                else r.Encapsulate(mr.bounds);
            }
            return r;
        }
    }
}