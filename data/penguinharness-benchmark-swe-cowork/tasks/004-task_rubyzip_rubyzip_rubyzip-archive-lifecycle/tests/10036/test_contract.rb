# frozen_string_literal: true
require 'minitest/autorun'
require 'tmpdir'
require 'stringio'
require 'zip'

class LegacyPublicCallsContract < Minitest::Test
  def test_encryption_round_trip_with_both_zip64_policies
    previous = Zip.write_zip64_support
    [true, false].each do |enabled|
      Zip.write_zip64_support = enabled
      payload = (0..255).to_a.pack('C*') * 130
      buffer = Zip::OutputStream.write_buffer(StringIO.new, Zip::TraditionalEncrypter.new('lifecycle')) do |output|
        output.put_next_entry('encrypted.bin')
        output.write(payload[0, 700])
        output.write(payload[700..-1])
      end
      Zip::InputStream.open(StringIO.new(buffer.string), 0, Zip::TraditionalDecrypter.new('lifecycle')) do |input|
        assert_equal('encrypted.bin', input.get_next_entry.name)
        assert_equal(payload[0, 97], input.read(97))
        assert_equal(payload[97..-1], input.read)
      end
    end
    Zip.reset!
    assert_equal(true, Zip.write_zip64_support)
  ensure
    Zip.write_zip64_support = previous
  end

  def test_reverted_metadata_preserves_bytes_but_real_edit_commits
    Dir.mktmpdir do |root|
      path = File.join(root, 'metadata.zip')
      Zip::File.open(path, create: true) { |archive| archive.get_output_stream('data') { |stream| stream.write('body') } }
      original = File.binread(path)
      Zip::File.open(path) do |archive|
        entry = archive.get_entry('data')
        timestamp = entry.time
        entry.time = timestamp + 120
        assert_equal(true, archive.commit_required?)
        entry.time = timestamp
        assert_equal(false, archive.commit_required?)
      end
      assert_equal(original, File.binread(path))
      Zip::File.open(path) { |archive| archive.get_entry('data').comment = 'persist this change' }
      refute_equal(original, File.binread(path))
      Zip::File.open(path) { |archive| assert_equal('persist this change', archive.get_entry('data').comment) }
    end
  end

  def test_file_create_flag_and_positional_options
    Dir.mktmpdir do |root|
      path = File.join(root, 'legacy.zip')
      archive = Zip::File.new(path, Zip::File::CREATE, false, {restore_times: false})
      archive.get_output_stream('first', 0o640, 'comment') { |stream| stream.write('one') }
      archive.close
      Zip::File.open(path, false, {restore_times: true}) do |opened|
        assert_equal('one', opened.read('first'))
        assert_equal('comment', opened.get_entry('first').comment)
        assert_equal(true, opened.restore_times)
      end
      Zip::File.open(path, create: false) { |opened| assert_equal('one', opened.read('first')) }
    end
  end

  def test_buffer_entry_and_stream_positional_forms
    entry = Zip::Entry.new('', 'item', 'note', '', 0, 0, Zip::Entry::STORED, 0)
    buffer = Zip::File.add_buffer do |archive|
      archive.get_output_stream(entry) { |stream| stream.write('bytes') }
    end
    Zip::File.open_buffer(buffer, {restore_times: false}) do |archive|
      assert_equal('bytes', archive.read('item'))
      assert_equal('note', archive.get_entry('item').comment)
    end
    Zip::InputStream.open(StringIO.new(buffer.string), 0, nil) do |stream|
      assert_equal('item', stream.get_next_entry.name)
      assert_equal('bytes', stream.read)
    end
    output = StringIO.new
    writer = Zip::OutputStream.new(output, true, nil)
    writer.put_next_entry('new', '', nil, Zip::Entry::STORED)
    writer.write('new bytes')
    writer.close_buffer
    Zip::File.open_buffer(StringIO.new(output.string)) { |archive| assert_equal('new bytes', archive.read('new')) }
  end

  def test_legacy_explicit_destination_is_caller_selected
    Dir.mktmpdir do |root|
      buffer = Zip::File.add_buffer { |archive| archive.get_output_stream('entry') { |stream| stream.write('data') } }
      Zip::File.open_buffer(buffer) do |archive|
        target = File.join(root, 'chosen.txt')
        archive.extract('entry', target)
        assert_equal('data', File.read(target))
        assert_raises(Zip::DestinationFileExistsError) { archive.extract('entry', target) }
      end
    end
  end
end
