using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using SteamKit2.Discovery;

namespace Tests;

internal sealed class DirectoryHandler : HttpMessageHandler
{
    public int Requests { get; private set; }
    public HttpRequestMessage? LastRequest { get; private set; }
    public string Body { get; set; } = Response("fresh.example.test:27019");
    public string JsonBody { get; set; } = JsonResponse("fresh.example.test:27019");
    public HttpStatusCode Status { get; set; } = HttpStatusCode.OK;

    public static string Response(string? endpoint) => endpoint == null
        ? "\"response\" { \"success\" \"1\" \"serverlist\" { } }"
        : "\"response\" { \"success\" \"1\" \"serverlist\" { \"0\" { \"type\" \"netfilter\" \"endpoint\" \"" + endpoint + "\" } } }";

    public static string JsonResponse(string? endpoint) => JsonSerializer.Serialize(new
    {
        response = new
        {
            success = true,
            serverlist = endpoint == null ? Array.Empty<object>()
                : new object[] { new { type = "netfilter", endpoint } },
        },
    });

    public void SetEndpoint(string? endpoint)
    {
        Body = Response(endpoint);
        JsonBody = JsonResponse(endpoint);
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Requests++;
        LastRequest = request;
        // Steam Web API defaults to JSON. The native WebAPI helper explicitly
        // requests VDF; a direct HttpClient implementation may use default JSON.
        var format = request.RequestUri!.Query.TrimStart('?').Split('&')
            .Select(part => part.Split('=', 2))
            .Where(parts => Uri.UnescapeDataString(parts[0]) == "format")
            .Select(parts => parts.Length == 2 ? Uri.UnescapeDataString(parts[1]) : "")
            .LastOrDefault() ?? "json";
        if (format != "json" && format != "vdf")
            throw new InvalidOperationException("Directory test service supports JSON and VDF response formats");
        return Task.FromResult(new HttpResponseMessage(Status)
        {
            Content = new StringContent(format == "vdf" ? Body : JsonBody, Encoding.UTF8,
                                        format == "vdf" ? "text/plain" : "application/json"),
        });
    }
}

internal sealed class DatedProvider : IServerListProvider
{
    public DateTime LastServerListRefresh { get; set; }
    public ServerRecord[] Records { get; set; } = Array.Empty<ServerRecord>();
    public int Updates { get; private set; }
    public Task<IEnumerable<ServerRecord>> FetchServerListAsync() => Task.FromResult<IEnumerable<ServerRecord>>(Records);
    public Task UpdateServerListAsync(IEnumerable<ServerRecord> endpoints)
    {
        Updates++;
        Records = endpoints.ToArray();
        LastServerListRefresh = DateTime.UtcNow;
        return Task.CompletedTask;
    }
}
