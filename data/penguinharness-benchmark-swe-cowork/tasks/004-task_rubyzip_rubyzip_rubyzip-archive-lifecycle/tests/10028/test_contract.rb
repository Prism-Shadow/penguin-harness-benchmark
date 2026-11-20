# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class OutputCentralDirectoryContract < Minitest::Test
  def test_output_stream_round_trips_through_file_reader
    buffer = Zip::OutputStream.write_buffer do |out|
      out.comment = "integrated"
      out.put_next_entry("payload.txt")
      out.write("payload")
    end
    Zip::File.open_buffer(buffer) do |archive|
      assert_equal("integrated", archive.comment)
      assert_equal("payload", archive.read("payload.txt"))
    end
  end
end
