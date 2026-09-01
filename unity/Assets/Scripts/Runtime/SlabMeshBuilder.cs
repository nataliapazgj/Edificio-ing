using System;
using System.Collections.Generic;
using UnityEngine;

namespace EdificioIng.Viewer
{
    // Representacion QA de las losas: descomposicion del rectangulo exterior
    // menos los holes en una cobertura exacta de rectangulos, triangulada como
    // quads (2 triangulos) en el plano XZ a Y=z. Robusto ante holes que tocan
    // el borde del poligono (casos degenerados de escaleras y claraboyas LT2).
    // Solo uso visual; NO modifica la geometria fuente.
    public static class SlabMeshBuilder
    {
        const double Eps = 1e-9;

        public static Mesh Build(List<Vector2> exterior, List<List<Vector2>> holes,
            float z)
        {
            // 1) Rectangulo exterior (bounding box del ring exterior).
            if (exterior == null || exterior.Count < 3) return null;
            RectD outer = BoundingRect(exterior);

            // 2) Rectangulos de los holes.
            var holeRects = new List<RectD>();
            if (holes != null)
            {
                foreach (var h in holes)
                    if (h != null && h.Count >= 3)
                        holeRects.Add(BoundingRect(h));
            }

            // 3) Descomposicion en rectangulos de cobertura exacta.
            var rects = Decompose(outer, holeRects);
            if (rects.Count == 0) return null;

            // 4) Triangulos: cada rectangulo -> 2 triangulos, 4 vertices.
            var verts = new List<Vector3>();
            var tris = new List<int>();
            var uvs = new List<Vector2>();
            var normals = new List<Vector3>();
            foreach (var r in rects)
            {
                int i0 = verts.Count;
                float x0 = (float)r.X0, y0 = (float)r.Y0;
                float x1 = (float)r.X1, y1 = (float)r.Y1;
                verts.Add(new Vector3(x0, z, y0));
                verts.Add(new Vector3(x1, z, y0));
                verts.Add(new Vector3(x1, z, y1));
                verts.Add(new Vector3(x0, z, y1));
                uvs.Add(new Vector2(x0, y0));
                uvs.Add(new Vector2(x1, y0));
                uvs.Add(new Vector2(x1, y1));
                uvs.Add(new Vector2(x0, y1));
                for (int k = 0; k < 4; k++)
                {
                    normals.Add(Vector3.up);
                }
                tris.Add(i0 + 0); tris.Add(i0 + 1); tris.Add(i0 + 2);
                tris.Add(i0 + 0); tris.Add(i0 + 2); tris.Add(i0 + 3);
            }

            var mesh = new Mesh();
            mesh.vertices = verts.ToArray();
            mesh.triangles = tris.ToArray();
            mesh.normals = normals.ToArray();
            mesh.uv = uvs.ToArray();
            return mesh;
        }

        // ---------------- descomposicion ----------------

        struct RectD
        {
            public double X0, Y0, X1, Y1;
            public RectD(double x0, double y0, double x1, double y1)
            { X0 = x0; Y0 = y0; X1 = x1; Y1 = y1; }
            public double Area { get { return (X1 - X0) * (Y1 - Y0); } }
        }

        static RectD BoundingRect(List<Vector2> ring)
        {
            double x0 = double.MaxValue, y0 = double.MaxValue;
            double x1 = double.MinValue, y1 = double.MinValue;
            foreach (var p in ring)
            {
                if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x;
                if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
            }
            return new RectD(x0, y0, x1, y1);
        }

        static List<RectD> Decompose(RectD outer, List<RectD> holes)
        {
            var ys = new SortedSet<double> { outer.Y0, outer.Y1 };
            foreach (var h in holes) { ys.Add(h.Y0); ys.Add(h.Y1); }
            var ysList = new List<double>(ys);

            var result = new List<RectD>();
            for (int i = 0; i < ysList.Count - 1; i++)
            {
                double y0 = ysList[i], y1 = ysList[i + 1];
                if (y1 - y0 <= Eps) continue;
                // Intervalos x dentro de la franja Y.
                var segs = new List<Interval> { new Interval(outer.X0, outer.X1) };
                foreach (var h in holes)
                {
                    if (h.Y0 <= y0 + Eps && y1 <= h.Y1 + Eps)
                        segs = SubtractX(segs, h.X0, h.X1);
                }
                foreach (var s in segs)
                    if (s.B - s.A > Eps)
                        result.Add(new RectD(s.A, y0, s.B, y1));
            }
            return result;
        }

        struct Interval
        {
            public double A, B;
            public Interval(double a, double b) { A = a; B = b; }
        }

        static List<Interval> SubtractX(List<Interval> segs, double h0, double h1)
        {
            var next = new List<Interval>();
            foreach (var s in segs)
            {
                if (h1 <= s.A + Eps || h0 >= s.B - Eps)
                {
                    next.Add(s);              // hole no toca este intervalo
                }
                else if (h0 <= s.A + Eps && h1 >= s.B - Eps)
                {
                    // hole cubre todo; se elimina
                }
                else if (h0 <= s.A + Eps)
                {
                    next.Add(new Interval(h1, s.B));
                }
                else if (h1 >= s.B - Eps)
                {
                    next.Add(new Interval(s.A, h0));
                }
                else
                {
                    next.Add(new Interval(s.A, h0));
                    next.Add(new Interval(h1, s.B));
                }
            }
            return next;
        }
    }
}