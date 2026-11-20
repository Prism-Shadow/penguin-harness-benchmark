using Xunit;
public sealed class Node_4040_Behavior {
    [Fact(Timeout = 30000)] public async Task Public_contract_is_observable() => await ContractChecks.Run(4040);
}
