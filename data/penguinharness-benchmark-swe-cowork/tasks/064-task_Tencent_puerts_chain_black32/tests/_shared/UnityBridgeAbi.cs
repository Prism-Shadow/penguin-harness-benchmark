using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;

namespace UnityEngine
{
    public enum LogType { Error, Assert, Warning, Log, Exception }
    public static class Application
    {
        public delegate void LogCallback(string message, string trace, LogType type);
        public static event LogCallback logMessageReceived;
        public static void Emit(string message, LogType type = LogType.Log) => logMessageReceived?.Invoke(message, "abi-stack", type);
    }
    public static class Debug
    {
        public static void Log(object message) => Application.Emit(message?.ToString());
        public static void LogWarning(object message) => Application.Emit(message?.ToString(), LogType.Warning);
        public static void LogError(object message) => Application.Emit(message?.ToString(), LogType.Error);
    }
    public static class Time { public static float realtimeSinceStartup; }
}
namespace UnityEngine.Scripting
{
    public sealed class PreserveAttribute : Attribute { }
}
namespace UnityEditor
{
    public sealed class InitializeOnLoadMethodAttribute : Attribute { }
    public sealed class InitializeOnLoadAttribute : Attribute { }
    public static class EditorApplication
    {
        public static event Action update;
        public static event Action quitting;
        public static int UpdateSubscribers => update?.GetInvocationList().Length ?? 0;
        public static void Tick() => update?.Invoke();
        public static void Quit() => quitting?.Invoke();
        public static void Load()
        {
            foreach (var type in Assembly.GetExecutingAssembly().GetTypes())
            {
                if (type.IsDefined(typeof(InitializeOnLoadAttribute)))
                    System.Runtime.CompilerServices.RuntimeHelpers.RunClassConstructor(type.TypeHandle);
                foreach (var method in type.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
                    if (method.IsDefined(typeof(InitializeOnLoadMethodAttribute))) method.Invoke(null, null);
            }
        }
    }
}
namespace UnityEngine.Networking
{
    public class DownloadHandler : IDisposable
    {
        protected readonly List<byte> received = new List<byte>();
        public virtual string text => Encoding.UTF8.GetString(received.ToArray());
        public byte[] data => received.ToArray();
        protected virtual bool ReceiveData(byte[] data, int length)
        {
            received.AddRange(data.Take(length));
            return true;
        }
        protected virtual void CompleteContent() { }
        protected virtual float GetProgress() => 0;
        public bool Feed(byte[] data) => ReceiveData(data, data.Length);
        public void Finish() => CompleteContent();
        public virtual void Dispose() { }
    }
    public class DownloadHandlerBuffer : DownloadHandler { }
    public class DownloadHandlerScript : DownloadHandler
    {
        public DownloadHandlerScript() { }
        public DownloadHandlerScript(byte[] buffer) { }
    }
    public class UploadHandler : IDisposable { public virtual void Dispose() { } }
    public class UploadHandlerRaw : UploadHandler
    {
        public byte[] data;
        public UploadHandlerRaw(byte[] bytes) { data = bytes; }
    }
    public class UnityWebRequestAsyncOperation
    {
        public UnityWebRequest webRequest;
        public bool isDone;
    }
    public class UnityWebRequest : IDisposable
    {
        public enum Result { InProgress, Success, ConnectionError, ProtocolError, DataProcessingError }
        public static readonly List<UnityWebRequest> Requests = new List<UnityWebRequest>();
        public string url, method, error;
        public long responseCode;
        public int timeout, DisposeCount, AbortCount;
        public Result result = Result.InProgress;
        public DownloadHandler downloadHandler;
        public UploadHandler uploadHandler;
        public readonly Dictionary<string, string> RequestHeaders = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public readonly Dictionary<string, string> ResponseHeaders = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public UnityWebRequestAsyncOperation Operation;
        public bool isDone => Operation?.isDone == true;
        public UnityWebRequest(string address, string verb) { url = address; method = verb; Requests.Add(this); }
        public static UnityWebRequest Get(string url) => new UnityWebRequest(url, "GET") { downloadHandler = new DownloadHandlerBuffer() };
        public static UnityWebRequest Head(string url) => new UnityWebRequest(url, "HEAD");
        public static UnityWebRequest Delete(string url) => new UnityWebRequest(url, "DELETE");
        public void SetRequestHeader(string name, string value) => RequestHeaders[name] = value;
        public Dictionary<string, string> GetResponseHeaders() => ResponseHeaders;
        public string GetResponseHeader(string name) => ResponseHeaders.TryGetValue(name, out var value) ? value : null;
        public UnityWebRequestAsyncOperation SendWebRequest() => Operation = new UnityWebRequestAsyncOperation { webRequest = this };
        public void Feed(byte[] bytes)
        {
            if (DisposeCount > 0 || isDone) return;
            if (responseCode == 0) responseCode = 200;
            ResponseHeaders["content-type"] = "text/event-stream";
            if (downloadHandler != null && !downloadHandler.Feed(bytes)) End("download-rejected");
        }
        public void End(string failure = null)
        {
            if (DisposeCount > 0 || isDone) return;
            error = failure;
            result = failure == null ? Result.Success : Result.ConnectionError;
            if (responseCode == 0 && failure == null) responseCode = 200;
            downloadHandler?.Finish();
            Operation.isDone = true;
        }
        public void Abort() { AbortCount++; End("aborted"); }
        public void Dispose() { DisposeCount++; downloadHandler?.Dispose(); uploadHandler?.Dispose(); }
    }
}
