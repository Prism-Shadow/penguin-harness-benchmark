# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class SunbitPaymentIntentParamsTest < Minitest::Test
  def test_sunbit_options_preserve_capture_and_future_usage_fields
    options = Stripe::PaymentIntentCreateParams::PaymentMethodOptions::Sunbit.new(
      capture_method: "manual",
      setup_future_usage: "off_session"
    )

    assert_equal({ capture_method: "manual", setup_future_usage: "off_session" }, options.to_h)
  end
end
