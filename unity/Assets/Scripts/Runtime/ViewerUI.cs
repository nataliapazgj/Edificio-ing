using System.Collections.Generic;
using UnityEngine;

namespace EdificioIng.Viewer
{
    // UI minima (IMGUI) del viewer: toggles de categorias (Nodes, Beams,
    // Columns, Walls, Supports, Diaphragms, IDs), toggle de ejes locales,
    // boton Frame All, y panel de informacion del elemento seleccionado.
    public sealed class ViewerUI : MonoBehaviour
    {
        ModelLoader _loader;
        SelectionManager _selection;
        OrbitCamera _orbit;

        bool _nodesOn = true;
        bool _beamsOn = true;
        bool _columnsOn = true;
        bool _wallsOn = true;
        bool _supportsOn = true;
        bool _diaphragmsOn = true;
        bool _slabsOn = true;
        bool _idsOn = false;
        bool _localAxesOn = false;

        GUIStyle _panel;
        GUIStyle _title;
        GUIStyle _mono;
        bool _stylesBuilt;

        public void Setup(ModelLoader loader, SelectionManager selection,
            OrbitCamera orbit)
        {
            _loader = loader;
            _selection = selection;
            _orbit = orbit;
        }

        void OnGUI()
        {
            BuildStyles();
            DrawToolbar();
            DrawInfoPanel();
            DrawHints();
        }

        void DrawToolbar()
        {
            float x = 12, y = 12, w = 150, h = 24, gap = 6;
            int rows = 10; // 9 toggles + Frame All
            GUI.Box(new Rect(x - 6, y - 6, w + 12, rows * h + (rows - 1) * gap + 12),
                "LT2", _title);

            y += 6;
            _nodesOn = GUI.Toggle(new Rect(x, y, w, h), _nodesOn, "Nodes"); y += h + gap;
            _beamsOn = GUI.Toggle(new Rect(x, y, w, h), _beamsOn, "Beams"); y += h + gap;
            _columnsOn = GUI.Toggle(new Rect(x, y, w, h), _columnsOn, "Columns"); y += h + gap;
            _wallsOn = GUI.Toggle(new Rect(x, y, w, h), _wallsOn, "Walls"); y += h + gap;
            _supportsOn = GUI.Toggle(new Rect(x, y, w, h), _supportsOn, "Supports"); y += h + gap;
            _diaphragmsOn = GUI.Toggle(new Rect(x, y, w, h), _diaphragmsOn, "Diaphragms"); y += h + gap;
            _slabsOn = GUI.Toggle(new Rect(x, y, w, h), _slabsOn, "Slabs"); y += h + gap;
            _localAxesOn = GUI.Toggle(new Rect(x, y, w, h), _localAxesOn, "Local Axes"); y += h + gap;
            _idsOn = GUI.Toggle(new Rect(x, y, w, h), _idsOn, "IDs"); y += h + gap;

            if (GUI.Button(new Rect(x, y, w, h), "Frame All"))
                FrameAll();

            ApplyToggles();
        }

        void ApplyToggles()
        {
            _loader.nodeContainer.SetActive(_nodesOn);
            _loader.beamContainer.SetActive(_beamsOn);
            _loader.columnContainer.SetActive(_columnsOn);
            _loader.wallContainer.SetActive(_wallsOn);
            _loader.supportContainer.SetActive(_supportsOn);
            _loader.diaphragmContainer.SetActive(_diaphragmsOn);
            _loader.slabContainer.SetActive(_slabsOn);
            _loader.idContainer.SetActive(_idsOn);
            if (_selection != null)
                _selection.LocalAxesOn = _localAxesOn;
        }

        void DrawInfoPanel()
        {
            var info = _selection != null ? _selection.Selected : null;
            if (info == null) return;
            float x = Screen.width - 320, y = 12, w = 300;
            string txt = "<b>" + info.label + "</b>" + "\n" + info.extra;
            GUI.Box(new Rect(x, y, w, 150), "Seleccion", _panel);
            GUILayout.BeginArea(new Rect(x + 10, y + 10, w - 20, 130));
            GUILayout.Label(txt, _mono);
            if (info.category == "beam")
                GUILayout.Label("Selected: BEAM", _title);
            else if (info.category == "column")
                GUILayout.Label("Selected: COLUMN", _title);
            else if (info.category == "wall")
                GUILayout.Label("Selected: WALL", _title);
            else if (info.category == "slab")
                GUILayout.Label("Selected: SLAB (QA)", _title);
            GUILayout.EndArea();
        }

        void DrawHints()
        {
            var style = new GUIStyle(GUI.skin.label) { fontSize = 12 };
            style.normal.textColor = new Color(0.8f, 0.8f, 0.8f);
            GUI.Label(new Rect(Screen.width - 470, Screen.height - 44, 460, 36),
                "Izq: orbitar   Rueda: zoom   Der/centro: pan   F o boton 'Frame All': reencuadrar   Click: seleccionar",
                style);
        }

        public void FrameAll()
        {
            if (ViewerBoot.RoiBounds.HasValue)
                _orbit.FrameAll(ViewerBoot.RoiBounds.Value);
        }

        void BuildStyles()
        {
            if (_stylesBuilt) return;
            _title = new GUIStyle(GUI.skin.box) { fontSize = 13, fontStyle = FontStyle.Bold };
            _panel = new GUIStyle(GUI.skin.box);
            _mono = new GUIStyle(GUI.skin.label) { fontSize = 12 };
            _mono.richText = true;
            _stylesBuilt = true;
        }
    }
}