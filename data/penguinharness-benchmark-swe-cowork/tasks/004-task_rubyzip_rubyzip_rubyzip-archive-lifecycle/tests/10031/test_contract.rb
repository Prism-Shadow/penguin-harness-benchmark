# frozen_string_literal: true
require "zip"
require "minitest/autorun"

class CentralDirtyStateContract < Minitest::Test
  def test_directory_becomes_dirty_when_an_entry_is_added
    directory = Zip::CentralDirectory.new
    assert_equal(false, directory.dirty?)
    directory << Zip::Entry.new("archive.zip", "payload")
    assert_equal(true, directory.dirty?)
  end
end
