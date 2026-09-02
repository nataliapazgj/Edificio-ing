using System;
using System.Collections.Generic;

namespace EdificioIng.Viewer
{
    // Esquema consumido: data/unity/edificio_lt2.json (exportado por
    // src/export_unity_model.py). Unity NO reinterpreta la geometria:
    // lee estos datos y los dibuja.
    //
    // Las unidades son metros (coinciden con el modelo estructural).
    // Mapeo de coordenadas al espacio de Unity (left-handed, Y up):
    //   Unity.x = modelo.x (planta)
    //   Unity.y = modelo.z (elevacion / nivel)
    //   Unity.z = modelo.y (planta)

    [Serializable]
    public class MetaData
    {
        public string model;
        public string generator;
        public string schema_version;
    }

    [Serializable]
    public class LevelData
    {
        public string name;
        public float z;
    }

    [Serializable]
    public class NodeData
    {
        public int tag;
        public float x;
        public float y;
        public float z;
        public string level;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2 (backward compatible)
    }

    [Serializable]
    public class MasterNodeData
    {
        public int tag;
        public string master_id;
        public string level;
        public float x;
        public float y;
        public float z;
        public string tower;
    }

    [Serializable]
    public class BeamData
    {
        public string beam_id;
        public int elementTag;
        public string level;
        public string section;
        public int node_i;
        public int node_j;
        public float length_m;
        // Datos de area tributaria (BLOQUE 3/4B) cuando aplica; si
        // load_status == "NO_TRIBUTARY_AREA" no corresponden.
        public float tributary_area_m2;
        public float slab_load_kN;
        public float equivalent_uniform_kN_m;
        public string load_status;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2
    }

    [Serializable]
    public class ColumnData
    {
        public string column_id;
        public string parent_id;
        public int elementTag;
        public string section;
        public string from_level;
        public string to_level;
        public int node_i;
        public int node_j;
        public float x;
        public float y;
        public float length_m;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2
    }

    [Serializable]
    public class WallNodesData
    {
        public int bottom_i;
        public int bottom_j;
        public int top_i;
        public int top_j;
    }

    [Serializable]
    public class WallData
    {
        public string wall_id;
        public string parent_id;
        public float thickness_m;
        public string from_level;
        public string to_level;
        public WallNodesData nodes;
        public string status;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2
    }

    [Serializable]
    public class SupportData
    {
        public string support_id;
        public int tag;
        public string level;
        public float x;
        public float y;
        public float z;
        public int ux;
        public int uy;
        public int uz;
        public int rx;
        public int ry;
        public int rz;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2
    }

    [Serializable]
    public class DiaphragmData
    {
        public string diaphragm_id;
        public string level;
        public string master_id;
        public int master_tag;
        public int[] slave_tags;
        public int slave_count;
        public string tower;   // "LT1" | "LT2"; null/empty => LT2
    }

    // Losa QA (representacion, NO elemento estructural). polygon/holes son
    // cadenas 'x,y;x,y;...' en planta (modelo x,y).
    [Serializable]
    public class SlabData
    {
        public string panel_id;
        public string level;
        public float z;
        public string polygon;
        public string[] holes;
        public float area_m2;
        public float thickness_m;
        public float qG_kN_m2;
        public string status;
        public string hole_status;
    }

    [Serializable]
    public class ModelData
    {
        public MetaData meta;
        public LevelData[] levels;
        public NodeData[] nodes;
        public MasterNodeData[] master_nodes;
        public BeamData[] beams;
        public ColumnData[] columns;
        public WallData[] walls;
        public SupportData[] supports;
        public DiaphragmData[] diaphragms;
        public SlabData[] slabs;
    }

    // Dato identificado por seleccion.
    public sealed class SelectableInfo
    {
        public string category;   // beam | column | wall | node | support | master
        public string id;         // id estructural
        public string label;
        public string extra;
    }
}