using UnityEngine;

namespace EdificioIng.Viewer
{
    // Almacena los ejes locales de un elemento lineal para mostrarlos cuando
    // se activa el toggle "Local Axes".
    public sealed class LocalAxesHost : MonoBehaviour
    {
        public LocalAxes Axes { get; private set; }
        public bool HasAxes { get; private set; }
        public Vector3 MemberCenter;

        public void Set(LocalAxes axes)
        {
            Axes = axes;
            HasAxes = true;
        }
    }
}