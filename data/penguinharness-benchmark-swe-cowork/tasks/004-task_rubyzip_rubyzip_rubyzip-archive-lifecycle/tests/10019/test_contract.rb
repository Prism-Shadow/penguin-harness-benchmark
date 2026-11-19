# frozen_string_literal: true
require "minitest/autorun"
require "stringio"
require "zip"

class EmptyInputStreamStateContract < Minitest::Test
  def test_empty_io_has_no_current_entry
    Zip::InputStream.open(StringIO.new) do |stream|
      assert_nil(stream.get_next_entry)
    end
  end
end
