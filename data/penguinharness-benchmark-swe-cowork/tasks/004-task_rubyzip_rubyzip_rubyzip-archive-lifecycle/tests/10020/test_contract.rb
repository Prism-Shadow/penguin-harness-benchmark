# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class OsxStreamingErrorContract < Minitest::Test
  def test_osx_archive_reports_incomplete_local_metadata
    path = File.join(ENV.fetch("NODE_SUPPORT_DIR"), "osx-archive.zip")
    error = assert_raises(Zip::Error) do
      Zip::InputStream.open(path) { |stream| stream.get_next_entry }
    end
    assert_match(/(bit 3|metadata|local header)/i, error.message)
  end
end
