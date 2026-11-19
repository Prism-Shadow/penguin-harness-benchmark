/** Public Unity/Puerts bridge ABI used by the standalone projects.
 * Type declarations only; runtime behavior comes from Unity and submitted C#.
 * Unity projects may regenerate a larger declaration set from their assemblies.
 */
declare namespace CS {
  interface $Ref<T> { value: T }
  interface $Task<T> { readonly Result: T }
  namespace System {
    class Type { readonly FullName: string; readonly Name: string }
    interface Action { Invoke(): void }
    interface Action$1<T> { Invoke(value: T): void }
    interface Action$2<T,U> { Invoke(first: T, second: U): void }
    interface Array<T> { readonly Length: number; get_Item(index: number): T }
  }
  namespace Puerts {
    class ScriptEnv { Tick(): void; Dispose(): void; Eval<T>(script: string): T }
  }
  namespace UnityEngine {
    class Object { name: string }
    class TextAsset extends Object { text: string }
    class Resources {
      static Load(path: string, type?: System.Type): Object | null;
      static LoadAll(path: string, type: System.Type): System.Array<Object>;
    }
  }
  namespace LLMAgent {
    class ScriptEnvBridge {
      static CreateJavaScriptEnv(): Puerts.ScriptEnv;
      static Eval(env: Puerts.ScriptEnv, script: string, onFinish: (value: string) => void): void;
      static EvalSync(env: Puerts.ScriptEnv, script: string): void;
      static Tick(env: Puerts.ScriptEnv): void;
      static ReleaseJavaScriptEnv(env?: Puerts.ScriptEnv): void;
    }
    class HttpBridge {
      static SendRequestAsync(url: string, method: string, headersJson: string, body: string, callback: (value: string) => void): void;
      static SendStreamRequestAsync(url: string, method: string, headersJson: string, body: string,
        onHeader: (value: string) => void, onChunk: (value: string) => void, onComplete: (value: string) => void): void;
      static CancelAllRequests(): void;
    }
    class UnityLogBridge {
      static GetLogSummary(): string;
      static GetRecentLogs(count: number, logType: string): string;
      static StartListening(): void;
      static StopListening(): void;
    }
    class TypeReflectionBridge {
      static GetAllNamespaces(): string;
      static GetTypesInNamespaces(namespacesComma: string): string;
      static GetTypeDetails(typeNamesComma: string): string;
    }
    class ScreenCaptureBridge {
      static CaptureScreenAsync(maxWidth: number, maxHeight: number, callback: (value: string) => void): void;
      static CaptureSceneViewAsync(maxWidth: number, maxHeight: number, callback: (value: string) => void): void;
      static GetSceneViewState(): string;
      static ManipulateSceneView(operation: string, direction: string, amount: number, callback: (value: string) => void): void;
      static GetGameObjectHierarchy(name: string, depth: number): string;
      static SelectGameObject(name: string): string;
      static SetSceneViewCamera(px: number, py: number, pz: number, setPivot: boolean, rx: number, ry: number, rz: number, setRotation: boolean, size: number): string;
      static FocusSceneViewOn(gameObjectName: string): string;
      static SaveScene(): string;
    }
  }
}
