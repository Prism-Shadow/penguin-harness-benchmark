# frozen_string_literal: true
require "minitest/autorun"
require "zip"
require "stringio"
require_relative '../support/archive_fixture'

class EocdUnpackingContract < Minitest::Test
  include ArchiveFixture

  def test_ordinary_eocd_unpacking_preserves_comment_and_fields
    ['', 'ordinary-comment', "binary\x00comment"].each_with_index do |comment, index|
      entries = (0...index).to_h { |number| ["item-#{number}", "data-#{number}" * (number + 1)] }
      assert_archive(archive_bytes(entries, comment: comment), entries, comment)
    end
  end

  def test_missing_end_record_fails_at_reader_boundary
    bytes = archive_bytes({'payload' => 'value'})
    assert_raises(Zip::Error) { Zip::File.open_buffer(StringIO.new(bytes[0...-22])) }
  end
end
