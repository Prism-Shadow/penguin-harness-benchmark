# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class MultidimensionalParameterEncodingTest < Minitest::Test
  def test_each_array_dimension_keeps_its_own_index
    params = { matrix: [[1, 2], [3, 4]] }

    assert_equal(
      [["matrix[0][0]", 1], ["matrix[0][1]", 2], ["matrix[1][0]", 3], ["matrix[1][1]", 4]],
      Stripe::Util.flatten_params(params, :v1)
    )
    assert_equal "matrix[0][0]=1&matrix[0][1]=2&matrix[1][0]=3&matrix[1][1]=4",
                 Stripe::Util.encode_parameters(params, :v1)
  end
end
