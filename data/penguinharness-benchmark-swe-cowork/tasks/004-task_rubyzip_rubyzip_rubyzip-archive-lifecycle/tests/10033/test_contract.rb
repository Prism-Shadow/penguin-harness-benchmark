# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class EntryDirtyWriterContract < Minitest::Test
  def test_dirty_status_has_no_public_writer
    entry = Zip::Entry.new("archive.zip", "payload")
    refute_respond_to(entry, :dirty=)
    assert_respond_to(entry, :dirty?)
  end
end
