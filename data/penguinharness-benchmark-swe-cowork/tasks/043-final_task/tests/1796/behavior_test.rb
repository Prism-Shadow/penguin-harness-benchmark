# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class V2ExplicitRequestFieldsTest < Minitest::Test
  def test_only_explicit_fields_are_serialized_and_explicit_nil_is_retained
    params = Stripe::V2::Billing::MeterEventCreateParams.new(
      event_name: "usage.recorded",
      identifier: nil,
      payload: { stripe_customer_id: "cus_123", value: "4" }
    )

    result = params.to_h
    assert_equal "usage.recorded", result[:event_name]
    assert result.key?(:identifier)
    assert_nil result[:identifier]
    refute result.key?(:timestamp)
  end
end
