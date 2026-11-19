require 'minitest/autorun'
require 'opentelemetry'
require 'logger'
require 'stringio'

REPO_DIR = ENV.fetch('REPO_DIR')
$LOAD_PATH.unshift(File.join(REPO_DIR, 'lib'))
require 'new_relic/control'
require 'new_relic/agent/http_clients/abstract'
NewRelic::Agent.logger = NewRelic::Agent::AgentLogger.new('', Logger.new($stderr))
NewRelic::Agent.agent = NewRelic::Agent::Agent.new
require_relative 'contract_cases'

class ProductionContract < Minitest::Test
  include ContractCases

  def setup
    @sources = []
    configure(:'distributed_tracing.enabled' => true, :'span_events.enabled' => true,
      :'opentelemetry.enabled' => true, :'opentelemetry.traces.enabled' => true,
      :'opentelemetry.traces.include' => '', :'opentelemetry.traces.exclude' => '',
      :monitor_mode => false, :'distributed_tracing.sampler.root' => 'always_on')
    NewRelic::Agent.instance.stats_engine.reset!
    NewRelic::Agent.instance.span_event_aggregator.reset!
    NewRelic::Agent.instance.error_collector.error_trace_aggregator.reset!
  end

  def teardown
    NewRelic::Agent::Tracer.current_transaction&.finish
    Thread.current[:nr_otel_current_span] = nil
    @sources.reverse_each { |source| NewRelic::Agent.config.remove_config(source) }
  end

  def configure(values)
    source = values.dup
    NewRelic::Agent.config.add_config_for_testing(source)
    @sources << source
    NewRelic::Agent.instance.refresh_attribute_filter
  end

  def bridge
    events = NewRelic::Agent::EventListener.new
    NewRelic::Agent::OpenTelemetryBridge.new(events)
    events
  end

  def tracer(name = 'contract', version = '1')
    bridge
    OpenTelemetry.tracer_provider.tracer(name, version)
  end

  def root_span
    tracer.start_root_span('root', kind: :server)
  end

  def segment_for(span)
    item = span.finishable
    item.is_a?(NewRelic::Agent::Transaction) ? item.segments.first : item
  end

  def event_for(span)
    segment = segment_for(span)
    primitive = NewRelic::Agent::SpanEventPrimitive
    case segment
    when NewRelic::Agent::Transaction::DatastoreSegment
      primitive.for_datastore_segment(segment)
    when NewRelic::Agent::Transaction::ExternalRequestSegment
      primitive.for_external_request_segment(segment)
    else
      primitive.for_segment(segment)
    end
  end

  def metric_count(name)
    NewRelic::Agent.instance.stats_engine.to_h.sum do |spec, stats|
      spec.name == name ? stats.call_count : 0
    end
  end

  def harvested_spans
    NewRelic::Agent.instance.span_event_aggregator.harvest!.last
  end

  def trace_carrier(flags, sampled = nil, priority = nil)
    carrier = {'traceparent' => "00-1234567890abcdef1234567890abcdef-abcdef1234567890-#{flags}"}
    unless sampled.nil?
      carrier['tracestate'] = "123@nr=0-0-123-456-abcdef1234567890-0123456789abcdef-#{sampled ? 1 : 0}-#{priority}-1700000000000"
    end
    carrier
  end

  def remote_context(sampled = true)
    OpenTelemetry::Trace::SpanContext.new(
      trace_id: ['1234567890abcdef1234567890abcdef'].pack('H*'),
      span_id: ['abcdef1234567890'].pack('H*'),
      trace_flags: sampled ? OpenTelemetry::Trace::TraceFlags::SAMPLED : OpenTelemetry::Trace::TraceFlags::DEFAULT,
      remote: true)
  end
end
