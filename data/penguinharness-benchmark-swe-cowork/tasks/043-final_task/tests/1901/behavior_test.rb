# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class GeneratedErrorFieldContractTest < Minitest::Test
  def test_optional_generated_error_fields_are_readable_when_omitted
    error = Stripe::StripeError.new("declined", json_body: { error: { code: "card_declined" } }).error

    assert_equal "card_declined", error.code
    assert_nil error.advice_code
    assert_nil error.network_advice_code
    assert_nil error.network_decline_code
    assert_nil error.payment_method_type
    assert_nil error.request_log_url
    assert_nil error.user_message
  end
end
