using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace EdificioIng.Viewer.EditorTools
{
    // Validacion de las losas QA del viewer: construye los mismos meshes que
    // ModelLoader.BuildSlabs() (sin requerir escena/camara) y comprueba que se
    // generan exactamente los meshes esperados (100 en LT2), con triangulos y
    // vertices validos y normales hacia arriba. Dividido para poder ver ficheros .
    //
    //   Unity -batchmode -projectPath unity -executeMethod
    //   EdificioIng.Viewer.EditorTools.SlabValidation.Run -quit -logFile ...
    public static class SlabValidation
    {
        const int ExpectedSlabs = 100;

        [MenuItem("EdificioIng/Validate Slabs")]
        public static void RunMenu()
        {
            Run();
        }

        public static void Run()
        {
            string path = Application.streamingAssetsPath + "/edificio_lt2.json";
            string text;
            try
            {
                text = System.IO.File.ReadAllText(path);
            }
            catch (System.Exception e)
            {
                Debug.LogError("[SlabValidation] no se pudo leer el JSON: " + e.Message);
                EditorApplication.Exit(2);
                return;
            }
            var model = JsonUtility.FromJson<ModelData>(text);
            if (model == null || model.slabs == null)
            {
                Debug.LogError("[SlabValidation] JSON sin slabs: " + path);
                EditorApplication.Exit(2);
                return;
            }

            int nMeshes = 0, nTri = 0, nVert = 0, nBad = 0;
            int nAreaOk = 0, nHolePanels = 0;
            var bounds = new Bounds();
            bool useFirst = true;
            var normalsOk = true;

            for (int idx = 0; idx < model.slabs.Length; idx++)
            {
                var s = model.slabs[idx];
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
                var mesh = SlabMeshBuilder.Build(ring, holes, s.z);
                if (mesh == null || mesh.triangles == null)
                {
                    nBad++;
                    Debug.LogWarning("[SlabValidation] mesh nulo: " + s.panel_id + " (" + ring.Count + " pts)");
                    continue;
                }
                nMeshes++;
                nTri += mesh.triangles.Length / 3;
                nVert += mesh.vertices.Length;
                if (mesh.normals != null && mesh.normals.Length > 0)
                {
                    for (int k = 0; k < mesh.normals.Length; k++)
                        if (mesh.normals[k].y < 0.99f) { normalsOk = false; break; }
                }
                // Area de cobertura == area del poligono neto (exterior - holes):
                // prueba fundamental de que los holes NO quedaron tapados.
                float meshArea = TriangleAreaSum(mesh);
                float expected = Area2(ring);
                if (holes.Count > 0) { nHolePanels++; }
                foreach (var h in holes) expected -= Area2(h);
                bool areaOk = Mathf.Abs(meshArea - expected) < 0.02f * Mathf.Max(1f, expected);
                if (areaOk)
                { nAreaOk++; }
                else
                {
                    Debug.LogWarning("[SlabValidation] area fuera de tolerancia: " + s.panel_id +
                        " mesh=" + meshArea.ToString("0.00") +
                        " esperado=" + expected.ToString("0.00") +
                        " holes=" + holes.Count);
                }

                if (bounds.size.magnitude < 0.001f && useFirst)
                { bounds = mesh.bounds; useFirst = false; }
                else if (!useFirst)
                { bounds.Encapsulate(mesh.bounds); }
            }

            Debug.Log("[SlabValidation] slabs en JSON: " + model.slabs.Length);
            Debug.Log("[SlabValidation] meshes de losa creados: " + nMeshes);
            Debug.Log("[SlabValidation] vertices totales: " + nVert);
            Debug.Log("[SlabValidation] triangulos totales: " + nTri);
            Debug.Log("[SlabValidation] paneles con holes: " + nHolePanels);
            Debug.Log("[SlabValidation] area de cobertura correcta (holes recortados): " + nAreaOk + "/" + nMeshes);
            Debug.Log("[SlabValidation] normales hacia arriba OK: " + normalsOk);
            Debug.Log("[SlabValidation] bounds encapsulados: " + (useFirst ? "vacias" : bounds.ToString()));

            bool pass = nMeshes == ExpectedSlabs && nBad == 0 && nTri > 0
                        && nVert > 0 && normalsOk && nAreaOk == nMeshes;
            if (pass)
            {
                Debug.Log("[SlabValidation] OK: se crean exactamente " + ExpectedSlabs +
                          " meshes de losa con triangulos y normales validos.");
                EditorApplication.Exit(0);
            }
            else
            {
                Debug.LogError("[SlabValidation] FALLO: meshes=" + nMeshes +
                               " (esperado " + ExpectedSlabs + ") bad=" + nBad +
                               " tri=" + nTri + " vert=" + nVert +
                               " normalsOk=" + normalsOk);
                EditorApplication.Exit(1);
            }
        }

        static float Area2(List<Vector2> ring)
        {
            float sum = 0f;
            for (int i = 0; i < ring.Count; i++)
            {
                var a = ring[i];
                var b = ring[(i + 1) % ring.Count];
                sum += a.x * b.y - b.x * a.y;
            }
            return Mathf.Abs(sum * 0.5f);
        }

        static float TriangleAreaSum(Mesh mesh)
        {
            var v = mesh.vertices;
            var t = mesh.triangles;
            float sum = 0f;
            for (int i = 0; i < t.Length; i += 3)
            {
                var a = v[t[i]];
                var b = v[t[i + 1]];
                var c = v[t[i + 2]];
                var ab = new Vector2(b.x - a.x, b.z - a.z);
                var ac = new Vector2(c.x - a.x, c.z - a.z);
                sum += Mathf.Abs(ab.x * ac.y - ab.y * ac.x) * 0.5f;
            }
            return sum;
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
    }
}