# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class StripeNoticeResponseTest < Minitest::Test
  class HeaderResponse
    def [](name)
      name.downcase == "stripe-notice" ? "Rotate the integration key" : nil
    end
  end

  def test_response_notice_is_emitted_before_response_deserialization
    requestor = Stripe::APIRequestor.new("sk_test_123")
    warnings = []
    requestor.define_singleton_method(:execute_request_internal) do |*_args, **_kwargs|
      [HeaderResponse.new, {}]
    end
    requestor.define_singleton_method(:warn) { |message| warnings << message }
    requestor.define_singleton_method(:interpret_response) { |_response| raise "stop after header" }

    error = assert_raises(RuntimeError) do
      requestor.execute_request(:get, "/v1/customers", :api)
    end
    assert_equal "stop after header", error.message
    assert_equal ["WARNING: Rotate the integration key"], warnings
  end
end
