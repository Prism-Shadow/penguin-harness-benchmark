# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class EventRequestTriggerHeaderTest < Minitest::Test
  Response = Struct.new(:http_body)

  class RecordingClient
    attr_reader :request

    def raw_request(method, path, opts:, usage:)
      @request = { method: method, path: path, opts: opts, usage: usage }
      Response.new('{"object":"v2.core.event","id":"evt_123","type":"unknown"}')
    end

    def deserialize(_body, api_mode:)
      [:decoded, api_mode]
    end
  end

  def test_fetch_event_marks_the_causative_event_in_request_options
    client = RecordingClient.new
    notification = Stripe::V2::Core::EventNotification.new(
      { id: "evt_123", object: "v2.core.event", type: "unknown", context: "acct_123" },
      client
    )

    assert_equal [:decoded, :v2], notification.fetch_event
    assert_equal :get, client.request[:method]
    assert_equal "/v2/core/events/evt_123", client.request[:path]
    assert_equal "event=evt_123", client.request[:opts]["Stripe-Request-Trigger"]
    assert_equal ["fetch_event"], client.request[:usage]
  end
end
