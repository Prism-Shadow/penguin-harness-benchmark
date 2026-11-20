# frozen_string_literal: true
require "minitest/autorun"
require "zip"
require "stringio"
require_relative '../support/archive_fixture'

class BinaryCommentContract < Minitest::Test
  include ArchiveFixture

  def test_output_comments_can_contain_end_record_signatures
    signatures = [0x06054b50, 0x06064b50, 0x07064b50].map { |value| [value].pack('V') }
    fake_eocd = [0x06054b50, 0, 0, 0, 0, 0, 0, 0].pack('VvvvvVVv')
    fake_zip64 = [0x06064b50, 44, 45, 45, 0, 0, 0, 0, 0, 0].pack('VQ<vvVVQ<Q<Q<Q<')
    fake_zip64 << [0x07064b50, 0, 0, 1].pack('VVQ<V')
    comments = signatures.flat_map { |signature| ["binary\x00".b + signature, signature + 'middle'] }
    comments += [fake_eocd, fake_zip64, fake_zip64 + fake_eocd,
                 'x' * (65_535 - 4) + signatures.first]
    [{}, {'payload' => "value\x00\xff".b}].each do |entries|
      comments.each do |comment|
        bytes = output_archive_bytes(entries, comment: comment)
        assert_archive(bytes, entries, comment)
        assert_entry_counts(bytes, entries.size)
      end
    end
  end

  def test_truncated_end_records_and_comments_remain_invalid
    bytes = output_archive_bytes({'payload' => 'body'}, comment: 'complete')
    [1, 8, 9, 20, 29].each do |missing|
      truncated = bytes.byteslice(0, bytes.bytesize - missing)
      assert_raises(Zip::Error) { Zip::CentralDirectory.new.read_from_stream(StringIO.new(truncated)) }
      assert_raises(Zip::Error) { Zip::CentralDirectory.new.count_entries(StringIO.new(truncated)) }
      assert_raises(Zip::Error) { Zip::File.open_buffer(StringIO.new(truncated)) }
    end
  end

  def test_locator_bytes_in_entry_comment_are_not_a_zip64_locator
    previous = Zip.write_zip64_support
    Zip.write_zip64_support = false
    entry_comment = [0x07064b50, 0, 0, 1].pack('VVQ<V')
    bytes = Zip::OutputStream.write_buffer do |output|
      output.put_next_entry('payload', entry_comment)
      output.write('body')
    end.string
    assert_archive(bytes, {'payload' => 'body'}, '')
    assert_entry_counts(bytes, 1)
    Zip::File.open_buffer(StringIO.new(bytes)) do |archive|
      assert_equal(entry_comment, archive.get_entry('payload').comment)
    end
  ensure
    Zip.write_zip64_support = previous
  end
end
