using System;
using SteamKit2;
using SteamKit2.Internal;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var response = new CMsgClientPICSProductInfoResponse
        {
            http_host = "content.example.test",
            http_min_size = 8,
        };
        var app = new CMsgClientPICSProductInfoResponse.AppInfo
        {
            appid = 440,
            size = 16,
            sha = new byte[] { 0x01, 0xA2, 0xFF },
        };

        var info = new SteamApps.PICSProductInfoCallback.PICSProductInfo(response, app);

        Assert.True(info.UseHttp);
        Assert.Equal(
            new Uri("http://content.example.test/appinfo/440/sha/01a2ff.txt.gz"),
            info.HttpUri);
    }
}
