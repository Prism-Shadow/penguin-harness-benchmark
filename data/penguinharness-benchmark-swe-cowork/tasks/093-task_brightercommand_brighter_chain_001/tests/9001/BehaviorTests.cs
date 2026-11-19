using Xunit;
public sealed class Node_9001_Behavior {
    [Fact(Timeout = 30000)] public async Task Existing_message_shape_remains_usable() => await ContractChecks.Run(9001);
}
