# frozen_string_literal: true
require "minitest/autorun"
require "tmpdir"
require "zip"

class CrossPlatformTimestampContract < Minitest::Test
  def test_fat_entries_receive_the_archive_timestamp
    Dir.mktmpdir do |dir|
      destination = File.join(dir, "restored.txt")
      File.write(destination, "x")
      target = Time.at(946684800)
      entry = Zip::Entry.new("archive.zip", "restored.txt", time: target)
      entry.fstype = Zip::FSTYPE_FAT
      entry.restore_times = true
      entry.send(:set_extra_attributes_on_path, destination)
      assert((File.mtime(destination) - target).abs < 3)
    end
  end
end
