from integration.test_chains import test_node_payload_uses_database_identity as check


def test_public_behavior_1008(dal_transport):
    check(dal_transport)
