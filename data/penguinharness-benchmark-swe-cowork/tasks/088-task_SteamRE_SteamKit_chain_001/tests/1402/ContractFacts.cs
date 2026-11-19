using System.Net;
using SteamKit2;
using SteamKit2.Discovery;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var configuration = SteamConfiguration.Create(builder =>
            builder.WithDirectoryFetch(false));
        var list = new SmartCMServerList(configuration);
        var first = ServerRecord.CreateSocketServer(
            new IPEndPoint(IPAddress.Parse("127.0.0.1"), 27015));
        var second = ServerRecord.CreateSocketServer(
            new IPEndPoint(IPAddress.Parse("127.0.0.2"), 27016));
        list.ReplaceList(new[] { first, second });

        var candidate = list.GetNextServerCandidate(ProtocolTypes.Tcp);

        Assert.NotNull(candidate);
        Assert.Equal(first.EndPoint, candidate.EndPoint);
        Assert.Equal(ProtocolTypes.Tcp, candidate.ProtocolTypes);
    }
}
