# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class FinancialConnectionsAuthorizationTest < Minitest::Test
  def test_authorization_maps_to_typed_nested_status_details
    authorization = Stripe::Util.convert_to_stripe_object(
      {
        object: "financial_connections.authorization",
        id: "fcauth_123",
        institution_name: "Example Bank",
        status: "active",
        status_details: { active: { action: "none", expected_deactivation_date: 1_800_000_000 } },
      },
      {}
    )

    assert_instance_of Stripe::FinancialConnections::Authorization, authorization
    assert_instance_of Stripe::FinancialConnections::Authorization::StatusDetails, authorization.status_details
    assert_instance_of Stripe::FinancialConnections::Authorization::StatusDetails::Active,
                       authorization.status_details.active
    assert_equal "Example Bank", authorization.institution_name
  end
end
