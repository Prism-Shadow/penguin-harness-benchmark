# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class AiAgentProfilingTest < Minitest::Test
  def test_known_environment_variables_map_to_stable_agent_names
    profiler = Stripe::APIRequestor::SystemProfiler

    assert_equal "claude_code", profiler.detect_ai_agent("CLAUDECODE" => "1")
    assert_equal "cursor", profiler.detect_ai_agent("CURSOR_AGENT" => "active", "OPENCODE" => "1")
    assert_equal "", profiler.detect_ai_agent("CLAUDECODE" => "")
  end
end
