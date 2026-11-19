using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var client = new SteamClient();
        var registered = new TestHandler();
        var differentInstance = new TestHandler();

        client.AddHandler(registered);
        client.RemoveHandler(differentInstance);

        Assert.Same(registered, client.GetHandler<TestHandler>());
    }

    private sealed class TestHandler : ClientMsgHandler
    {
        public override void HandleMsg(IPacketMsg packetMsg)
        {
        }
    }
}
