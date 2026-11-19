# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "bigdecimal"

class BidirectionalV2TypeCoercionTest < Minitest::Test
  def test_shared_coercion_handles_native_and_wire_values_in_both_directions
    schema = { amount: :int64_string, price: :decimal_string }
    native = { amount: 9_223_372_036_854_775_807, price: BigDecimal("10.2500"), untouched: true }
    wire = Stripe::V2TypeCoercion.coerce_fields(native, schema, direction: :encode)

    assert_equal [:amount, :price, :untouched], wire.keys.sort
    assert_equal "9223372036854775807", wire[:amount]
    assert_equal true, wire[:untouched]
    assert_fixed_decimal(native[:price], wire[:price])
    assert_equal native, Stripe::V2TypeCoercion.coerce_fields(wire, schema, direction: :decode)
  end
  def test_decimal_precision_and_fixed_point_format_across_field_coercion
    ["-7.00000000000000000019", "0.000000000000000001", "12.3400"].each do |spelling|
      value = BigDecimal(spelling)
      wire = Stripe::V2TypeCoercion.coerce_fields({ price: value }, { price: :decimal_string }, direction: :encode)
      assert_fixed_decimal(value, wire[:price])
    end
  end

  def assert_fixed_decimal(expected, actual)
    assert_kind_of String, actual
    assert_match(/\A[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\z/, actual)
    assert_equal BigDecimal(expected.to_s), BigDecimal(actual)
  end

end
