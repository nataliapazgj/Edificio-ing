using System;
using System.Collections.Generic;
using UnityEngine;

namespace EdificioIng.Viewer
{
    // Carga data/unity/edificio_lt2.json desde StreamingAssets y construye la
    // geometria procedural (nodos, vigas, columnas, muros, apoyos, masters,
    // diafragmas) y sus colliders para seleccion. Mantiene referencias en
    // grupos contenedores para el toggle de categorias.
    public sealed class ModelLoader : MonoBehaviour
    {
        public GameObject nodeContainer;
        public GameObject beamContainer;
        public GameObject columnContainer;
        public GameObject wallContainer;
        public GameObject supportContainer;
        public GameObject diaphragmContainer;
        public GameObject slabContainer;
        public GameObject idContainer;
        public GameObject localAxesContainer;

        public ModelData Model { get; private set; }
        public IDictionary<int, Vector3> NodePos { get; private set; } = new Dictionary<int, Vector3>();
        public GameObject BeamContainerObj => beamContainer;


        // -------- datos y utiles particulares por cada elemento, para el
        // panel de informacion. -------------------------------------------------
        private readonly Dictionary<string, BeamData> _beamById = new Dictionary<string, BeamData>();
        private readonly Dictionary<string, ColumnData> _columnById = new Dictionary<string, ColumnData>();
        private readonly Dictionary<string, WallData> _wallById = new Dictionary<string, WallData>();

        public bool TryBeam(string id, out BeamData b) => _beamById.TryGetValue(id, out b);
        public bool TryColumn(string id, out ColumnData c) => _columnById.TryGetValue(id, out c);
        public bool TryWall(string id, out WallData w) => _wallById.TryGetValue(id, out w);


        void Awake()
        {
            CreateContainers();
        }

        void CreateContainers()
        {
            nodeContainer = NewContainer("Nodes");
            beamContainer = NewContainer("Beams");
            columnContainer = NewContainer("Columns");
            wallContainer = NewContainer("Walls");
            supportContainer = NewContainer("Supports");
            diaphragmContainer = NewContainer("Diaphragms");
            slabContainer = NewContainer("Slabs");
            idContainer = NewContainer("IDs");
            localAxesContainer = NewContainer("LocalAxes");
            localAxesContainer.SetActive(false);
        }

        static GameObject NewContainer(string name)
        {
            var go = new GameObject(name);
            go.transform.SetParent(null);
            return go;
        }

        public void LoadAndBuild()
        {
            string path = Application.streamingAssetsPath + "/edificio_lt2.json";
            string text;
            try
            {
                text = System.IO.File.ReadAllText(path);
            }
            catch (Exception e)
            {
                Debug.LogError("No se pudo leer " + path + ": " + e.Message);
                gameObject.SetActive(false);
                return;
            }
            Model = JsonUtility.FromJson<ModelData>(text);
            if (Model == null || Model.nodes == null)
            {
                Debug.LogError("JSON invalido o esquema no esperado.");
                gameObject.SetActive(false);
                return;
            }
            IndexNodes();
            IndexElements();
            BuildGeometry();
        }

        void IndexNodes()
        {
            foreach (var n in Model.nodes)
            {
                NodePos[n.tag] = ToWorld(n.x, n.y, n.z);
            }
        }

        void IndexElements()
        {
            foreach (var b in Model.beams) _beamById[b.beam_id] = b;
            foreach (var c in Model.columns) _columnById[c.column_id] = c;
            foreach (var w in Model.walls) _wallById[w.wall_id] = w;
        }

        void BuildGeometry()
        {
            BuildNodes();
            BuildBeams();
            BuildColumns();
            BuildWalls();
            BuildSupports();
            BuildMasters();
            BuildDiaphragmSlaves();
            BuildSlabs();
        }

        // -------- nodos -------------------------------------------------------
        void BuildNodes()
        {
            foreach (var n in Model.nodes)
            {
                // Nodos sinteticos (tag<0) solo dan soporte a los quads de muro
                // LT1; no se dibujan esferas para no ensuciar la vista.
                if (n.tag < 0) continue;
                var go = new GameObject("N" + n.tag);
                go.transform.SetParent(nodeContainer.transform);
                go.transform.position = NodePos[n.tag];
                var color = IsLT1(n.tower) ? NodeLT1 : NodeLT2;
                var sphere = SphereBuilder.Create(go, 0.08f, color);
                sphere.name = "N" + n.tag;
                var info = go.AddComponent<Selectable>();
                info.Set(new SelectableInfo { category = "node", id = n.tag.ToString(),
                    label = "Node " + n.tag, extra = "level: " + n.level + "  tower: " + TowerLabel(n.tower) +
                    "  (" + F(n.x) + ", " + F(n.y) + ", " + F(n.z) + ")" });
                AddCollider(go, MeshOf(sphere));
            }
        }

