# frozen_string_literal: true
require "minitest/autorun"
require "stringio"
require "zip"

class Zip64CommentContract < Minitest::Test
  def test_zip64_sentinel_records_preserve_archive_comment
    zip64_record = [
      0x06064b50,
      44, 45, 45, 0, 0, 0, 0, 0, 0
    ].pack("VQ<vvVVQ<Q<Q<Q<")
    locator = [
      0x07064b50, 0, 0, 1
    ].pack("VVQ<V")
    ordinary_record = [
      0x06054b50,
      0xffff, 0xffff, 0xffff, 0xffff,
      0xffffffff, 0xffffffff, 3
    ].pack("VvvvvVVv") + "abc"
    directory = Zip::CentralDirectory.new
    directory.read_from_stream(StringIO.new(zip64_record + locator + ordinary_record))
    assert_equal("abc", directory.comment)
    assert_empty(directory.entries)
  end
end
