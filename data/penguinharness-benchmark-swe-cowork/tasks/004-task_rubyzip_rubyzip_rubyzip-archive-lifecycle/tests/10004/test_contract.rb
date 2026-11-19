# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class ResetEncodingContract < Minitest::Test
  def test_reset_clears_forced_entry_encoding
    Zip.force_entry_names_encoding = Encoding::ISO_8859_1
    Zip.reset!
    assert_nil(Zip.force_entry_names_encoding)
  end
end
