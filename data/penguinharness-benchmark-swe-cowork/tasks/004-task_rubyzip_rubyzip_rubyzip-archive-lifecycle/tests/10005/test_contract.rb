# frozen_string_literal: true
require "minitest/autorun"
require "tmpdir"
require "zip"

class SeparatorNormalizationContract < Minitest::Test
  def test_backslash_names_are_looked_up_with_forward_slashes
    Dir.mktmpdir do |dir|
      path = File.join(dir, "separators.zip")
      Zip::OutputStream.open(path) do |out|
        out.put_next_entry("dir\\payload.txt", "", nil, Zip::Entry::STORED)
        out.write("ok")
      end
      archive = Zip::File.open(path)
      assert_equal("ok", archive.read("dir/payload.txt"))
    end
  end
end
