using System;
using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var assembly = typeof(SteamClient).Assembly;

        Assert.Null(assembly.GetType("SteamKit2.SteamClient+CMListCallback"));
        Assert.DoesNotContain("ClientCMList", Enum.GetNames(typeof(EMsg)));
    }
}
