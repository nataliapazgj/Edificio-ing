using UnityEngine;

namespace EdificioIng.Viewer
{
    // Camara orbital: arrastrar con boton izquierdo orbita; rueda hace zoom;
    // boton derecho (o boton central) arrastra/pan; doble click o tecla F
    // recientra (Frame All). Use que la rotacion no dependa de la escala
    // del mundo: se maneja con distancia desde un foco.
    [RequireComponent(typeof(Camera))]
    public sealed class OrbitCamera : MonoBehaviour
    {
        public Transform focus;         // punto hacia el que orbita
        public float distance = 60f;
        public float minDistance = 2f;
        public float maxDistance = 400f;
        public float yaw = 45f;
        public float pitch = -35f;
        public float panSpeed = 0.02f;
        public float zoomSpeed = 8f;

        Camera _cam;
        Vector3 _focusPoint;

        void Awake()
        {
            _cam = GetComponent<Camera>();
            if (focus != null) _focusPoint = focus.position;
        }

        public void SetFocus(Vector3 p, float d)
        {
            _focusPoint = p;
            distance = Mathf.Clamp(d, minDistance, maxDistance);
            Apply();
        }

        public void FrameAll(Bounds bounds)
        {
            _focusPoint = bounds.center;
            distance = Mathf.Clamp(bounds.extents.magnitude * 1.8f,
                minDistance, maxDistance);
            pitch = -28f;
            yaw = 45f;
            Apply();
        }

        void LateUpdate()
        {
            float dt = Time.deltaTime;
            // Orbita con boton izquierdo
            if (Input.GetMouseButton(0))
            {
                float dx = Input.GetAxis("Mouse X");
                float dy = Input.GetAxis("Mouse Y");
                yaw += dx * 120f * dt * 3f;
                pitch -= dy * 120f * dt * 3f;
                pitch = Mathf.Clamp(pitch, -89f, 89f);
            }
            // Zoom con rueda
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 1e-4f)
            {
                distance -= scroll * zoomSpeed * distance * 0.1f;
                distance = Mathf.Clamp(distance, minDistance, maxDistance);
            }
            // Pan con boton derecho o central
            if (Input.GetMouseButton(1) || Input.GetMouseButton(2))
            {
                float dx = Input.GetAxis("Mouse X");
                float dy = Input.GetAxis("Mouse Y");
                Vector3 right = _cam.transform.right;
                Vector3 up = _cam.transform.up;
                _focusPoint -= right * dx * distance * panSpeed;
                _focusPoint -= up * -dy * distance * panSpeed;
            }
            // Frame All / recentrar con tecla F
            if (Input.GetKeyDown(KeyCode.F))
            {
                var roi = ViewerBoot.RoiBounds;
                if (roi.HasValue) FrameAll(roi.Value);
            }

            Apply();
        }

        void Apply()
        {
            Quaternion rot = Quaternion.Euler(pitch, yaw, 0);
            Vector3 dir = rot * Vector3.forward;
            _cam.transform.rotation = rot;
            _cam.transform.position = _focusPoint - dir * distance;
        }
    }
}