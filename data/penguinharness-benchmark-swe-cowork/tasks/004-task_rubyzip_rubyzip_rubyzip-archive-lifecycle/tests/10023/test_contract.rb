# frozen_string_literal: true
require "fileutils"
require "minitest/autorun"
require "tmpdir"
require "zip"

class SortedArchiveNoRewriteContract < Minitest::Test
  def test_sorting_does_not_mutate_an_untouched_archive
    Dir.mktmpdir do |dir|
      path = File.join(dir, "ordered.zip")
      Zip::OutputStream.open(path) do |out|
        out.put_next_entry("b.txt")
        out.write("b")
        out.put_next_entry("a.txt")
        out.write("a")
      end
      before = File.binread(path)
      Zip.sort_entries = true
      Zip::File.open(path) { |archive| assert_equal(["a.txt", "b.txt"], archive.entries.map(&:name)) }
      assert_equal(before, File.binread(path))
    ensure
      Zip.reset!
    end
  end
end
