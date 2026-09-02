using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// ── Destructuracion JSON (esquema de unity_model.json) ──────────────────────
// Los nombres de campo coinciden EXACTAMENTE con la exportacion Python.
[Serializable] public class UV3 { public float x; public float y; public float z; }
[Serializable] public class UPt2 { public float x; public float y; }

[Serializable] public class UNode {
    public int nodeTag; public float x; public float y; public float z; public string level;
}

[Serializable] public class UCrd { public float[] i; public float[] j; }

[Serializable] public class UElem {
    public int elementTag; public int physical_id; public string type;
    public int node_i; public int node_j;
    public UCrd coordinates; public string level;
    public string section; public string material;
    public UV3 local_axis_x; public UV3 local_axis_y; public UV3 local_axis_z;
    public string source_dxf; public string source_id; public string analysis_status;
}

[Serializable] public class USupport { public int nodeTag; public int[] restrained_DOFs; }

[Serializable] public class UDiaph {
    public string level; public int master_node; public int[] slave_nodes; public UPt2[] polygon;
}

[Serializable] public class USlab {
    public string slab_id; public string level; public UPt2[] polygon;
    public float area_m2; public float q_G_kN_m2; public string status;
}

[Serializable] public class UTrib {
    public int tributary_id; public string slab_id; public int beam_elementTag;
    public UPt2[] polygon; public float area_m2; public float q_G_kN_m2;
    public float load_kN; public float equivalent_line_load_kN_m;
}

[Serializable] public class UnityModelRoot {
    public UNode[] nodes; public UElem[] elements; public USupport[] supports;
    public UDiaph[] diaphragms; public USlab[] slabs; public UTrib[] tributary_areas;
}

// ── Referencias para seleccion ──────────────────────────────────────────────
public class ElemRef : MonoBehaviour { public int index; public Color baseColor; }
public class NodeRef : MonoBehaviour { public int index; }

public class ModelLoader : MonoBehaviour {

    [Header("Carga")] public string jsonPathOverride = "";

    UnityModelRoot M;
    GameObject root;
    Dictionary<string, GameObject> groups = new Dictionary<string, GameObject>();

    List<UElem> elements = new List<UElem>();
    List<GameObject> goNodes = new List<GameObject>();
    List<TribRefData> goTrib = new List<TribRefData>();

    class TribRefData { public int tribId; public GameObject go; public Color baseColor; }
    class LabelItem { public Vector3 world; public string text; }

    List<LabelItem> idLabels = new List<LabelItem>();
    List<GameObject> axisLines = new List<GameObject>();

    // Toggles
    bool showNodes = true, showBeams = true, showCols = true, showWalls = true,
         showSupports = true, showDiaph = true, showTrib = true,
         showIds = false, showAxes = false;

    int selElemIdx = -1;     // indice en elements
    bool selIsElement = false;
    int selNodeIdx = -1;

    CameraController camCtrl;
    Vector3 initTarget; float initDist;
    Dictionary<string, float> zCache = new Dictionary<string, float>();

    // ── Colores ──
    static readonly Color CNode   = new Color(0.75f, 0.78f, 0.80f);
    static readonly Color CBeam   = new Color(0.20f, 0.45f, 0.95f);
    static readonly Color CCol    = new Color(0.62f, 0.62f, 0.62f);
    static readonly Color CWall   = new Color(0.85f, 0.50f, 0.25f);
    static readonly Color CLoad   = new Color(0.90f, 0.20f, 0.80f);
    static readonly Color CSup    = new Color(1.00f, 0.85f, 0.10f);
    static readonly Color CDiaph  = new Color(0.30f, 0.90f, 1.00f, 0.25f);
    static readonly Color CTrib   = new Color(1.00f, 0.70f, 0.15f, 0.35f);
    static readonly Color CHilite = new Color(1.00f, 0.00f, 1.00f);

    Vector3 P(float x, float z, float y) { return new Vector3(x, z, y); }