        // -------- vigas -------------------------------------------------------
        void BuildBeams()
        {
            int i = 0;
            foreach (var b in Model.beams)
            {
                var go = new GameObject("Beam_" + b.beam_id);
                go.transform.SetParent(beamContainer.transform);
                var n1 = NodePos[b.node_i];
                var n2 = NodePos[b.node_j];
                var dir = (n2 - n1).normalized;
                LocalAxes axes = LocalAxes.ForBeam(n1, n2);
                var (h, w) = SectionDims(b.section);
                var center = (n1 + n2) * 0.5f + axes.V1 * (h * 0.5f);  // desplazamiento transversal (viga)
                var mesh = BoxBuilder.Create(n1, n2, axes, h, w);
                go.transform.position = center;
                var color = IsLT1(b.tower) ? BeamLT1 : BeamLT2;
                AddMesh(go, mesh, color, "Beam_" + b.beam_id);
                go.AddComponent<LocalAxesHost>().Set(axes);

                var pd = BuildBeamInfo(b);
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "beam", id = b.beam_id, label = pd,
                    extra = "tower: " + TowerLabel(b.tower)
                });
                AddCollider(go, mesh);
                i++;
            }
        }

        // -------- columnas ----------------------------------------------------
        void BuildColumns()
        {
            foreach (var c in Model.columns)
            {
                var go = new GameObject("Col_" + c.column_id);
                go.transform.SetParent(columnContainer.transform);
                var n1 = NodePos[c.node_i];
                var n2 = NodePos[c.node_j];
                LocalAxes axes = LocalAxes.ForColumn(n1, n2);
                float size = SectionDim(c.section);
                var mesh = BoxBuilder.Create(n1, n2, axes, size, size);
                go.transform.position = (n1 + n2) * 0.5f;
                var color = IsLT1(c.tower) ? ColLT1 : ColLT2;
                AddMesh(go, mesh, color, "Col_" + c.column_id);
                go.AddComponent<LocalAxesHost>().Set(axes);

                string info = "column_id: " + c.column_id + "\nelementTag: " + c.elementTag +
                    "\nsection: " + c.section + "\nstory: " + c.from_level + " to " + c.to_level;
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "column", id = c.column_id, label = info,
                    extra = "tower: " + TowerLabel(c.tower)
                });
                AddCollider(go, mesh);
            }
        }

        // -------- muros (visibles, pendientes en OpenSees) --------------------
        void BuildWalls()
        {
            foreach (var w in Model.walls)
            {
                var go = new GameObject("Wall_" + w.wall_id);
                go.transform.SetParent(wallContainer.transform);
                var a = NodePos[w.nodes.bottom_i];
                var b = NodePos[w.nodes.bottom_j];
                var c = NodePos[w.nodes.top_j];
                var d = NodePos[w.nodes.top_i];
                var mesh = QuadBuilder.Create(a, b, c, d, w.thickness_m);
                go.transform.position = Vector3.zero;
                var color = IsLT1(w.tower) ? WallLT1 : WallLT2;
                AddMesh(go, mesh, color, "Wall_" + w.wall_id);

                string info = "wall_id: " + w.wall_id + "\nthickness: " + F(w.thickness_m) +
                    " m\nlevel: " + w.from_level + " to " + w.to_level +
                    "\nOpenSees: " + w.status;
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "wall", id = w.wall_id, label = info,
                    extra = "tower: " + TowerLabel(w.tower)
                });
                AddCollider(go, mesh);
            }
        }

        // -------- apoyos ------------------------------------------------------
        void BuildSupports()
        {
            foreach (var s in Model.supports)
            {
                var go = new GameObject("Sup_" + s.support_id);
                go.transform.SetParent(supportContainer.transform);
                go.transform.position = ToWorld(s.x, s.y, s.z);
                var box = BoxBuilder.Pyramid(go, 0.5f, 0.9f, Color.green, true);
                box.name = "Sup_" + s.support_id;
                string info = "support_id: " + s.support_id + "\nlevel: " + s.level +
                    "\nfix: UX" + s.ux + " UY" + s.uy + " UZ" + s.uz +
                    "\n     RX" + s.rx + " RY" + s.ry + " RZ" + s.rz;
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "support", id = s.support_id, label = info
                });
                AddCollider(go, MeshOf(box));
            }
        }

        // -------- masters de diafragma ----------------------------------------
        void BuildMasters()
        {
            foreach (var m in Model.master_nodes)
            {
                var go = new GameObject("Master_" + m.master_id);
                go.transform.SetParent(diaphragmContainer.transform);
                go.transform.position = ToWorld(m.x, m.y, m.z);
                var cube = BoxBuilder.Pyramid(go, 0.22f, 0.22f, Color.blue, false);
                cube.name = "Master_" + m.master_id;
                string info = "master: " + m.master_id + " (diaphragm)\nlevel: " + m.level;
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "diaphragm_master", id = m.master_id, label = info
                });
                AddCollider(go, MeshOf(cube));
            }
        }

        // -------- esclavos de diafragma (marcadores pequenos) -----------------
        void BuildDiaphragmSlaves()
        {
            var slaveSet = new HashSet<int>();
            foreach (var d in Model.diaphragms)
            {
                if (d.slave_tags == null) continue;
                foreach (var t in d.slave_tags) slaveSet.Add(t);
            }
            foreach (var t in slaveSet)
            {
                if (!NodePos.TryGetValue(t, out var p)) continue;
                var go = new GameObject("Slave_" + t);
                go.transform.SetParent(diaphragmContainer.transform);
                go.transform.position = p;
                var cube = Geometry.CreateCubeVertices(0.05f);
                var mesh = Geometry.MeshFromVerticesXY(cube);
                AddMesh(go, mesh, new Color(0.5f, 0.7f, 1f), "Slave_" + t);
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "diaphragm_slave", id = "slave_" + t,
                    label = "diaphragm slave node " + t
                });
                AddCollider(go, mesh);
            }
        }

        // -------- losas QA (semitransparentes, con holes respetados) ----------
        void BuildSlabs()
        {
            if (Model.slabs == null) return;
            float levelZ = 0f;
            foreach (var s in Model.slabs)
            {
                levelZ = s.z;
                var ring = ParseRing(s.polygon);
                var holes = new List<List<Vector2>>();
                if (s.holes != null)
                {
                    foreach (var h in s.holes)
                    {
                        var hr = ParseRing(h);
                        if (hr.Count >= 3) holes.Add(hr);
                    }
                }
                var mesh = SlabMeshBuilder.Build(ring, holes, levelZ);
                if (mesh == null) continue;

                var go = new GameObject("Slab_" + s.panel_id);
                go.transform.SetParent(slabContainer.transform);
                go.transform.position = Vector3.zero;

                var mat = Geometry.CreateMaterial(new Color(0.55f, 0.7f, 0.85f,
                    0.55f));
                // Modo transparente estandar correcto.
                mat.SetFloat("_Surface", 1.0f);
                mat.SetOverrideTag("RenderType", "Transparent");
                mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
                mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
                mat.SetInt("_ZWrite", 0);
                mat.DisableKeyword("_ALPHATEST_ON");
                mat.EnableKeyword("_ALPHABLEND_ON");
                mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
                // Culling desactivado: las losas se ven desde arriba y abajo
                // sin depender del winding de los triangulos.
                mat.SetInt("_Cull", 0);
                mat.renderQueue = 3000;

                var mf = go.AddComponent<MeshFilter>();
                mf.sharedMesh = mesh;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = mat;
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                mr.receiveShadows = false;

                string info = "panel_id: " + s.panel_id + "\nlevel: " + s.level +
                    "\narea: " + F(s.area_m2) + " m2" +
                    (s.thickness_m > 0f ? "\nthickness: " + F(s.thickness_m) + " m" : "") +
                    "\nqG: " + (s.qG_kN_m2 > 0f ? F(s.qG_kN_m2) + " kN/m2" : "-") +
                    "\nstatus: " + s.status +
                    (s.hole_status != null && s.hole_status.Length > 0
                        ? "\nholes: " + s.hole_status : "");
                go.AddComponent<Selectable>().Set(new SelectableInfo
                {
                    category = "slab", id = s.panel_id, label = info
                });
                AddCollider(go, mesh);
            }
        }

        static List<Vector2> ParseRing(string s)
        {
            var outList = new List<Vector2>();
            if (string.IsNullOrEmpty(s)) return outList;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            foreach (var token in s.Split(';'))
            {
                var t = token.Trim();
                if (t.Length == 0) continue;
                var parts = t.Split(',');
                if (parts.Length < 2) continue;
                float x, y;
                if (float.TryParse(parts[0], System.Globalization.NumberStyles.Float,
                        inv, out x) &&
                    float.TryParse(parts[1], System.Globalization.NumberStyles.Float,
                        inv, out y))
                {
                    outList.Add(new Vector2(x, y));
                }
            }
            return outList;
        }

        // -------- panel info --------------------------------------------------
        string BuildBeamInfo(BeamData b)
        {
            string s = "beam_id: " + b.beam_id + "\nelementTag: " + b.elementTag +
                "\nlevel: " + b.level + "\nsection: " + b.section +
                "\nnode_i: " + b.node_i + "\nnode_j: " + b.node_j;
            if (b.load_status != "NO_TRIBUTARY_AREA" && b.tributary_area_m2 > 0f)
            {
                s += "\ntributary_area: " + F(b.tributary_area_m2) + " m2" +
                    "\nslab_load: " + F(b.slab_load_kN) + " kN";
            }
            return s;
        }

        // -------- Mesh/construccion -------------------------------------------
        static bool IsLT1(string tower) => !string.IsNullOrEmpty(tower) && tower == "LT1";

        static string TowerLabel(string tower) => IsLT1(tower) ? "LT1" : "LT2";

        // Color de familia segun torre (LT2 = colores historicos del viewer).
        // Los datos del standalone LT2 no llevan "tower" => se tratan como LT2.
        static readonly Color BeamLT2 = new Color(0.00f, 1.00f, 1.00f); // cyan
        static readonly Color BeamLT1 = new Color(1.00f, 0.55f, 0.00f); // naranja
        static readonly Color ColLT2 = new Color(1.00f, 0.00f, 1.00f);  // magenta
        static readonly Color ColLT1 = new Color(0.20f, 0.50f, 1.00f);  // azul
        static readonly Color WallLT2 = new Color(1.00f, 0.00f, 0.00f); // rojo
        static readonly Color WallLT1 = new Color(0.75f, 0.30f, 1.00f); // purpura
        static readonly Color NodeLT2 = new Color(1.00f, 1.00f, 0.00f); // amarillo
        static readonly Color NodeLT1 = new Color(0.60f, 0.90f, 1.00f); // celeste

        void AddMesh(GameObject go, Mesh mesh, Color color, string meshName)
        {
            var mf = go.GetComponent<MeshFilter>();
            if (mf == null) mf = go.AddComponent<MeshFilter>();
            mf.sharedMesh = mesh;
            var mr = go.GetComponent<MeshRenderer>();
            if (mr == null) mr = go.AddComponent<MeshRenderer>();
            var mat = Geometry.CreateMaterial(color);
            mr.sharedMaterial = mat;
        }

        void AddCollider(GameObject go, Mesh mesh)
        {
            var mc = go.GetComponent<MeshCollider>();
            if (mc == null) mc = go.AddComponent<MeshCollider>();
            mc.sharedMesh = mesh;
            mc.convex = false;
        }

        static Mesh MeshOf(GameObject childMeshGo)
        {
            var mf = childMeshGo.GetComponent<MeshFilter>();
            return mf != null ? mf.sharedMesh : null;
        }

        static Vector3 ToWorld(float x, float y, float z)
        {
            // modelo (x, y, z=elev) -> unity (x, z, y)
            return new Vector3(x, z, y);
        }

        static string F(float v) => v.ToString("0.0000", System.Globalization.CultureInfo.InvariantCulture);

        // (h, w): alturas/alto y ancho de la seccion en metros (b x h -> w=b, h=h).
        static (float h, float w) SectionDims(string section)
        {
            float b, h;
            ParseSection(section, out b, out h);
            return (h, b);
        }

        static float SectionDim(string section)
        {
            float b, h;
            ParseSection(section, out b, out h);
            return System.Math.Max(b, h) == 0f ? 0.30f : System.Math.Max(b, h);
        }

        static void ParseSection(string section, out float b, out float h)
        {
            b = 0.30f; h = 0.30f;
            if (string.IsNullOrEmpty(section)) return;
            var matches = System.Text.RegularExpressions.Regex.Matches(
                section, "[0-9]+(\\.[0-9]+)?");
            if (matches.Count < 2) return;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            float v1, v2;
            if (float.TryParse(matches[0].Value, System.Globalization.NumberStyles.Float,
                    inv, out v1) &&
                float.TryParse(matches[1].Value, System.Globalization.NumberStyles.Float,
                    inv, out v2) &&
                v1 > 0f && v2 > 0f)
            {
                b = v1 / 100f;  // cm -> m
                h = v2 / 100f;
            }
        }
    }
}