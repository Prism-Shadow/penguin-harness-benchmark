# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class ManagedPaymentsObjectTest < Minitest::Test
  def test_subscription_deserializes_managed_payments_to_its_typed_object
    subscription = Stripe::Subscription.construct_from(
      id: "sub_123",
      object: "subscription",
      managed_payments: { enabled: true }
    )

    assert_instance_of Stripe::Subscription::ManagedPayments, subscription.managed_payments
    assert_equal true, subscription.managed_payments.enabled
  end
end