    void Start() {
        string path = ResolveJson();
        if (path == null || !File.Exists(path)) {
            Debug.LogError("[StructuralViewer] unity_model.json no encontrado. " +
                           "Ejecuta primero: python src/export_unity.py");
            return;
        }
        try { M = JsonUtility.FromJson<UnityModelRoot>(File.ReadAllText(path)); }
        catch (Exception e) { Debug.LogError("[StructuralViewer] JSON invalido: " + e.Message); return; }
        Debug.Log("[StructuralViewer] nodos=" + (M.nodes?.Length ?? 0) +
                  " elementos=" + (M.elements?.Length ?? 0) +
                  " tributarias=" + (M.tributary_areas?.Length ?? 0));
        BuildScene();
        FrameCamera();
    }

    string ResolveJson() {
        if (!string.IsNullOrEmpty(jsonPathOverride) && File.Exists(jsonPathOverride))
            return jsonPathOverride;
        string dataRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        string local = Path.Combine(dataRoot, "Data", "unity_model.json");
        if (File.Exists(local)) return local;
        string repoJSON = Path.GetFullPath(Path.Combine(dataRoot, "..", "..",
            "data", "processed", "unity_model.json"));
        if (File.Exists(repoJSON)) return repoJSON;
        return null;
    }

    void BuildScene() {
        root = new GameObject("StructuralViewer");
        foreach (string k in new[] { "NODES", "BEAMS", "COLUMNS", "WALLS",
                                     "LOAD_ONLY", "SUPPORTS", "DIAPHRAGMS",
                                     "TRIBUTARY", "LOCAL_AXES", "ID_LABELS" }) {
            var g = new GameObject(k);
            g.transform.SetParent(root.transform, false);
            groups[k] = g;
        }

        // Nodos
        foreach (var n in M.nodes) {
            GameObject s = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            s.name = "node_" + n.nodeTag;
            s.transform.SetParent(groups["NODES"].transform, false);
            s.transform.position = P(n.x, n.z, n.y);
            s.transform.localScale = Vector3.one * 0.30f;
            s.GetComponent<Renderer>().material = MakeMat(CNode, false);
            var nr = s.AddComponent<NodeRef>();
            nr.index = goNodes.Count;
            goNodes.Add(s);
        }

        // Elementos FE: columnas / vigas / muros
        foreach (var e in M.elements) {
            if (e.analysis_status != "FE") continue;
            AddElementGeometry(e, e.type == "column" ? "COLUMNS"
                                    : e.type == "wall" ? "WALLS" : "BEAMS",
                               e.type == "column" ? CCol : e.type == "wall" ? CWall : CBeam,
                               e.type == "column" ? 0.30f : 0.14f);
        }

        // LOAD_ONLY: solo visualizacion / trazabilidad (distinto color)
        foreach (var e in M.elements) {
            if (e.analysis_status != "LOAD_ONLY") continue;
            AddElementGeometry(e, "LOAD_ONLY", CLoad, 0.14f);
        }

        // Apoyos
        foreach (var sup in M.supports) {
            UNode n = FindNode(sup.nodeTag);
            if (n == null) continue;
            GameObject cu = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cu.name = "supp_" + sup.nodeTag;
            cu.transform.SetParent(groups["SUPPORTS"].transform, false);
            cu.transform.position = P(n.x, n.z, n.y) + new Vector3(0f, 0.4f, 0f);
            cu.transform.localScale = Vector3.one * 0.55f;
            cu.GetComponent<Renderer>().material = MakeMat(CSup, false);
        }

        // Diafragmas (poligono semitransparente por nivel)
        foreach (var d in M.diaphragms)
            BuildPolygon(d.polygon, DiaphZ(d), CDiaph, 0.00f,
                         "diaph_" + d.level, groups["DIAPHRAGMS"].transform);

        // Areas tributarias (poligonos semitransparentes sobre la losa)
        foreach (var t in M.tributary_areas) {
            if (t.polygon == null || t.polygon.Length < 3) continue;
            GameObject go = BuildPolygon(t.polygon, SlabZ(t.slab_id), CTrib, 0.06f,
                                         "trib_" + t.tributary_id,
                                         groups["TRIBUTARY"].transform);
            goTrib.Add(new TribRefData { tribId = t.tributary_id, go = go, baseColor = CTrib });
        }
    }

