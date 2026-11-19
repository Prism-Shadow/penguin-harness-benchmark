using System;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text.Json;
using Puerts;
using PuertsMcp;
public static class McpHttpHost
{
    static readonly object OutputLock = new();
    static void Emit(object data) { lock (OutputLock) { Console.WriteLine(JsonSerializer.Serialize(data)); Console.Out.Flush(); } }
    static void Check(bool ok, string message) { if (!ok) throw new Exception(message); }
    static int Port() { var listener=new TcpListener(IPAddress.Loopback,0);listener.Start();int port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();return port; }
    static object Export(string name, Action<string,object,Action<bool,string>> initialize) => name switch {
        "onInitialize" => initialize,
        "onShutdown" => new Action(() => Emit(new {kind="shutdown"})),
        "handleHttpPost" => new Action<string,string,string,string>((context,method,body,session) => Emit(new {kind="post",context,method,body,session})),
        "handleHttpDelete" => new Action<string>(session => Emit(new {kind="delete",session})),
        _ => null
    };
    static int FailureControls() {
        foreach (string mode in new[]{"throw","missing-export","failure-callback","double-callback","late-callback"}) {
            int subscribers=UnityEditor.EditorApplication.UpdateSubscribers;
            int created=ScriptEnv.Created,disposed=ScriptEnv.Disposed,ready=0;bool success=true;Action<bool,string> late=null;
            ScriptEnv.FailModule=mode=="throw";
            ScriptEnv.Resolve=name=> mode=="missing-export" ? null : Export(name,(root,bridge,callback)=>{
                if(mode=="late-callback") late=callback;
                else { callback(false,"fixture initialization failure"); if(mode=="double-callback") callback(true,""); }
            });
            using var manager=new McpScriptManager();int port=Port();
            manager.Initialize("LLMAgent/editor-assistant",port,ok=>{ready++;success=ok;});
            if(mode=="late-callback") { manager.Shutdown();late(true,"");Check(!manager.IsInitialized,"late callback resurrected disposed manager"); }
            else { Check(ready==1 && !success,"initialization failure must report readiness false once"); Check(!manager.IsInitialized && !String.IsNullOrEmpty(manager.LastError),"initialization failure lost error state"); }
            Check(ScriptEnv.Created-created==ScriptEnv.Disposed-disposed,"initialization failure leaked ScriptEnv");
            int ticks=ScriptEnv.Ticks;UnityEditor.EditorApplication.Tick();Check(ScriptEnv.Ticks==ticks && ScriptEnv.DeadTouches==0 && UnityEditor.EditorApplication.UpdateSubscribers==subscribers,"failed initialization retained editor ticks");
            using var probe=new TcpListener(IPAddress.Loopback,port);probe.Start();probe.Stop();
            manager.Shutdown();
        }
        Console.WriteLine("production McpScriptManager failure, late callback, resource and subscription controls passed");return 0;
    }
    public static int Main(string[] arguments)
    {
        if(arguments.Length>0) return FailureControls();
        int port=Port();McpHttpServer server=null;Action<bool,string> onReady=null;
        ScriptEnv.ModuleLoaded=module=>Emit(new {kind="module",module});
        ScriptEnv.Resolve=name=>Export(name,(root,bridge,callback)=>{
            server=(McpHttpServer)bridge;onReady=callback;
            server.OnSseStreamOpened=()=>Emit(new {kind="stream"});
            Emit(new {kind="initialize",root});
        });
        using var manager=new McpScriptManager();
        manager.Initialize("LLMAgent/editor-assistant",port,ok=>Emit(new {kind="initialized",ok,error=manager.LastError}));
        Emit(new {kind="ready",port});
        string line;
        while ((line=Console.ReadLine())!=null) {
            using var doc=JsonDocument.Parse(line);var c=doc.RootElement;object result=null;
            try {
                string name=c.GetProperty("method").GetString();var args=c.GetProperty("args").EnumerateArray().ToArray();
                if(name=="Ready") onReady(args[0].GetBoolean(),args[1].GetString());
                else if(name=="EditorTick") UnityEditor.EditorApplication.Tick();
                else if(name=="Shutdown") manager.Shutdown();
                else if(name=="Stats") result=new {created=ScriptEnv.Created,disposed=ScriptEnv.Disposed,ticks=ScriptEnv.Ticks,deadTouches=ScriptEnv.DeadTouches,initialized=manager.IsInitialized};
                else {
                    var method=typeof(McpHttpServer).GetMethod(name);
                    method.Invoke(server,method.GetParameters().Select((p,i)=>p.ParameterType==typeof(int)?(object)args[i].GetInt32():args[i].GetString()).ToArray());
                }
                Emit(new {kind="ack",id=c.GetProperty("id").GetInt32(),result});
            }catch(Exception e){Emit(new{kind="error",error=(e.InnerException??e).ToString()});return 1;}
        }
        return 0;
    }
}
