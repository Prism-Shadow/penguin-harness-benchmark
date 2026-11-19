# frozen_string_literal: true
require "minitest/autorun"
require "stringio"
require "tmpdir"
require "zip"

class InputStreamSizeContract < Minitest::Test
  def test_size_tracks_the_selected_entry
    Dir.mktmpdir do |dir|
      archive = File.join(dir, "size.zip")
      Zip::OutputStream.open(archive) do |out|
        out.put_next_entry("payload.txt")
        out.write("payload")
      end
      Zip::InputStream.open(archive) do |stream|
        assert_nil(stream.size)
        stream.get_next_entry
        assert_equal(7, stream.size)
      end
    end
  end
end
