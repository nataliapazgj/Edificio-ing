using UnityEngine;

namespace EdificioIng.Viewer
{
    // Componente adosado a cada elemento dibujable. Guarda su informacion
    // para el panel de seleccion.
    public sealed class Selectable : MonoBehaviour
    {
        public SelectableInfo Data { get; private set; }
        public LocalAxesHost LocalHost;

        public void Set(SelectableInfo info)
        {
            Data = info;
            if (LocalHost == null)
                LocalHost = GetComponent<LocalAxesHost>();
        }

        void Awake()
        {
            LocalHost = GetComponent<LocalAxesHost>();
        }

        void Reset()
        {
            LocalHost = GetComponent<LocalAxesHost>();
        }
    }
}