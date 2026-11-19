using System;
using System.IO;
using SteamKit2;
using Xunit;

namespace Tests;

public sealed class ContractFacts
{
    [Fact]
    public void Contract()
    {
        var expected = new byte[] { 3, 1, 4, 1, 5, 9, 2, 6 };
        using var stream = new FragmentedStream(expected);
        var buffer = new byte[expected.Length];

        var count = stream.ReadAll(buffer);

        Assert.Equal(expected.Length, count);
        Assert.Equal(expected, buffer);
    }

    private sealed class FragmentedStream : MemoryStream
    {
        public FragmentedStream(byte[] bytes) : base(bytes)
        {
        }

        public override int Read(byte[] buffer, int offset, int count)
        {
            return base.Read(buffer, offset, Math.Min(2, count));
        }

        public override int Read(Span<byte> buffer)
        {
            return base.Read(buffer[..Math.Min(2, buffer.Length)]);
        }
    }
}
