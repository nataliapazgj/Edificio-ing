using UnityEngine;

namespace EdificioIng.Viewer
{
    // Geometria procedural simple (Boxes, quads, esferas, conos/pyramids).
    // Unidades en metros.
    public static class Geometry
    {
        public static Material CreateMaterial(Color color)
        {
            var shader = Shader.Find("Standard");
            if (shader == null) shader = Shader.Find("Sprites/Default");
            var m = new Material(shader != null ? shader : Shader.Find("Diffuse"));
            if (ShadersNoStandard(m)) m.shader = Shader.Find("Sprites/Default");
            m.color = color;
            return m;
        }

        static bool ShadersNoStandard(Material m)
        {
            return m.shader == null || m.shader.name != "Standard";
        }

        public static Vector3[] CreateCubeVertices(float size)
        {
            float h = size / 2f;
            return new Vector3[]
            {
                new Vector3(-h,-h,-h), new Vector3(h,-h,-h), new Vector3(h,h,-h), new Vector3(-h,h,-h),
                new Vector3(-h,-h,h), new Vector3(h,-h,h), new Vector3(h,h,h), new Vector3(-h,h,h),
            };
        }

        // Caja alineada a ejes locales entre dos puntos, seccion (h x w) en las
        // direcciones locales v1 (vertical) y v2 (transversal). El mesh queda
        // centrado en el origen y orientado a lo largo del eje local Axis; el
        // transform del objeto lo posiciona en el centro del elemento.
        public static Mesh Box(Vector3 axis, Vector3 v1, Vector3 v2, float length,
            float h, float w)
        {
            Vector3 a1 = v1 * (h * 0.5f);
            Vector3 a2 = v2 * (w * 0.5f);
            Vector3 half = axis * (length * 0.5f);
            Vector3 midNeg = -half;
            var verts = new Vector3[]
            {
                midNeg - a1 - a2,
                midNeg - a1 + a2,
                midNeg + a1 + a2,
                midNeg + a1 - a2,
                half  - a1 - a2,
                half  - a1 + a2,
                half  + a1 + a2,
                half  + a1 - a2,
            };
            return MeshFromVerticesXY(verts);
        }

        public static Mesh BoxCenteredAtElem(Vector3 p1, Vector3 p2, Vector3 v1, Vector3 v2,
            float h, float w)
        {
            Vector3 axis = (p2 - p1).normalized;
            float length = (p2 - p1).magnitude;
            return Box(axis, v1, v2, length, h, w);
        }

        public static Mesh Quad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, float extrude)
        {
            // panel con espesor ficticio para que no sea plano (seleccion mas facil)
            Vector3 n = Vector3.Cross(b - a, d - a).normalized * extrude;
            Vector3 a1 = a + n, b1 = b + n, c1 = c + n, d1 = d + n;
            var verts = new Vector3[] { a, b, c, d, a1, b1, c1, d1 };
            var tri = new int[]
            {
                0,1,2, 0,2,3,
                4,5,1, 4,1,0,
                5,6,2, 5,2,1,
                6,7,3, 6,3,2,
                7,4,0, 7,0,3,
            };
            var mesh = new Mesh();
            mesh.vertices = verts;
            mesh.triangles = tri;
            mesh.RecalculateNormals();
            var uv = new Vector2[8];
            for (int i = 0; i < 8; i++) uv[i] = new Vector2(0, 0);
            mesh.uv = uv;
            return mesh;
        }

        public static Mesh UvSphere(float radius, int rings, int segments)
        {
            var verts = new System.Collections.Generic.List<Vector3>();
            var tris = new System.Collections.Generic.List<int>();
            for (int ri = 0; ri <= rings; ri++)
            {
                float ph = Mathf.PI * ri / rings;
                for (int si = 0; si <= segments; si++)
                {
                    float th = 2f * Mathf.PI * si / segments;
                    verts.Add(new Vector3(
                        radius * Mathf.Sin(ph) * Mathf.Cos(th),
                        radius * Mathf.Cos(ph),
                        radius * Mathf.Sin(ph) * Mathf.Sin(th)));
                }
            }
            for (int ri = 0; ri < rings; ri++)
            {
                for (int si = 0; si < segments; si++)
                {
                    int a = ri * (segments + 1) + si;
                    int b = a + segments + 1;
                    tris.Add(a); tris.Add(b); tris.Add(a + 1);
                    tris.Add(b); tris.Add(b + 1); tris.Add(a + 1);
                }
            }
            var mesh = new Mesh();
            mesh.vertices = verts.ToArray();
            mesh.triangles = tris.ToArray();
            mesh.RecalculateNormals();
            return mesh;
        }

