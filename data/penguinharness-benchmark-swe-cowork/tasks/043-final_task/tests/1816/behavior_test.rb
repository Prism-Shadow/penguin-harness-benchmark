# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class V1ExplicitRequestFieldsTest < Minitest::Test
  class TeamParams < Stripe::RequestParams
    attr_accessor :name, :team

    def initialize(name: nil, team: nil)
      @name = name
      @team = team
    end
  end

  def test_v1_params_share_explicit_key_tracking_with_v2_params
    implicit = TeamParams.new(name: "Ada").to_h
    explicit = TeamParams.new(name: "Ada", team: nil).to_h

    assert_equal({ name: "Ada" }, implicit)
    assert_equal({ name: "Ada", team: nil }, explicit)
  end
end
