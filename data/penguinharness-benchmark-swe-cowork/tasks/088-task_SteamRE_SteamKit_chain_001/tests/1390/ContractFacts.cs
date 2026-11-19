using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var callback = new SteamUser.LoggedOnCallback(EResult.AccountLogonDenied);

        Assert.Equal(EResult.AccountLogonDenied, callback.Result);
        Assert.Equal(JobID.Invalid, callback.JobID);
    }
}
