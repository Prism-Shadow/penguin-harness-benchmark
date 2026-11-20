# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class Int64RequestCoercionTest < Minitest::Test
  def test_nested_boundaries_nil_and_unencoded_siblings_do_not_mutate_input
    schema = { kind: :object, fields: { groups: { kind: :array, element: {
      kind: :object, fields: { quantity: { kind: :nullable, inner: :int64_string } }
    } } } }
    [-9_223_372_036_854_775_808, -19, 0, 9_223_372_036_854_775_807, nil].each do |number|
      input = { "groups" => [{ "quantity" => number, "untouched" => number }] }
      before = Marshal.load(Marshal.dump(input))
      expected = number.nil? ? nil : number.to_s
      result = Stripe::RequestParams.coerce_value(input, schema)
      assert_equal expected, result["groups"][0]["quantity"]
      assert_equal number, result["groups"][0]["untouched"]
      assert_equal before, input
    end
  end

  def test_int64_values_are_string_encoded_through_nested_schemas
    schema = {
      kind: :array,
      element: { kind: :object, fields: { quantity: :int64_string } },
    }
    input = [{ quantity: 9_223_372_036_854_775_807, label: "max" }, { quantity: -7 }]

    assert_equal(
      [{ quantity: "9223372036854775807", label: "max" }, { quantity: "-7" }],
      Stripe::RequestParams.coerce_value(input, schema)
    )
  end
end
