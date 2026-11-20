from integration.test_chains import test_real_builder_auth_retry as check


def test_public_behavior_1445(dal_transport):
    check(dal_transport, "PGRST301", "invalid token", True)
