using UnityEngine;

namespace EdificioIng.Viewer
{
    // Maneja la seleccion por click (raycast), muestra el panel de
    // informacion del elemento, y dibuja los ejes locales del elemento
    // seleccionado cuando el toggle Local Axes esta activo.
    public sealed class SelectionManager : MonoBehaviour
    {
        public Camera viewCamera;
        public ModelLoader loader;
        public GameObject localAxesRoot;

        public bool LocalAxesOn { get; set; }
        public SelectableInfo Selected { get; private set; }
        public Vector3 SelectedCenter { get; private set; }
        public LocalAxes? SelectedAxes { get; private set; }

        static readonly Color[] AxisColors =
        {
            new Color(1f, 0.25f, 0.25f),
            new Color(0.25f, 1f, 0.25f),
            new Color(0.3f, 0.6f, 1f),
        };

        int _lineCount;

        void Update()
        {
            if (Input.GetMouseButtonDown(0))
            {
                Ray ray = viewCamera.ScreenPointToRay(Input.mousePosition);
                if (Physics.Raycast(ray, out var hit, 1e5f))
                {
                    var sel = hit.collider.GetComponentInParent<Selectable>();
                    Select(sel);
                }
                else
                {
                    Deselect();
                }
            }

            UpdateLocalAxesVisual();
        }

        void Select(Selectable sel)
        {
            if (sel == null) { Deselect(); return; }
            Selected = sel.Data;
            SelectedCenter = sel.transform.position;
            SelectedAxes = null;

            var host = sel.GetComponentInParent<LocalAxesHost>();
            if (host != null && host.HasAxes)
            {
                SelectedAxes = host.Axes;
            }
        }

        public void Deselect()
        {
            Selected = null;
            SelectedAxes = null;
        }

        // -------- ejes locales del elemento seleccionado ----------------------
        void UpdateLocalAxesVisual()
        {
            foreach (Transform ch in localAxesRoot.transform)
                Destroy(ch.gameObject);
            _lineCount = 0;

            if (!LocalAxesOn || SelectedAxes == null) return;

            var ax = SelectedAxes.Value;
            Vector3 origin = SelectedCenter;
            float len = 3.5f;
            DrawAxis(origin, ax.Axis, len, AxisColors[0]);
            DrawAxis(origin, ax.V1, len, AxisColors[1]);
            DrawAxis(origin, ax.V2, len, AxisColors[2]);
        }

        void DrawAxis(Vector3 origin, Vector3 dir, float len, Color color)
        {
            Vector3 tip = origin + dir * len;
            Tail(origin, tip, 0.08f, color);
            Tail(tip - dir * 0.6f, tip, 0.24f, color);
        }

        GameObject Tail(Vector3 a, Vector3 b, float width, Color color)
        {
            var go = new GameObject("LAseg_" + _lineCount++);
            go.transform.SetParent(localAxesRoot.transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = 2;
            lr.SetPosition(0, a);
            lr.SetPosition(1, b);
            lr.startWidth = width;
            lr.endWidth = width * 0.35f;
            var mat = new Material(Shader.Find("Sprites/Default"));
            mat.color = color;
            lr.material = mat;
            return go;
        }

        void OnDisable()
        {
            if (localAxesRoot != null)
            {
                foreach (Transform ch in localAxesRoot.transform)
                    Destroy(ch.gameObject);
            }
        }

        void Awake()
        {
            if (localAxesRoot == null && ViewerBoot.Instance != null)
                localAxesRoot = ViewerBoot.Instance.Loader.localAxesContainer;
        }
    }
}