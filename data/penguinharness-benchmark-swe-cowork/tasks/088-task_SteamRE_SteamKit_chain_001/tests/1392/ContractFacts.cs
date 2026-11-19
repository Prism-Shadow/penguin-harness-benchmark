using System;
using System.Reflection;
using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var assembly = typeof(SteamClient).Assembly;
        var tradingType = assembly.GetType("SteamKit2.SteamTrading");

        if (tradingType is not null)
        {
            var client = new SteamClient();
            var getHandler = typeof(SteamClient)
                .GetMethod("GetHandler", BindingFlags.Instance | BindingFlags.Public)!
                .MakeGenericMethod(tradingType);
            Assert.Null(getHandler.Invoke(client, null));
        }

        Assert.Null(tradingType);
    }
}
