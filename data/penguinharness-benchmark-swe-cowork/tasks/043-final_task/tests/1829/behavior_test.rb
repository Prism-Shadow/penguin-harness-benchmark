# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "bigdecimal"

class DecimalWireCoercionTest < Minitest::Test
  def test_decimal_arrays_and_small_floats_have_fixed_point_wire_values
    [BigDecimal("-0.000000000000000019"), 1.0e-9, -7, 0].each do |number|
      wire = Stripe::RequestParams.coerce_value([number, nil], :decimal_string)
      assert_fixed_decimal(number, wire.first)
      assert_nil wire.last
    end
    assert_raises(ArgumentError) { DecimalResource.construct_from(amount: "not-a-number") }
  end

  class DecimalResource < Stripe::StripeObject
    def self.field_encodings
      { amount: :decimal_string }
    end
  end

  def test_decimal_strings_decode_without_losing_precision
    object = DecimalResource.construct_from(id: "obj_123", amount: "99.999000000000000001")

    assert_instance_of BigDecimal, object.amount
    assert_equal BigDecimal("99.999000000000000001"), object.amount
    ["12.34", "-7.00000000000000000019", "0.000000000000000001"].each do |number|
      assert_fixed_decimal(BigDecimal(number), Stripe::RequestParams.coerce_value(BigDecimal(number), :decimal_string))
    end
  end
  def assert_fixed_decimal(expected, actual)
    assert_kind_of String, actual
    assert_match(/\A[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\z/, actual)
    assert_equal BigDecimal(expected.to_s), BigDecimal(actual)
  end

end
