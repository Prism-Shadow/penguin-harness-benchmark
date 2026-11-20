using System.IO;
using System.Text;
using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        using var stream = new MemoryStream();
        stream.WriteNullTermString(null!, Encoding.Unicode);
        Assert.Equal(new byte[] { 0, 0 }, stream.ToArray());
    }
}