    void AddElementGeometry(UElem e, string parentKey, Color color, float radius) {
        if (e.coordinates == null || e.coordinates.i == null || e.coordinates.j == null) return;
        Vector3 a = P(e.coordinates.i[0], e.coordinates.i[2], e.coordinates.i[1]);
        Vector3 b = P(e.coordinates.j[0], e.coordinates.j[2], e.coordinates.j[1]);
        if (Vector3.Distance(a, b) < 0.05f) return;
        GameObject go = MakeCyl(a, b, radius, color,
                                (parentKey + "_" + e.elementTag), groups[parentKey].transform);
        var er = go.AddComponent<ElemRef>();
        er.index = elements.Count;
        er.baseColor = color;
        elements.Add(e);
        idLabels.Add(new LabelItem {
            world = (a + b) * 0.5f,
            text = e.elementTag >= 0
                ? (e.type == "beam" ? e.elementTag.ToString()
                    : e.type == "column" ? "C" + e.elementTag : "M" + e.elementTag)
                : "LO"
        });
    }

    UNode FindNode(int tag) { foreach (var n in M.nodes) if (n.nodeTag == tag) return n; return null; }
    UNode GetNode(int idx) { return (idx >= 0 && idx < M.nodes.Length) ? M.nodes[idx] : null; }

    float DiaphZ(UDiaph d) {
        if (zCache.ContainsKey(d.level)) return zCache[d.level];
        float z = 0f;
        UNode n = FindNode(d.master_node);
        if (n != null) z = n.z;
        zCache[d.level] = z;
        return z;
    }

    float SlabZ(string slabId) {
        foreach (var d in M.diaphragms)
            if (SlabLevel(slabId) == d.level) return DiaphZ(d);
        return 0f;
    }

    string SlabLevel(string slabId) {
        for (int i = 0; i < M.slabs.Length; i++)
            if (M.slabs[i].slab_id == slabId) return M.slabs[i].level;
        return slabId;
    }

    Material MakeMat(Color c, bool transparent) {
        Shader sh = Shader.Find(transparent ? "Unlit/Transparent" : "Standard");
        if (sh == null) sh = Shader.Find("Sprites/Default");
        var m = new Material(sh);
        m.color = c;
        if (transparent) m.renderQueue = 3000;
        return m;
    }

    GameObject MakeCyl(Vector3 a, Vector3 b, float r, Color c, string name, Transform parent) {
        var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        go.name = name;
        go.transform.SetParent(parent, false);
        go.transform.position = (a + b) * 0.5f;
        go.transform.rotation = Quaternion.FromToRotation(Vector3.up, b - a);
        go.transform.localScale = new Vector3(r * 2f, Vector3.Distance(a, b) * 0.5f, r * 2f);
        go.GetComponent<Renderer>().material = MakeMat(c, false);
        return go;
    }

    GameObject BuildPolygon(UPt2[] poly, float elev, Color col, float yOff,
                            string name, Transform parent) {
        var go = new GameObject(name);
        go.transform.SetParent(parent, false);
        var mf = go.AddComponent<MeshFilter>();
        var mr = go.AddComponent<MeshRenderer>();
        int n = poly.Length;
        Vector3[] v = new Vector3[n];
        int[] tris = new int[(n - 2) * 3];
        for (int i = 0; i < n; i++) v[i] = new Vector3(poly[i].x, elev + yOff, poly[i].y);
        for (int i = 0; i < n - 2; i++) {
            tris[i * 3] = 0; tris[i * 3 + 1] = i + 1; tris[i * 3 + 2] = i + 2;
        }
        var mesh = new Mesh { vertices = v, triangles = tris };
        mesh.RecalculateNormals();
        mf.sharedMesh = mesh;
        mr.sharedMaterial = MakeMat(col, true);
        return go;
    }

