# frozen_string_literal: true
require "minitest/autorun"
require "stringio"
require "zip"

class FileCountEntriesContract < Minitest::Test
  def test_file_count_entries_accepts_an_io_source
    buffer = Zip::OutputStream.write_buffer do |out|
      out.put_next_entry("one")
      out.write("1")
      out.put_next_entry("two")
      out.write("2")
      out.put_next_entry("three")
      out.write("3")
    end
    assert_equal(3, Zip::File.count_entries(buffer))
  end
end
