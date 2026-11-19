using System;
using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    private sealed class MarkerCallback : CallbackMsg
    {
    }

    [Fact]
    public void Contract()
    {
        var client = new SteamClient();
        var manager = new CallbackManager(client);
        IDisposable? victim = null;
        var removerCalled = false;

        using var remover = manager.Subscribe<MarkerCallback>(_ =>
        {
            removerCalled = true;
            victim!.Dispose();
        });
        victim = manager.Subscribe<MarkerCallback>(_ => { });

        client.PostCallback(new MarkerCallback());
        var run = typeof(CallbackManager).GetMethod("RunCallbacks", Type.EmptyTypes);
        Assert.NotNull(run);
        run.Invoke(manager, null);

        Assert.True(removerCalled);
    }
}