        public static Mesh MeshFromVerticesXY(Vector3[] verts)
        {
            var mesh = new Mesh();
            mesh.vertices = verts;
            var tri = new int[]
            {
                0,2,1, 0,3,2,
                4,5,6, 4,6,7,
                4,0,1, 4,1,5,
                5,1,2, 5,2,6,
                6,2,3, 6,3,7,
                7,3,0, 7,0,4,
            };
            mesh.triangles = tri;
            mesh.RecalculateNormals();
            return mesh;
        }

        public static Mesh MeshFromVertices(Vector3[] verts, Color color, string name)
        {
            return MeshFromVerticesXY(verts);
        }
    }

    public static class BoxBuilder
    {
        public static Mesh Create(Vector3 p1, Vector3 p2, LocalAxes axes, float h, float w)
        {
            return Geometry.BoxCenteredAtElem(p1, p2, axes.V1, axes.V2, h, w);
        }

        // Piramide/cono simple para apoyos y masters.
        public static GameObject Pyramid(GameObject parent, float baseHalf, float height,
            Color color, bool upSat)
        {
            Vector3[] verts;
            if (baseHalf == height) verts = Geometry.CreateCubeVertices(baseHalf);
            else verts = PyramidVerts(baseHalf, height);
            var mesh = Geometry.MeshFromVerticesXY(verts);
            var go = new GameObject(parent.name + "_mesh");
            go.transform.SetParent(parent.transform);
            go.transform.localPosition = Vector3.zero;
            var mf = go.AddComponent<MeshFilter>();
            mf.sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = Geometry.CreateMaterial(color);
            return go;
        }

        static Vector3[] PyramidVerts(float b, float h)
        {
            return new Vector3[]
            {
                new Vector3(-b, -b, -b), new Vector3(b, -b, -b), new Vector3(b, b, -b), new Vector3(-b, b, -b),
                new Vector3(-b, -b, b), new Vector3(b, -b, b), new Vector3(b, b, b), new Vector3(-b, b, b),
            };
        }
    }

    public static class SphereBuilder
    {
        public static GameObject Create(GameObject parent, float radius, Color color)
        {
            var mesh = Geometry.UvSphere(radius, 8, 12);
            var go = new GameObject(parent.name + "_mesh");
            go.transform.SetParent(parent.transform);
            go.transform.localPosition = Vector3.zero;
            var mf = go.AddComponent<MeshFilter>();
            mf.sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = Geometry.CreateMaterial(color);
            return go;
        }
    }

    public static class QuadBuilder
    {
        public static Mesh Create(Vector3 a, Vector3 b, Vector3 c, Vector3 d, float extrude)
        {
            return Geometry.Quad(a, b, c, d, extrude);
        }
    }

    // Ejes locales de un elemento lineal, coherentes con el modelo:
    //   v1 = eje "vertical local" (perpendicular al eje del miembro, en el
    //        plano del miembro), v2 = eje transversal, axis = eje del miembro.
    public struct LocalAxes
    {
        public Vector3 Axis;   // direccion del miembro
        public Vector3 V1;     // eje local 1 (vertical del miembro / g1)
        public Vector3 V2;     // eje local 2 (transversal / g2)

        public static LocalAxes ForBeam(Vector3 p1, Vector3 p2)
        {
            var axis = (p2 - p1).normalized;
            // vigas horizontales: local z = +Z global (igual que OpenSees
            // transforms 2/3); v1 apunta vertical (mundo +Y), v2 transversal.
            Vector3 v1 = Vector3.up;
            Vector3 v2 = Vector3.Cross(axis, v1).normalized;
            v1 = Vector3.Cross(v2, axis).normalized;
            return new LocalAxes { Axis = axis, V1 = v1, V2 = v2 };
        }

        public static LocalAxes ForColumn(Vector3 p1, Vector3 p2)
        {
            var axis = (p2 - p1).normalized;
            Vector3 v2 = Vector3.Cross(axis, Vector3.forward).normalized;
            if (v2.sqrMagnitude < 0.01f) v2 = Vector3.Cross(axis, Vector3.right).normalized;
            Vector3 v1 = Vector3.Cross(v2, axis).normalized;
            return new LocalAxes { Axis = axis, V1 = v1, V2 = v2 };
        }
    }
}