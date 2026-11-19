# frozen_string_literal: true
require "minitest/autorun"
require "zip"
require_relative '../support/archive_fixture'

class Zip64UnpackingContract < Minitest::Test
  include ArchiveFixture

  def test_zip64_eocd_unpacking_keeps_record_boundaries
    [0, 1, 3].each do |count|
      entries = (0...count).to_h { |number| ["zip64-#{number}", "payload-#{number}" * (number + 1)] }
      comment = "zip64-comment-#{count}"
      assert_archive(archive_bytes(entries, comment: comment, zip64: true), entries, comment)
    end
  end

  def test_incomplete_archive_is_not_an_empty_archive
    assert_raises(Zip::Error) do
      Zip::File.open_buffer(StringIO.new(archive_bytes({}, zip64: true)[0, 8]))
    end
  end

  def test_real_zip64_output_ignores_signatures_inside_maximum_comment
    entries = (0...65_535).to_h { |number| ["entry-#{number}", number.zero? ? 'payload' : ''] }
    signatures = [0x06064b50, 0x07064b50, 0x06054b50].pack('V*')
    comment = 'c' * (65_535 - signatures.bytesize) + signatures
    bytes = output_archive_bytes(entries, comment: comment, zip64: true)
    locator_offset = bytes.bytesize - comment.bytesize - 22 - 20
    assert_equal(0x07064b50, bytes.byteslice(locator_offset, 4).unpack1('V'))
    directory = Zip::CentralDirectory.new.read_from_stream(StringIO.new(bytes))
    assert_equal(comment, directory.comment)
    assert_equal(entries.keys.sort, directory.entries.map(&:name).sort)
    assert_entry_counts(bytes, entries.size)
    Zip::File.open_buffer(StringIO.new(bytes)) do |archive|
      assert_equal(comment, archive.comment)
      assert_equal(entries.size, archive.size)
      assert_equal('payload', archive.read('entry-0'))
      assert_equal('', archive.read('entry-65534'))
    end
  end
end
