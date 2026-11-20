module ContractCases
  def contract_3195
    bridge
    propagator = OpenTelemetry.propagation
    key = OpenTelemetry::Context.create_key('unrelated')
    original = OpenTelemetry::Context.current.set_value(key, 'preserved')
    ['01', '00', '03', 'ff'].each do |flags|
      result = propagator.extract({'traceparent' => "00-1234567890abcdef1234567890abcdef-abcdef1234567890-#{flags}"}, context: original)
      extracted = OpenTelemetry::Trace.current_span(result).context
      assert_equal 'preserved', result.value(key)
      assert extracted.remote?
      assert extracted.valid?
      assert_equal '1234567890abcdef1234567890abcdef', extracted.hex_trace_id
      assert_equal 'abcdef1234567890', extracted.hex_span_id
      assert_equal flags.to_i(16).odd?, extracted.trace_flags.sampled?
    end
    [{}, {'traceparent' => 'invalid'}, {'traceparent' => '00-' + '0' * 32 + '-' + '0' * 16 + '-01'}].each do |carrier|
      assert_same original, propagator.extract(carrier, context: original)
    end
    getter = Object.new
    def getter.get(carrier, key)
      carrier['HTTP_' + key.upcase.tr('-', '_')]
    end
    result = propagator.extract({'HTTP_TRACEPARENT' => '00-1234567890abcdef1234567890abcdef-abcdef1234567890-01'}, getter: getter)
    assert_equal 'abcdef1234567890', OpenTelemetry::Trace.current_span(result).context.hex_span_id
  end

  def contract_3207
    span = root_span
    child = tracer.start_span('child', kind: :internal)
    span.set_attribute('one', 1)
    span.add_attributes('two' => 2)
    span.add_attributes('one' => 3)
    span.add_attributes(nil)
    span.add_attributes({})
    child.set_attribute('child', true)
    root_id, child_id = span.context.hex_span_id, child.context.hex_span_id
    child.finish
    span.finish
    data = harvested_spans
    attributes = data.find { |e| e[0]['guid'] == root_id }[1]
    assert_equal 3, attributes['one']
    assert_equal 2, attributes['two']
    child_attributes = data.find { |e| e[0]['guid'] == child_id }[1]
    assert_equal true, child_attributes['child']
    refute child_attributes.key?('one')
  end

  def contract_3209
    configure(:'error_collector.attributes.exclude' => ['secret'])
    span = root_span
    NewRelic::Agent.add_custom_attributes('transaction.source' => 'transaction')
    error = RuntimeError.new('contract error')
    span.record_exception(error, attributes: {'source' => 'contract', 'secret' => 'hidden'})
    span.record_exception(error, attributes: {'source' => 'latest', 'secret' => 'hidden'})
    span.record_exception(ArgumentError.new('no attributes'), attributes: nil)
    span.finish
    errors = NewRelic::Agent.instance.error_collector.error_trace_aggregator.harvest!
    assert_equal 2, errors.length
    noticed = errors.find { |e| e.message == 'contract error' }
    assert_equal 'RuntimeError', noticed.exception_class_name
    attrs = noticed.processed_attributes['userAttributes']
    assert_equal 'latest', attrs['source']
    assert_equal 'transaction', attrs['transaction.source']
    refute attrs.key?('secret')
    assert errors.any? { |e| e.exception_class_name == 'ArgumentError' }
  end

  def contract_3220
    root = root_span
    span = tracer.start_span('select', kind: :client, attributes: {'db.system' => 'postgresql'})
    segment_for(span).params[:backtrace] = ['frame.rb:1', 'caller.rb:2']
    id = span.context.hex_span_id
    span.finish
    root.finish
    event = harvested_spans.find { |e| e[0]['guid'] == id }
    assert_equal ['frame.rb:1', 'caller.rb:2'], event[2]['code.stacktrace']
  end

  def contract_3306
    payload = NewRelic::Agent::TraceContextPayload::INVALID
    refute payload.valid?
    assert_nil payload.sampled
    assert_kind_of Integer, payload.timestamp
  end

  def contract_3308
    configure(:'opentelemetry_bridge.enabled' => false)
    span = root_span
    assert span.recording?
    assert span.context.valid?
    assert_instance_of NewRelic::Agent::Transaction, span.finishable
    span.finish
  end

  def contract_3330
    previous_logger = NewRelic::Agent.logger
    warning_output = StringIO.new
    warning_sink = Logger.new(warning_output)
    NewRelic::Agent.logger = NewRelic::Agent::AgentLogger.new('', warning_sink)
    warning_sink.level = Logger::WARN
    %w[root remote_parent_sampled remote_parent_not_sampled].each do |branch|
      key = "distributed_tracing.sampler.#{branch}".to_sym
      ratio_key = "#{key}.trace_id_ratio_based.ratio".to_sym
      before_warning_bytes = warning_output.string.bytesize
      configure(key => 'trace_id_ratio_based', ratio_key => nil)
      assert_equal 'default', NewRelic::Agent.config[key]
      assert_operator warning_output.string.bytesize, :>, before_warning_bytes
      [0.0, 0.5, 1.0].each do |ratio|
        configure(key => 'trace_id_ratio_based', ratio_key => ratio)
        assert_equal ratio, NewRelic::Agent.config[ratio_key]
        assert_equal 'trace_id_ratio_based', NewRelic::Agent.config[key]
      end
      [nil, 0, 1, '0.5', -0.1, 1.1, Float::NAN, Float::INFINITY, -Float::INFINITY].each do |ratio|
        configure(key => 'trace_id_ratio_based', ratio_key => ratio)
        assert_nil NewRelic::Agent.config[ratio_key], "reject #{branch}: #{ratio.inspect}"
        assert_equal 'default', NewRelic::Agent.config[key]
      end
    end
  ensure
    NewRelic::Agent.logger = previous_logger
  end

  def contract_3353
    ['true', 'yes', 'on', true].each do |value|
      configure(:monitor_mode => value, :'opentelemetry.traces.enabled' => value)
      assert_equal true, NewRelic::Agent.config[:monitor_mode]
      assert_equal true, NewRelic::Agent.config[:'opentelemetry.traces.enabled']
    end
    ['false', 'no', 'off', false].each do |value|
      configure(:monitor_mode => value, :'opentelemetry.traces.enabled' => value)
      assert_equal false, NewRelic::Agent.config[:monitor_mode]
      assert_equal false, NewRelic::Agent.config[:'opentelemetry.traces.enabled']
    end
  end

  def contract_3354
    span = root_span
    assert span.recording?
    span.name = 'renamed'
    assert_equal 'renamed', span.finishable.best_name
    span.finish
    refute span.recording?
    span.name = 'too late'
    assert_equal 'renamed', span.finishable.best_name
  end

  def contract_3368
    configure(:account_id => '123', :trusted_account_key => '123', :primary_application_id => '456')
    NewRelic::Agent.instance.instance_variable_set(:@connect_state, :connected)
    active = tracer
    ['01', '00'].each do |flags|
      branch = flags == '01' ? 'remote_parent_sampled' : 'remote_parent_not_sampled'
      [true, false].each do |supplied|
        ['adaptive', 'always_on', 'always_off', 'trace_id_ratio_based'].each do |strategy|
          ratios = strategy == 'trace_id_ratio_based' ? [0.0, 1.0, 2.0] : [nil]
          ratios.each do |ratio|
            configure("distributed_tracing.sampler.#{branch}".to_sym => strategy,
              "distributed_tracing.sampler.#{branch}.trace_id_ratio_based.ratio".to_sym => ratio)
            priority = supplied ? 1.375 : 0.275
            carrier = trace_carrier(flags, supplied, priority)
            ctx = OpenTelemetry.propagation.extract(carrier)
            span = active.start_span('incoming', kind: :server, with_parent: ctx)
            txn = NewRelic::Agent::Tracer.current_transaction
            expected = case strategy
            when 'always_on' then true
            when 'always_off' then false
            when 'trace_id_ratio_based' then ratio == 2.0 ? supplied : ratio == 1.0
            else supplied
            end
            assert_equal expected, span.context.trace_flags.sampled?
            assert_equal expected, txn.sampled?, "#{branch}/#{strategy}/#{ratio}/#{supplied}"
            assert_equal priority, txn.priority if strategy == 'adaptive' || ratio == 2.0
            outgoing = {}
            assert_same txn, OpenTelemetry.propagation.inject(outgoing)
            assert_equal expected ? '01' : '00', outgoing.fetch('traceparent').split('-').last
            assert_equal txn.trace_id, outgoing['traceparent'].split('-')[1]
            assert_equal span.context.hex_span_id, outgoing['traceparent'].split('-')[2]
            nr_state = outgoing.fetch('tracestate').split(',').find { |v| v.start_with?('123@nr=') }.split('=', 2).last.split('-')
            assert_equal expected ? '1' : '0', nr_state[6]
            assert_in_delta txn.priority, nr_state[7].to_f, 0.000001
            before_priority = txn.priority
            span.finish
            spans = harvested_spans.select { |e| e[0]['type'] == 'Span' }
            assert_equal expected ? 1 : 0, spans.length
            unless spans.empty?
              assert_equal txn.trace_id, spans.first[0]['traceId']
              assert_equal before_priority, spans.first[0]['priority']
            end
          end
        end
      end
      configure("distributed_tracing.sampler.#{branch}".to_sym => 'adaptive')
      [nil, 'malformed', '123@nr=0-0---bad'].each do |state|
        carrier = trace_carrier(flags)
        carrier['tracestate'] = state if state
        span = active.start_span('fallback', kind: :server, with_parent: OpenTelemetry.propagation.extract(carrier))
        assert_equal flags == '01', NewRelic::Agent::Tracer.current_transaction.sampled?
        span.finish
        harvested_spans
      end
    end
    ['always_on', 'always_off', 'trace_id_ratio_based'].each do |strategy|
      [0.0, 1.0].each do |ratio|
        configure(:'distributed_tracing.sampler.root' => strategy,
          :'distributed_tracing.sampler.root.trace_id_ratio_based.ratio' => ratio)
        span = active.start_root_span('root-sampling', kind: :server)
        assert_equal(strategy == 'always_on' || (strategy == 'trace_id_ratio_based' && ratio == 1.0), NewRelic::Agent::Tracer.current_transaction.sampled?)
        span.finish
        harvested_spans
      end
    end
  end

  def contract_3400
    [[false, false], [false, true], [true, false]].each do |enabled, traces|
      configure(:'opentelemetry.enabled' => enabled, :'opentelemetry.traces.enabled' => traces)
      NewRelic::Agent.instance.stats_engine.reset!
      previous = OpenTelemetry.tracer_provider
      events = bridge
      assert_same previous, OpenTelemetry.tracer_provider
      metric = 'Supportability/Tracing/Ruby/OpenTelemetryBridge/disabled'
      assert_equal 0, metric_count(metric)
      2.times { events.notify(:initial_configuration_complete) }
      assert_equal 1, metric_count(metric)
    end
  end

  def contract_3403
    active = tracer
    [:client, :producer, :internal, nil].each do |kind|
      refute active.start_span('orphan', kind: kind).recording?
      assert_nil NewRelic::Agent::Tracer.current_transaction
    end
    [:server, :consumer].each do |kind|
      span = active.start_span('entry', kind: kind)
      assert span.recording?
      span.finish
    end
    parent = OpenTelemetry::Trace.context_with_span(OpenTelemetry::Trace.non_recording_span(remote_context))
    span = active.start_span('remote-client', kind: :client, with_parent: parent)
    assert span.recording?
    assert_equal remote_context.hex_trace_id, span.finishable.trace_id
    assert_equal remote_context.trace_id, span.context.trace_id
    assert_equal remote_context.hex_trace_id, span.context.hex_trace_id
    span.finish
    [
      ['fedcba98765432101234567890abcdef', '1234567890abcdef', '01', :producer],
      ['00112233445566778899aabbccddeeff', 'fedcba9876543210', '00', :internal]
    ].each do |trace_id, parent_id, flags, kind|
      context = OpenTelemetry.propagation.extract({'traceparent' => "00-#{trace_id}-#{parent_id}-#{flags}"})
      entry = active.start_span('propagated-entry', kind: kind, with_parent: context)
      assert entry.recording?
      assert_equal trace_id, entry.finishable.trace_id
      assert_equal parent_id, entry.finishable.parent_span_id
      assert_equal [trace_id].pack('H*'), entry.context.trace_id
      assert_equal trace_id, entry.context.hex_trace_id
      assert_equal 8, entry.context.span_id.bytesize
      child = active.start_span('propagated-child', kind: :internal)
      assert_equal entry.context.trace_id, child.context.trace_id
      assert_equal trace_id, event_for(child)[0]['traceId']
      child.finish
      assert_same entry, OpenTelemetry::Trace.current_span
      entry.finish
      assert_nil NewRelic::Agent::Tracer.current_transaction
    end
  end

  def contract_3410
    root = root_span
    span = tracer.start_span('request', kind: :client, attributes: {'url.scheme' => 'https', 'server.address' => 'api.test', 'server.port' => 8443, 'url.path' => '/v2', 'http.request.method' => 'POST'})
    assert_equal 'https://api.test:8443/v2', segment_for(span).uri.to_s
    assert_equal 'POST', segment_for(span).procedure
    span.finish
    root.finish
  end

  def contract_3411
    root = root_span
    status = OpenTelemetry::Trace::Status.error('root failure')
    child = tracer.start_span('child-status', kind: :internal)
    root.status = status
    assert_equal status, root.status
    child.status = OpenTelemetry::Trace::Status.error('child failure')
    child_id = child.context.hex_span_id
    root_id = root.context.hex_span_id
    child.finish
    root.finish
    events = harvested_spans
    assert_equal 2, events.count { |e| e[0]['type'] == 'Span' }
    {root_id => 'root failure', child_id => 'child failure'}.each do |id, description|
      event = events.find { |e| e[0]['guid'] == id }
      attrs = event[1].merge(event[2])
      assert_equal 2, attrs['status.code']
      assert_equal description, attrs['status.description']
    end
  end

  def contract_3429
    events = bridge
    metric = 'Supportability/Tracing/Ruby/OpenTelemetryBridge/enabled'
    assert_equal 0, metric_count(metric)
    2.times { events.notify(:initial_configuration_complete) }
    assert_equal 1, metric_count(metric)
  end

  def contract_3427
    root = root_span
    [ ['select', {'db.operation' => 'insert', 'db.statement' => 'UPDATE users SET x=1'}, 'insert'],
      ['select', {'db.statement' => 'UPDATE users SET x=1'}, 'update'],
      ['DELETE', {}, 'delete'], ['custom', {}, 'custom'] ].each do |name, attrs, expected|
      span = tracer.start_span(name, kind: :client, attributes: attrs.merge('db.system' => 'postgresql'))
      assert_equal expected, segment_for(span).operation
      span.finish
    end
    root.finish
  end

  def contract_3430
    bridge
    provider = OpenTelemetry.tracer_provider
    assert_same provider.tracer('library', '1'), provider.tracer('library', '1')
    refute_same provider.tracer('library', '1'), provider.tracer('library', '2')
    refute_same provider.tracer('library', '1'), provider.tracer('another-library', '1')
    ready = Queue.new
    gate = Queue.new
    threads = 16.times.map do
      Thread.new do
        ready << true
        gate.pop
        provider.tracer('concurrent', 'version')
      end
    end
    16.times { ready.pop }
    16.times { gate << true }
    values = threads.map(&:value)
    assert_equal 1, values.map(&:object_id).uniq.length
    name = 'OpenTelemetry::Instrumentation::Redis::Instrumentation'
    refute provider.tracer(name).start_span('excluded', kind: :server).recording?
    configure(:'opentelemetry.traces.include' => name)
    bridge
    span = OpenTelemetry.tracer_provider.tracer(name).start_span('included', kind: :server)
    assert span.recording?
    span.finish
    configure(:'opentelemetry.traces.exclude' => name)
    bridge
    refute OpenTelemetry.tracer_provider.tracer(name).start_span('explicit-exclude', kind: :server).recording?
    configure(:'opentelemetry.traces.exclude' => 'blocked')
    bridge
    refute OpenTelemetry.tracer_provider.tracer('blocked').start_span('entry', kind: :server).recording?
  end

  def contract_3433
    span = tracer('Rack').start_root_span('fallback', kind: :server, attributes: {'http.request.method' => 'GET', 'url.path' => '/items'})
    assert_equal 'Controller/Rack/GET /items', span.finishable.best_name
    span.finish
  end

  def contract_3442
    result = NewRelic::Agent::Configuration::DefaultSource.convert_to_regexp_list(['foo', '^bar$'])
    assert result[0].match?('food')
    assert result[1].match?('bar')
    refute result[1].match?('barley')
  end

  def contract_3452
    span = root_span
    assert_same span, OpenTelemetry::Trace.current_span
    fallback = OpenTelemetry::Trace.non_recording_span(remote_context)
    context = OpenTelemetry::Trace.context_with_span(fallback)
    assert_same fallback, OpenTelemetry::Trace.current_span(context)
    span.finish
    OpenTelemetry::Context.with_current(context) { assert_same fallback, OpenTelemetry::Trace.current_span }
  end

  def contract_3454
    root = root_span
    child = tracer.start_span('unfinished-child', kind: :internal)
    root.finish
    refute child.recording?
    refute root.recording?
    assert_nil NewRelic::Agent::Tracer.current_transaction
    refute OpenTelemetry::Trace.current_span.recording?
    assert_equal 2, harvested_spans.count { |e| e[0]['type'] == 'Span' }
  end

  def contract_3539
    span = tracer('Rack').start_root_span('fallback', kind: :server, attributes: {'http.request.method' => 'POST', 'url.path' => '/health'})
    assert_equal 'Controller/Rack/POST /health', span.finishable.best_name
    span.finish
  end

  def contract_3562
    root = root_span
    span = tracer('opentelemetry-instrumentation-redis').start_span('fetch', kind: :client, attributes: {'db.system' => 'redis', 'db.statement' => 'GET another-key'})
    assert_equal 'redis', segment_for(span).product
    assert_equal 'GET another-key', segment_for(span).nosql_statement
    span.finish
    root.finish
  end

  def contract_3574
    root = root_span
    span = tracer.start_span('call', kind: :client, attributes: {'rpc.system' => 'grpc', 'server.address' => 'dns:///host', 'rpc.service' => 'Svc', 'rpc.method' => 'Call'})
    assert_equal 'grpc://host/Svc/Call', segment_for(span).uri.to_s
    span.finish
    root.finish
  end

  def contract_3586
    configure(:'span_events.attributes.exclude' => ['secret'])
    span = root_span
    span_id = span.context.hex_span_id
    trace_id = span.context.hex_trace_id
    101.times do |i|
      link = OpenTelemetry::Trace::Link.new(remote_context, {'index' => i, 'secret' => 'hidden'})
      assert_same span, span.add_link(link)
    end
    span.finish
    span.add_link(OpenTelemetry::Trace::Link.new(remote_context))
    assert_equal 1, metric_count('Supportability/Ruby/SpanEvent/Links/Dropped')
    links = harvested_spans.select { |e| e[0]['type'] == 'SpanLink' }
    assert_equal 100, links.length
    assert_equal (0...100).to_a, links.map { |e| e[1]['index'] }.sort
    links.each do |entry|
      assert_equal remote_context.hex_span_id, entry[0]['linkedSpanId']
      assert_equal remote_context.hex_trace_id, entry[0]['linkedTraceId']
      assert_equal span_id, entry[0]['id']
      assert_equal trace_id, entry[0]['trace.id']
      refute entry[1].key?('secret')
      assert_equal 3, entry.length
    end
  end

  def contract_3587
    configure(:'span_events.attributes.exclude' => ['secret'])
    span = root_span
    span_id = span.context.hex_span_id
    trace_id = span.context.hex_trace_id
    span.add_event('nano', attributes: {'ok' => true, 'secret' => 'hidden'}, timestamp: 1_000_000_000)
    span.add_link(OpenTelemetry::Trace::Link.new(remote_context))
    span.add_event('seconds', timestamp: 2.5)
    99.times { |index| span.add_event("event-#{index}", timestamp: 3.0) }
    span.finish
    span.add_event('late')
    assert_equal 1, metric_count('Supportability/Ruby/SpanEvent/Events/Dropped')
    data = harvested_spans
    events = data.select { |entry| entry[0]['type'] == 'SpanEvent' }
    assert_equal 100, events.length
    assert_equal ['nano', 'seconds', *(0...98).map { |i| "event-#{i}" }].sort, events.map { |e| e[0]['name'] }.sort
    nano = events.find { |e| e[0]['name'] == 'nano' }
    assert_equal 1000, nano[0]['timestamp']
    assert_equal true, nano[1]['ok']
    refute nano[1].key?('secret')
    assert_equal 2500, events.find { |e| e[0]['name'] == 'seconds' }[0]['timestamp']
    events.each do |e|
      assert_equal span_id, e[0]['span.id']
      assert_equal trace_id, e[0]['trace.id']
    end
    assert_equal 1, data.count { |e| e[0]['type'] == 'SpanLink' }
    assert data.all? { |e| e.length == 3 }
  end

  def contract_3588
    active = tracer
    ambient = OpenTelemetry::Trace.context_with_span(OpenTelemetry::Trace.non_recording_span(remote_context))
    OpenTelemetry::Context.with_current(ambient) do
      span = active.start_root_span('root', kind: :server)
      assert span.recording?
      refute_equal remote_context.hex_trace_id, span.context.hex_trace_id
      assert_nil span.finishable.parent_span_id
      span.finish
    end
  end

  def contract_3589
    span = root_span
    span.kind = :consumer
    assert_equal :consumer, span.kind
    assert_equal 'consumer', event_for(span)[0]['span.kind']
    span.finish
  end

  def contract_3591
    configure(:'message_tracer.segment_parameters.enabled' => true)
    active = tracer
    ['invoices', 'alerts'].each do |destination|
      attrs = {'messaging.system' => 'kafka', 'messaging.destination.name' => destination,
        'messaging.kafka.message.key' => "#{destination}-7", 'messaging.message.conversation_id' => "conversation-#{destination}"}
      ctx = OpenTelemetry::Trace.context_with_span(OpenTelemetry::Trace.non_recording_span(remote_context))
      producer = active.start_span('send', kind: :producer, attributes: attrs, with_parent: ctx)
      txn = NewRelic::Agent::Tracer.current_transaction
      assert_equal "OtherTransaction/Message/Kafka/Topic/Produce/Named/#{destination}", txn.best_name
      child = active.start_span('send-child', kind: :producer, attributes: attrs)
      segment = NewRelic::Agent::Tracer.current_segment
      assert_equal "MessageBroker/Kafka/Topic/Produce/Named/#{destination}", segment.name
      assert_equal "#{destination}-7", segment.params[:routing_key]
      assert_equal "conversation-#{destination}", segment.params[:correlation_id]
      id = child.context.hex_span_id
      child.finish
      producer.finish
      event = harvested_spans.find { |e| e[0]['guid'] == id }
      assert_equal "MessageBroker/Kafka/Topic/Produce/Named/#{destination}", event[0]['name']
    end
  end

end
