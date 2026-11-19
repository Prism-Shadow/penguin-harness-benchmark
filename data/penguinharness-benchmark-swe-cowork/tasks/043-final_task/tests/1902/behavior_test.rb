# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "tmpdir"

class PersistentTelemetryIdTest < Minitest::Test
  def test_identifier_is_persisted_reloaded_and_used_in_the_profile
    previous_xdg = ENV["XDG_CONFIG_HOME"]
    Dir.mktmpdir do |dir|
      ENV["XDG_CONFIG_HOME"] = dir
      Stripe::TelemetryId.reset!
      first = Stripe::TelemetryId.get
      assert_match(/\A[0-9a-f]{32}\z/, first)
      assert_equal first, File.read(File.join(dir, "stripe", "telemetry_id"))

      Stripe::TelemetryId.reset!
      assert_equal first, Stripe::TelemetryId.get
      Stripe.enable_telemetry = true
      assert_equal first, Stripe::APIRequestor::SystemProfiler.user_agent[:telemetry_id]
      refute Stripe::APIRequestor::SystemProfiler.user_agent.key?(:source)
    end
  ensure
    Stripe.enable_telemetry = false
    Stripe::TelemetryId.reset! if defined?(Stripe::TelemetryId)
    previous_xdg.nil? ? ENV.delete("XDG_CONFIG_HOME") : ENV["XDG_CONFIG_HOME"] = previous_xdg
  end
end
