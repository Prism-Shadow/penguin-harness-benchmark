from integration.test_chains import test_real_writes_and_rpc as check


def test_public_behavior_1100(dal_transport):
    check(dal_transport, "acct-b", "west", 0, 11)
