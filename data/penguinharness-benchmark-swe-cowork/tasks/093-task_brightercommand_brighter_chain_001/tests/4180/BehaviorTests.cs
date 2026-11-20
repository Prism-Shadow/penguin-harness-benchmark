using Xunit;
public sealed class Node_4180_Behavior {
    [Fact(Timeout = 30000)] public async Task Public_contract_is_observable() => await ContractChecks.Run(4180);
}
