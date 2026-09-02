using UnityEngine;

/// <summary>
/// Camara de orbita simple para QA estructural.
/// Controles:
///   - Boton derecho + arrastrar: orbitar
///   - Boton medio + arrastrar: pan / desplazamiento
///   - Rueda del raton: zoom
///   - Tecla F (o boton en UI): volver a la vista general
/// </summary>
public class CameraController : MonoBehaviour {

    Vector3 target = Vector3.zero;
    float yaw = 45f;
    float pitch = 25f;
    float dist = 90f;
    Vector3 targetInit; float distInit;
    bool inited = false;

    public void Init(Vector3 center, float distance) {
        target = center;
        dist = distance;
        targetInit = center;
        distInit = distance;
        inited = true;
        Apply();
    }

    public void ResetView() {
        if (!inited) return;
        target = targetInit;
        dist = distInit;
        Apply();
    }

    void Update() {
        if (!inited) return;

        if (Input.GetMouseButton(1)) {
            yaw += Input.GetAxis("Mouse X") * 0.6f;
            pitch -= Input.GetAxis("Mouse Y") * 0.6f;
            pitch = Mathf.Clamp(pitch, -89f, 89f);
        }
        if (Input.GetMouseButton(2)) {
            float s = dist * 0.0018f;
            target -= transform.right * Input.GetAxis("Mouse X") * s;
            target -= transform.up   * Input.GetAxis("Mouse Y") * s;
        }
        float sc = Input.GetAxis("Mouse ScrollWheel");
        if (Mathf.Abs(sc) > 0.0001f) {
            dist *= 1f - sc * 0.12f;
            dist = Mathf.Clamp(dist, 2f, 1200f);
        }
        if (Input.GetKeyDown(KeyCode.F)) ResetView();

        Apply();
    }

    void Apply() {
        Quaternion rot = Quaternion.Euler(pitch, yaw, 0f);
        transform.position = target + rot * (Vector3.back * dist);
        transform.LookAt(target);
    }
}