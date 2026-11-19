using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var configuration = SteamConfiguration.Create(_ => { });

        Assert.Equal(
            ProtocolTypes.Tcp | ProtocolTypes.WebSocket,
            configuration.ProtocolTypes);
        Assert.True(configuration.ProtocolTypes.HasFlag(ProtocolTypes.Tcp));
        Assert.True(configuration.ProtocolTypes.HasFlag(ProtocolTypes.WebSocket));
        Assert.False(configuration.ProtocolTypes.HasFlag(ProtocolTypes.Udp));
    }
}
