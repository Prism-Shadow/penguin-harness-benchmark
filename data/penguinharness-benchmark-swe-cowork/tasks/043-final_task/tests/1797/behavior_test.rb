# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class ReserveHoldObjectMappingTest < Minitest::Test
  def test_reserve_hold_maps_to_typed_resource_and_release_schedule
    hold = Stripe::Util.convert_to_stripe_object(
      { object: "reserve.hold", id: "res_hold_123", amount: 500,
        release_schedule: { release_after: 1_750_000_000, scheduled_release: 1_750_003_200 } },
      {}
    )

    assert_instance_of Stripe::Reserve::Hold, hold
    assert_equal "reserve.hold", hold.class.object_name
    assert_instance_of Stripe::Reserve::Hold::ReleaseSchedule, hold.release_schedule
    assert_equal 1_750_000_000, hold.release_schedule.release_after
  end
end
