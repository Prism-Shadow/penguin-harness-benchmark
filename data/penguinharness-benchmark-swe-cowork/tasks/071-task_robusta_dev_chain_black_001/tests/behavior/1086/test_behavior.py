from integration.test_chains import test_real_writes_and_rpc as check


def test_public_behavior_1086(dal_transport):
    check(dal_transport, "acct-a", "east", 3, 7)
