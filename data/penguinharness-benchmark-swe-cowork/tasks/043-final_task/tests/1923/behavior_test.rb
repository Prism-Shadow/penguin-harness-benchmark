# frozen_string_literal: true

require "minitest/autorun"
require "stripe"

class DiscriminatedUnionRuntimeTest < Minitest::Test
  class CardParams < Stripe::RequestParams
    discriminator :type, "card"
    attr_accessor :exp_year

    def initialize(exp_year: nil)
      @exp_year = exp_year
    end
  end

  class ShapeBase < Stripe::StripeObject; end
  class CardShape < ShapeBase; end
  class BankShape < ShapeBase; end

  class Envelope < Stripe::StripeObject
    def self.inner_class_types
      { shape: ShapeBase }
    end

    def self.inner_class_union_variant_types
      { shape: ["type", { card: CardShape, bank: BankShape }] }
    end
  end

  def test_request_tags_and_response_variant_dispatch_share_the_discriminator
    assert_equal({ exp_year: 2030, type: "card" }, CardParams.new(exp_year: 2030).to_h)

    known = Envelope.construct_from(shape: { type: "card", last4: "4242" })
    unknown = Envelope.construct_from(shape: { type: "future_wallet", token: "tok_123" })
    assert_instance_of CardShape, known.shape
    assert_equal "4242", known.shape.last4
    assert_instance_of ShapeBase, unknown.shape
    assert_equal "future_wallet", unknown.shape.type
  end

  def test_fixed_tag_cannot_be_mutated_through_input_getter_or_serialized_result
    original = String.new("card_mutable")
    params_class = Class.new(Stripe::RequestParams) do
      define_method(:initialize) {}
    end
    params_class.discriminator(:type, original)
    original.replace("changed_input")
    instance = params_class.new
    assert_equal "card_mutable", instance.type
    [instance.type, instance.to_h.fetch(:type)].each do |exposed|
      begin
        exposed.replace("changed_result")
      rescue FrozenError
        # Frozen views and detached mutable copies are both valid.
      end
      assert_equal "card_mutable", params_class.new.to_h.fetch(:type)
    end
    hash = instance.to_h
    hash[:type] = "new_hash_value"
    assert_equal "card_mutable", instance.to_h.fetch(:type)
    subclass = Class.new(params_class)
    assert_equal "card_mutable", subclass.new.to_h.fetch(:type)
  end

  def test_union_tag_boundaries_and_schema_selection
    [{}, { type: nil }, { type: 7 }, { type: "future" }].each do |shape|
      result = Envelope.construct_from(shape: shape.merge(payload: "preserved"))
      assert_instance_of ShapeBase, result.shape
      assert_equal "preserved", result.shape.payload
    end
    assert_instance_of BankShape, Envelope.construct_from(shape: { type: :bank }).shape
    schema = { kind: :discriminated_union, discriminator: "type",
               variants: { card: { kind: :object, fields: { quantity: :int64_string } } } }
    ["card", :card].each do |tag|
      result = Stripe::RequestParams.coerce_value({ "type" => tag, "quantity" => -91 }, schema)
      assert_equal "-91", result["quantity"]
    end
    [{}, { type: nil }, { type: 8 }, { type: [] }].each do |value|
      assert_raises(ArgumentError) { Stripe::RequestParams.coerce_value(value, schema) }
    end
    future = { type: "future", quantity: 81 }
    assert_equal future, Stripe::RequestParams.coerce_value(future, schema)
  end
end
