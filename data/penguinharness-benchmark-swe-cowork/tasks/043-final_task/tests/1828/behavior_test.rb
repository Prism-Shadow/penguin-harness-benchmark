# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "json"

class WebhookPayloadKindIsolationTest < Minitest::Test
  def test_snapshot_acceptance_and_signature_precedence
    snapshot = { id: "evt_snapshot_control", object: "event", type: "customer.created",
                 data: { object: { id: "cus_control", object: "customer" } } }.to_json
    timestamp = Time.now
    secret = "whsec_contract"
    signature = Stripe::Webhook::Signature.compute_signature(timestamp, snapshot, secret)
    header = Stripe::Webhook::Signature.generate_header(timestamp, signature)
    parsed = Stripe::Webhook.construct_event(snapshot, header, secret)
    assert_equal "evt_snapshot_control", parsed.id
    assert_equal "cus_control", parsed.data.object.id
    assert_raises(Stripe::SignatureVerificationError) do
      Stripe::Webhook.construct_event("not-json", "invalid", secret)
    end
  end

  def test_snapshot_parser_rejects_a_thin_event_notification
    payload = { id: "evt_123", object: "v2.core.event", type: "example.created" }.to_json
    timestamp = Time.now
    secret = "whsec_contract"
    signature = Stripe::Webhook::Signature.compute_signature(timestamp, payload, secret)
    header = Stripe::Webhook::Signature.generate_header(timestamp, signature)

    error = assert_raises(ArgumentError) do
      Stripe::Webhook.construct_event(payload, header, secret)
    end
    assert_match(/parse_event_notification/, error.message)
  end
end
