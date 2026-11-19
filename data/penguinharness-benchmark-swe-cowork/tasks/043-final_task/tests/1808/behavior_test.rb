# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class TelemetryPrivacyProfileTest < Minitest::Test
  def test_system_profile_omits_platform_when_telemetry_is_disabled
    Stripe.enable_telemetry = false
    profile = Stripe::APIRequestor::SystemProfiler.user_agent

    assert_equal "ruby", profile[:lang]
    refute profile.key?(:platform)
    refute profile.key?(:hostname)
    refute profile.key?(:uname)
  ensure
    Stripe.enable_telemetry = false
  end
end
