using System.Collections;
using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Microsoft.Extensions.Hosting;

var observer = new ModelObserver(args[1]);
using var subscription = DiagnosticListener.AllListeners.Subscribe(observer);
try
{
    var assembly = Assembly.LoadFrom(args[0]);
    ServiceContract.Observe(args[0], args[1] + ".services.json");
    var hostArguments = args.Length > 2 && args[2] == "run" ? Array.Empty<string>() : new[] { "--publisher", "manifest", "--output-path", args[1] + ".manifest.json" };
    var result = assembly.EntryPoint!.Invoke(null, [hostArguments]);
    if (result is Task task) await task;
}
catch (Exception error) when (observer.Captured && (error is StopHostException || error.InnerException is StopHostException)) { }
if (!observer.Captured)
{
    Console.Error.WriteLine("infrastructure_error: production AppHost did not expose a HostBuilt model");
    return 2;
}
return 0;

sealed class StopHostException : Exception { }

static class ServiceContract
{
    // Inspect project assemblies from the built application's dependency graph.
    // This accepts different namespaces, source files, and static properties as
    // well as fields, while excluding unrelated package types with this name.
    public static void Observe(string application, string output)
    {
        using var dependencies = JsonDocument.Parse(File.ReadAllText(Path.ChangeExtension(application, ".deps.json")));
        var libraries = dependencies.RootElement.GetProperty("libraries");
        var assemblies = new HashSet<string> { Path.GetFullPath(application) };
        foreach (var target in dependencies.RootElement.GetProperty("targets").EnumerateObject())
        foreach (var library in target.Value.EnumerateObject())
        {
            if (!libraries.TryGetProperty(library.Name, out var metadata) ||
                metadata.GetProperty("type").GetString() != "project" ||
                !library.Value.TryGetProperty("runtime", out var runtime)) continue;
            foreach (var asset in runtime.EnumerateObject())
            {
                if (!asset.Name.EndsWith(".dll", StringComparison.OrdinalIgnoreCase)) continue;
                var path = Path.Combine(Path.GetDirectoryName(application)!, Path.GetFileName(asset.Name));
                if (File.Exists(path)) assemblies.Add(path);
            }
        }
        string[] names = ["WebFrontend", "WebApi", "DatabaseServer", "Database"];
        var contracts = new List<object>();
        foreach (var path in assemblies)
        foreach (var type in Assembly.LoadFrom(path).GetExportedTypes().Where(type => type.Name == "Services"))
        {
            var values = new Dictionary<string, string?>();
            foreach (var name in names)
            {
                const BindingFlags flags = BindingFlags.Public | BindingFlags.Static;
                var field = type.GetField(name, flags);
                var property = type.GetProperty(name, flags);
                values[name] = field != null ? field.GetValue(null) as string :
                    property?.GetIndexParameters().Length == 0 ? property.GetValue(null) as string : null;
            }
            contracts.Add(new { assembly = Path.GetFileName(path), type = type.FullName, values });
        }
        File.WriteAllText(output, JsonSerializer.Serialize(contracts, new JsonSerializerOptions { WriteIndented = true }));
    }
}

sealed class ModelObserver(string output) : IObserver<DiagnosticListener>, IObserver<KeyValuePair<string, object?>>
{
    public bool Captured { get; private set; }
    public void OnNext(DiagnosticListener listener)
    {
        if (listener.Name == "Microsoft.Extensions.Hosting") listener.Subscribe(this);
    }
    public void OnNext(KeyValuePair<string, object?> notification)
    {
        if (notification.Key != "HostBuilt" || notification.Value is not IHost host) return;
        var modelType = AppDomain.CurrentDomain.GetAssemblies().Select(assembly => assembly.GetType("Aspire.Hosting.ApplicationModel.DistributedApplicationModel")).FirstOrDefault(type => type != null);
        if (modelType == null) throw new InvalidOperationException("infrastructure_error: no DistributedApplicationModel type at HostBuilt; refusing resource startup");
        var model = host.Services.GetService(modelType);
        if (model == null) throw new InvalidOperationException("infrastructure_error: no DistributedApplicationModel service at HostBuilt; refusing resource startup");
        var resources = (IEnumerable)modelType.GetProperty("Resources")!.GetValue(model)!;
        var rows = new List<object>();
        foreach (var resource in resources)
        {
            var annotations = (IEnumerable)resource.GetType().GetProperty("Annotations")!.GetValue(resource)!;
            var edges = new List<object>();
            foreach (var annotation in annotations)
            {
                var target = annotation.GetType().GetProperty("Resource")?.GetValue(annotation);
                edges.Add(new
                {
                    type = annotation.GetType().Name,
                    target = target?.GetType().GetProperty("Name")?.GetValue(target)?.ToString(),
                    relationship = annotation.GetType().GetProperty("Type")?.GetValue(annotation)?.ToString(),
                    waitType = annotation.GetType().GetProperty("WaitType")?.GetValue(annotation)?.ToString(),
                    properties = annotation.GetType().GetProperties().Select(property => new { name = property.Name, type = property.PropertyType.FullName }).ToArray()
                });
            }
            var hierarchy = new List<string?>();
            for (var resourceType = resource.GetType(); resourceType != null; resourceType = resourceType.BaseType) hierarchy.Add(resourceType.FullName);
            rows.Add(new
            {
                name = resource.GetType().GetProperty("Name")!.GetValue(resource),
                type = resource.GetType().FullName,
                hierarchy,
                interfaces = resource.GetType().GetInterfaces().Select(contract => contract.FullName).ToArray(),
                annotations = edges
            });
        }
        File.WriteAllText(output, JsonSerializer.Serialize(rows, new JsonSerializerOptions { WriteIndented = true }));
        Captured = true;
        throw new StopHostException();
    }
    public void OnCompleted() { }
    public void OnError(Exception error) => throw error;
}