    void FrameCamera() {
        if (M.nodes.Length == 0) return;
        float x0 = float.MaxValue, y0 = float.MaxValue, z0 = float.MaxValue;
        float x1 = float.MinValue, y1 = float.MinValue, z1 = float.MinValue;
        foreach (var n in M.nodes) {
            x0 = Mathf.Min(x0, n.x); x1 = Mathf.Max(x1, n.x);
            y0 = Mathf.Min(y0, n.y); y1 = Mathf.Max(y1, n.y);
            z0 = Mathf.Min(z0, n.z); z1 = Mathf.Max(z1, n.z);
        }
        initTarget = new Vector3((x0 + x1) * 0.5f, (z0 + z1) * 0.5f, (y0 + y1) * 0.5f);
        float span = Mathf.Max(x1 - x0, Mathf.Max(y1 - y0, z1 - z0));
        initDist = span * 2.2f;
        camCtrl = GetComponent<CameraController>();
        if (camCtrl != null) camCtrl.Init(initTarget, initDist);
    }

    void UpdateToggles() {
        groups["NODES"].SetActive(showNodes);
        groups["BEAMS"].SetActive(showBeams);
        groups["COLUMNS"].SetActive(showCols);
        groups["WALLS"].SetActive(showWalls);
        groups["SUPPORTS"].SetActive(showSupports);
        groups["DIAPHRAGMS"].SetActive(showDiaph);
        groups["TRIBUTARY"].SetActive(showTrib);
        groups["ID_LABELS"].SetActive(showIds);
        groups["LOCAL_AXES"].SetActive(showAxes && selIsElement);
    }

    // ── Seleccion ──
    void Update() {
        if (M == null) return;
        if (Input.GetMouseButtonDown(0)) DoPick();
        if (Input.GetKeyDown(KeyCode.F)) ResetView();
    }

    void DoPick() {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        RaycastHit hit;
        if (Physics.Raycast(ray, out hit, 5000f)) {
            var er = hit.collider.GetComponentInParent<ElemRef>();
            if (er != null) { SelectElem(er.index); return; }
            var nr = hit.collider.GetComponentInParent<NodeRef>();
            if (nr != null) { SelectNode(nr.index); return; }
        }
        ClearSelection();
    }

    void SelectElem(int idx) {
        if (idx < 0 || idx >= elements.Count) return;
        ClearSelection();
        selElemIdx = idx;
        selIsElement = true;
        UElem e = elements[idx];
        SetElementColor(idx, CHilite);
        HighlightTributaries(e.elementTag);
        BuildAxes(e);
        UpdateToggles();
    }

    void SelectNode(int idx) {
        if (idx < 0 || idx >= goNodes.Count) return;
        ClearSelection();
        selNodeIdx = idx;
        goNodes[idx].GetComponent<Renderer>().material.color = CHilite;
    }

    void ClearSelection() {
        if (selIsElement && selElemIdx >= 0) SetElementColor(selElemIdx, BaseColor(selElemIdx));
        if (selNodeIdx >= 0 && selNodeIdx < goNodes.Count)
            goNodes[selNodeIdx].GetComponent<Renderer>().material.color = CNode;
        selElemIdx = -1; selIsElement = false; selNodeIdx = -1;
        RestoreTributaries();
        RemoveAxes();
        UpdateToggles();
    }

    Color BaseColor(int idx) {
        return elements[idx].analysis_status == "LOAD_ONLY" ? CLoad
             : elements[idx].type == "column" ? CCol
             : elements[idx].type == "wall" ? CWall : CBeam;
    }

