require_relative 'support'
require 'open3'
require 'rbconfig'

class AgentStartupTest < Minitest::Test
  def test_manual_start_in_a_clean_production_process
    script = <<~RUBY
      require 'opentelemetry'
      require 'logger'
      require 'new_relic/control'
      begin
        NewRelic::Agent.manual_start(:monitor_mode => 'off', :config_path => '',
          :log => Logger.new($stderr), :log_level => 'error',
          :'opentelemetry.enabled' => true)
        raise 'Boolean configuration compatibility lost' unless NewRelic::Agent.config[:monitor_mode] == false
        puts 'production manual_start and Boolean configuration passed'
      ensure
        NewRelic::Agent.shutdown
      end
    RUBY
    output, errors, status = Open3.capture3(RbConfig.ruby, '-I' + File.join(REPO_DIR, 'lib'), '-e', script)
    assert status.success?, "production startup failed (#{status.exitstatus}): #{output}\n#{errors}"
    assert_includes output.lines.map(&:chomp), 'production manual_start and Boolean configuration passed'
  end
end

class RegressionTest < ProductionContract
  def test_non_otel_segment_serialization_and_fresh_event_bounds
    bridge
    transaction = NewRelic::Agent::Tracer.start_transaction_or_segment(name: 'native', category: :web)
    segment = NewRelic::Agent::Transaction::Segment.new('native-child')
    segment.transaction = transaction
    segment.start
    event = NewRelic::Agent::SpanEventPrimitive.for_segment(segment)
    assert_equal 'Span', event[0]['type']
    segment.finish
    transaction.finish
    first = root_span
    before = Time.now.to_f
    first.add_event('now')
    after = Time.now.to_f
    first.finish
    events = harvested_spans.select { |e| e[0]['type'] == 'SpanEvent' }
    assert_equal 1, events.length
    assert_includes((before * 1000).floor..(after * 1000).ceil, events.first[0]['timestamp'])
    second = root_span
    second.finish
    refute harvested_spans.any? { |e| ['SpanEvent', 'SpanLink'].include?(e[0]['type']) }
  end

  def test_eager_constructor_and_in_span_exception_cleanup
    bridge
    active = tracer
    error = assert_raises(RuntimeError) do
      active.in_span('failing', kind: :server) do |span|
        span.set_attribute('constructed', true)
        raise 'application failure'
      end
    end
    assert_equal 'application failure', error.message
    assert_nil NewRelic::Agent::Tracer.current_transaction
    refute OpenTelemetry::Trace.current_span.recording?
  end
end
