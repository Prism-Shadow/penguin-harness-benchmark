# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class FatalHttpRetryTest < Minitest::Test
  def test_http_fatal_errors_are_retryable_until_the_retry_budget_is_exhausted
    response = Net::HTTPServiceUnavailable.new("1.1", "503", "Service Unavailable")
    error = Net::HTTPFatalError.new('503 "Service Unavailable"', response)
    config = Stripe::StripeConfiguration.new
    config.max_network_retries = 2

    assert Stripe::APIRequestor.should_retry?(error, num_retries: 0, config: config)
    refute Stripe::APIRequestor.should_retry?(error, num_retries: 2, config: config)
  end
end