    void SetElementColor(int idx, Color c) {
        foreach (Transform ch in groups[GroupOf(idx)].transform) {
            var er = ch.GetComponent<ElemRef>();
            if (er != null && er.index == idx) er.gameObject.GetComponent<Renderer>().material.color = c;
        }
    }

    string GroupOf(int idx) {
        UElem e = elements[idx];
        if (e.analysis_status == "LOAD_ONLY") return "LOAD_ONLY";
        return e.type == "column" ? "COLUMNS" : e.type == "wall" ? "WALLS" : "BEAMS";
    }

    void HighlightTributaries(int beamTag) {
        foreach (var tr in goTrib) {
            bool sel = tr.beamTag == beamTag;
            tr.go.GetComponent<Renderer>().material.color = sel ? CHilite : tr.baseColor;
        }
    }

    void RestoreTributaries() {
        foreach (var tr in goTrib)
            tr.go.GetComponent<Renderer>().material.color = tr.baseColor;
    }

    // ── Ejes locales ──
    void BuildAxes(UElem e) {
        RemoveAxes();
        Vector3 o = P(e.coordinates.i[0], e.coordinates.i[2], e.coordinates.i[1]);
        float len = 2.0f;
        Color[] cols = { Color.red, Color.green, Color.blue };
        UV3[] axes = { e.local_axis_x, e.local_axis_y, e.local_axis_z };
        string[] names = { "local_x", "local_y", "local_z" };
        for (int k = 0; k < 3; k++) {
            var ln = new GameObject(names[k]);
            ln.transform.SetParent(groups["LOCAL_AXES"].transform, false);
            var lr = ln.AddComponent<LineRenderer>();
            lr.positionCount = 2;
            lr.useWorldSpace = true;
            lr.startWidth = 0.06f; lr.endWidth = 0.06f;
            lr.material = new Material(Shader.Find("Sprites/Default"));
            lr.startColor = cols[k]; lr.endColor = cols[k];
            lr.SetPosition(0, o);
            lr.SetPosition(1, o + new Vector3(axes[k].x, axes[k].z, axes[k].y) * len);
            axisLines.Add(ln);
        }
    }

    void RemoveAxes() { if (axisLines == null) return; foreach (var g in axisLines) if (g) Destroy(g); axisLines.Clear(); }

    void ResetView() { if (camCtrl != null) camCtrl.Init(initTarget, initDist); }

    // ── UI minima (OnGUI) ──
    void OnGUI() {
        if (M == null) {
            GUI.Box(new Rect(10, 10, 460, 60), "");
            GUILayout.BeginArea(new Rect(18, 18, 440, 40));
            GUILayout.Label("No se encontro unity_model.json (ejecutar src/export_unity.py)");
            GUILayout.EndArea();
            return;
        }
        GUILayout.BeginArea(new Rect(10, 10, 215, 370), GUI.skin.box);
        GUILayout.Label("QA Estructural - Viewer (Semana 2)");
        showNodes    = GUILayout.Toggle(showNodes,    "Nodos");
        showBeams    = GUILayout.Toggle(showBeams,    "Vigas");
        showCols     = GUILayout.Toggle(showCols,     "Columnas");
        showWalls    = GUILayout.Toggle(showWalls,    "Muros");
        showSupports = GUILayout.Toggle(showSupports, "Apoyos");
        showDiaph    = GUILayout.Toggle(showDiaph,    "Diafragmas");
        showTrib     = GUILayout.Toggle(showTrib,     "Areas tributarias");
        GUILayout.Space(4);
        showIds      = GUILayout.Toggle(showIds,      "IDs");
        showAxes     = GUILayout.Toggle(showAxes,     "Ejes locales");
        GUILayout.Space(6);
        if (GUILayout.Button("Vista general (F)")) ResetView();
        GUILayout.Space(4);
        GUILayout.Label("Izq: seleccionar | Der: orbitar");
        GUILayout.Label("Rueda: zoom | Medio: pan | F: vista general");
        GUILayout.EndArea();
        UpdateToggles();

        if (showIds) DrawLabels();
        if (selIsElement) DrawElemPanel(selElemIdx);
        else if (selNodeIdx >= 0) DrawNodePanel(selNodeIdx);
    }

