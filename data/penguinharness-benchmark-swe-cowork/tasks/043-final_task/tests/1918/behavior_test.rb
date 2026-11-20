# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "json"

class CloudEventEnvelopeParsingTest < Minitest::Test
  def test_raw_aws_and_azure_snapshots_keep_business_data
    snapshot = { id: "evt_data", object: "event", type: "customer.created",
                 data: { object: { id: "cus_kept", object: "customer", name: "retained" } } }
    [snapshot, snapshot.merge(detail: { object: "not_an_event" }),
     { detail: snapshot }, { specversion: "1.0", data: snapshot }].each do |wrapped|
      parsed = Stripe::Webhook.construct_event_without_verification(wrapped.to_json)
      assert_equal "evt_data", parsed.id
      assert_equal "customer.created", parsed.type
      assert_equal "cus_kept", parsed.data.object.id
      assert_equal "retained", parsed.data.object.name
    end
    client = Stripe::StripeClient.new("sk_test_contract")
    assert_raises(ArgumentError) { client.parse_event_notification_without_verification(snapshot.to_json) }
    assert_raises(JSON::ParserError) { client.parse_event_notification_without_verification("{") }
    assert_raises(JSON::ParserError) { Stripe::Webhook.construct_event_without_verification("{") }
    assert_raises(ArgumentError) do
      Stripe::Webhook.construct_event_without_verification({ detail: { object: "customer" } }.to_json)
    end
  end

  def test_unverified_parsers_extract_aws_envelopes_for_both_event_kinds
    snapshot = { id: "evt_snapshot", object: "event", type: "customer.created", data: { object: {} } }
    thin = { id: "evt_thin", object: "v2.core.event", type: "unknown.created", context: nil }

    event = Stripe::Webhook.construct_event_without_verification({ detail: snapshot }.to_json)
    notification = Stripe::StripeClient.new("sk_test_123")
                                         .parse_event_notification_without_verification({ detail: thin }.to_json)

    assert_instance_of Stripe::Event, event
    assert_equal "evt_snapshot", event.id
    assert_instance_of Stripe::Events::UnknownEventNotification, notification
    assert_equal "evt_thin", notification.id
  end
end
