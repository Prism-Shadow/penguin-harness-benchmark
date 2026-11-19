# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class NilParameterSerializationTest < Minitest::Test
  def test_hash_nils_are_omitted_by_default_but_can_be_preserved
    input = { name: "Ada", optional: nil, nested: { value: 7, absent: nil }, list: [nil, 3] }

    assert_equal({ name: "Ada", nested: { value: 7 }, list: [nil, 3] }, Stripe::Util.objects_to_ids(input))
    assert_equal input, Stripe::Util.objects_to_ids(input, serialize_empty: true)
  end
end
