# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class Zip64DefaultContract < Minitest::Test
  def test_zip64_writing_is_enabled_after_reset
    Zip.reset!
    assert_equal(true, Zip.write_zip64_support)
  end
end
