# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class DecompressorRegistryContract < Minitest::Test
  class Probe < Zip::Decompressor
  end

  def test_registration_round_trips_a_class
    method_id = 0x7f01
    Zip::Decompressor.register(method_id, Probe)
    assert_same(Probe, Zip::Decompressor.find_by_compression_method(method_id))
  end
end
