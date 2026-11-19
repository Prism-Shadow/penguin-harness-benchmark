# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "tmpdir"

class AnonymousTelemetryIdentityTest < Minitest::Test
  def test_enabled_telemetry_includes_one_nonempty_anonymous_identity
    previous_xdg = ENV["XDG_CONFIG_HOME"]
    Dir.mktmpdir do |dir|
      ENV["XDG_CONFIG_HOME"] = dir
      Stripe::TelemetryId.reset! if defined?(Stripe::TelemetryId)
      Stripe.enable_telemetry = true
      profile = Stripe::APIRequestor::SystemProfiler.user_agent
      identities = profile.values_at(:source, :telemetry_id).compact

      assert_equal 1, identities.length
      assert_match(/\A[0-9a-f]{32}\z/, identities.first)
    end
  ensure
    Stripe.enable_telemetry = false
    Stripe::TelemetryId.reset! if defined?(Stripe::TelemetryId)
    previous_xdg.nil? ? ENV.delete("XDG_CONFIG_HOME") : ENV["XDG_CONFIG_HOME"] = previous_xdg
  end
end