    void DrawLabels() {
        var cam = Camera.main;
        if (cam == null) return;
        foreach (var it in idLabels) {
            Vector3 sp = cam.WorldToScreenPoint(it.world);
            if (sp.z < 0f) continue;
            GUI.Label(new Rect(sp.x - 15, Screen.height - sp.y, 90, 18), it.text);
        }
    }

    void DrawElemPanel(int idx) {
        if (idx < 0 || idx >= elements.Count) return;
        UElem e = elements[idx];
        float x = 10f, y = 388f, w = 380f;
        GUI.Box(new Rect(x, y, w, 268f), "");
        GUILayout.BeginArea(new Rect(x + 8, y + 8, w - 16, 250f));
        GUILayout.Label("ELEMENTO  (" + e.analysis_status + ")");
        GUILayout.Label("elementTag:  " + e.elementTag);
        GUILayout.Label("physical_id: " + e.physical_id);
        GUILayout.Label("tipo:        " + e.type);
        GUILayout.Label("nivel:       " + e.level);
        if (e.analysis_status == "FE") {
            GUILayout.Label("node_i:      " + e.node_i);
            GUILayout.Label("node_j:      " + e.node_j);
        }
        GUILayout.Label("seccion:     " + e.section);
        GUILayout.Label("material:    " + e.material);
        float len = Vector3.Distance(
            P(e.coordinates.i[0], e.coordinates.i[2], e.coordinates.i[1]),
            P(e.coordinates.j[0], e.coordinates.j[2], e.coordinates.j[1]));
        GUILayout.Label("longitud:    " + len.ToString("0.00") + " m");
        if (!string.IsNullOrEmpty(e.source_dxf)) GUILayout.Label("source_dxf:  " + e.source_dxf);
        if (!string.IsNullOrEmpty(e.source_id) && e.source_id != "0")
            GUILayout.Label("source_id:   " + e.source_id);

        if (e.type == "beam" && e.analysis_status == "FE")
            DrawTributaryInspector(e.elementTag);
        GUILayout.EndArea();
    }

    void DrawTributaryInspector(int beamTag) {
        var found = new List<UTrib>();
        foreach (var t in M.tributary_areas)
            if (t.beam_elementTag == beamTag) found.Add(t);
        GUILayout.Space(6);
        GUILayout.Label("Tributary Area Inspector");
        bool anyPoly = false;
        foreach (var t in found) if (t.polygon != null && t.polygon.Length >= 3) anyPoly = true;
        if (!anyPoly) {
            GUILayout.Label("  > Sin area tributaria asignada");
        } else {
            foreach (var t in found) {
                GUILayout.Label("  slab " + t.slab_id + "  area " + t.area_m2.ToString("0.00") + " m2");
                GUILayout.Label("  q_G " + t.q_G_kN_m2.ToString("0.00") +
                                "  load " + t.load_kN.ToString("0.00") + " kN");
                GUILayout.Label("  eq " + t.equivalent_line_load_kN_m.ToString("0.00") + " kN/m");
            }
        }
    }

    void DrawNodePanel(int idx) {
        UNode n = GetNode(idx);
        if (n == null) return;
        GUI.Box(new Rect(10, 388, 320, 120), "");
        GUILayout.BeginArea(new Rect(18, 396, 300, 100));
        GUILayout.Label("NODO");
        GUILayout.Label("nodeTag: " + n.nodeTag);
        GUILayout.Label("level:   " + n.level);
        GUILayout.Label("pos:     (" + n.x.ToString("0.00") + ", " + n.y.ToString("0.00") +
                        ", " + n.z.ToString("0.00") + ")");
        GUILayout.EndArea();
    }
}