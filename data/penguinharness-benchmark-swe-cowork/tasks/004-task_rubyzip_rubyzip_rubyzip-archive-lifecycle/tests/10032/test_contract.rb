# frozen_string_literal: true
require "minitest/autorun"
require "stringio"
require "tempfile"
require "zip"

class CommitRequiredCompatibilityContract < Minitest::Test
  def test_comment_mutation_requires_a_commit
    buffer = StringIO.new
    Zip::OutputStream.write_buffer(buffer) do |out|
      out.put_next_entry("payload")
      out.write("x")
    end
    file = Tempfile.new(["rubyzip-commit", ".zip"])
    begin
      file.binmode
      file.write(buffer.string)
      file.close
      archive = Zip::File.open(file.path)
      assert_equal(false, archive.commit_required?)
      archive.comment = "changed"
      assert_equal(true, archive.commit_required?)
    ensure
      file.unlink
    end
  end
end
