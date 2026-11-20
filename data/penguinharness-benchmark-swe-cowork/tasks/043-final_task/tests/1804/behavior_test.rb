# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class TypedUpiParameterTest < Minitest::Test
  def test_payment_intent_upi_mandate_serializes_as_typed_nested_params
    mandate = Stripe::PaymentIntentCreateParams::PaymentMethodData::Upi::MandateOptions.new(
      amount: 1200,
      amount_type: "maximum",
      description: "Monthly plan",
      end_date: 1_800_000_000
    )
    upi = Stripe::PaymentIntentCreateParams::PaymentMethodData::Upi.new(mandate_options: mandate)

    assert_kind_of Stripe::RequestParams, upi
    assert_equal(
      { mandate_options: { amount: 1200, amount_type: "maximum", description: "Monthly plan", end_date: 1_800_000_000 } },
      upi.to_h
    )
  end
end
