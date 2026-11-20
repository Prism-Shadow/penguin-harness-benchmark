# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class DataDescriptorStreamingErrorContract < Minitest::Test
  def test_unknown_local_sizes_are_rejected
    path = File.join(ENV.fetch("NODE_SUPPORT_DIR"), "gpbit3stored.zip")
    error = nil
    Zip::File.open(path) do |archive|
      stream = archive.get_input_stream("file1.txt")
      error = assert_raises(Zip::Error) { stream.get_next_entry }
    end
    assert_match(/(bit 3|metadata|local header)/i, error.message)
    assert_match(/InputStream|local header/i, error.message)
  end
end
