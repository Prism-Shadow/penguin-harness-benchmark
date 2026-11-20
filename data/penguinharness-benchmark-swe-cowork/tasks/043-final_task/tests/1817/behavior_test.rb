# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class RemovedLegacyResourcesTest < Minitest::Test
  def test_removed_resources_cannot_be_loaded_or_exposed_as_sdk_constants
    assert_raises(LoadError) { require "stripe/resources/alipay_account" }
    assert_raises(LoadError) { require "stripe/resources/recipient_transfer" }
    refute Stripe.const_defined?(:AlipayAccount, false)
    refute Stripe.const_defined?(:RecipientTransfer, false)
  end
end
