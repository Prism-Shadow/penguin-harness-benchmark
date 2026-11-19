from integration.test_chains import test_real_factory_session_and_token_refresh as check


def test_public_behavior_988(dal_transport):
    check(dal_transport)
