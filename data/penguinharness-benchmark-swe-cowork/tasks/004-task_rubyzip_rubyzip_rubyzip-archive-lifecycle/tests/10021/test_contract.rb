# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class SplitArchiveErrorContract < Minitest::Test
  def test_split_signature_is_not_silently_accepted
    path = File.join(ENV.fetch("NODE_SUPPORT_DIR"), "invalid-split.zip")
    assert_raises(Zip::SplitArchiveError) do
      Zip::InputStream.open(path) { |stream| stream.get_next_entry }
    end
  end
end
