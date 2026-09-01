using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace EdificioIng.Viewer.EditorTools
{
    // Construye y guarda la escena del viewer (Assets/Scenes/Edificio.unity).
    // Se ejecuta desde Unity (menu EdificioIng/Build Scene) o en batchmode:
    //   Unity -batchmode -projectPath unity -executeMethod
    //   EdificioIng.Viewer.EditorTools.BootSceneGenerator.BuildScene -quit
    public static class BootSceneGenerator
    {
        public const string ScenePath = "Assets/Scenes/Edificio.unity";

        [MenuItem("EdificioIng/Build Scene")]
        public static void BuildSceneMenu()
        {
            BuildScene();
            Debug.Log("Viewer scene built: " + ScenePath);
        }

        public static void BuildScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,
                NewSceneMode.Single);

            // Luces de preview para no ver todo negro.
            var lightGo = new GameObject("Directional Light");
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0);
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.1f;
            light.shadows = LightShadows.None;

            // Vista inicial de la camara (ViewerBoot la ajusta con FrameAll).
            var cam = SceneViewUtils.CreateCamera();

            // Boot principal.
            var boot = new GameObject("ViewerBoot");
            boot.AddComponent<ViewerBoot>();

            EnsureFolders();
            EditorSceneManager.SaveScene(scene, ScenePath);
        }

        static void EnsureFolders()
        {
            if (!AssetDatabase.IsValidFolder("Assets/Scenes"))
                AssetDatabase.CreateFolder("Assets", "Scenes");
        }

        static class SceneViewUtils
        {
            public static GameObject CreateCamera()
            {
                var camObj = new GameObject("Main Camera");
                camObj.tag = "MainCamera";
                var cam = camObj.AddComponent<Camera>();
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.12f, 0.12f, 0.14f);
                cam.nearClipPlane = 0.1f;
                cam.farClipPlane = 1000f;
                camObj.AddComponent<AudioListener>();
                return camObj;
            }
        }
    }
}