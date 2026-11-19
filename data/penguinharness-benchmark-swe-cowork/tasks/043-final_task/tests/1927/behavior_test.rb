# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "json"

class EventNotificationObjectFieldTest < Minitest::Test
  def test_parsed_notification_retains_its_wire_object_discriminator
    payload = { id: "evt_123", object: "v2.core.event", type: "unknown.created", context: nil }.to_json
    notification = Stripe::StripeClient.new("sk_test_123").parse_event_notification_without_verification(payload)

    assert_equal "v2.core.event", notification.object
    assert_equal "evt_123", notification.id
  end
end
