# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class OpenClawAgentProfilingTest < Minitest::Test
  def test_openclaw_shell_is_reported_with_the_generated_agent_name
    profiler = Stripe::APIRequestor::SystemProfiler

    assert_equal "openclaw", profiler.detect_ai_agent("OPENCLAW_SHELL" => "1")
  end
end
