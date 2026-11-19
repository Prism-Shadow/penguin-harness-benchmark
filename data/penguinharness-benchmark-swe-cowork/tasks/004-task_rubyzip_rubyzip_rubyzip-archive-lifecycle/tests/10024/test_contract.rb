# frozen_string_literal: true
require 'minitest/autorun'
require 'tmpdir'
require 'zip'
require_relative '../support/archive_fixture'

class UnknownExtraFieldContract < Minitest::Test
  include ArchiveFixture

  def test_local_and_central_bytes_survive_file_edits_and_rewrites
    local = field(0xfefe, "local\x00\xff".b) + field(0xfdfd, 'local-second')
    central = field(0xfefe, 'central-longer') + field(0xfdfd, "\x00central".b)
    representations = {'both' => [local, central], 'local-only' => [local, ''.b],
                       'central-only' => [''.b, central]}
    entries = representations.keys.to_h { |name| [name, "payload-#{name}"] }
    Dir.mktmpdir do |root|
      path = File.join(root, 'unknown.zip')
      File.binwrite(path, archive_bytes(entries, extra_fields: representations))
      assert_wire_representations(File.binread(path), representations)
      2.times do |revision|
        Zip::File.open(path) do |archive|
          entries.each do |name, payload|
            assert_equal(payload, archive.read(name))
            assert_entry_representations(archive.get_entry(name), representations.fetch(name))
            archive.get_entry(name).comment = "edit-#{revision}-#{name}"
          end
          archive.comment = "archive-edit-#{revision}"
        end
        assert_wire_representations(File.binread(path), representations)
        Zip::File.open(path) do |archive|
          assert_equal("archive-edit-#{revision}", archive.comment)
          entries.each do |name, payload|
            assert_equal(payload, archive.read(name))
            assert_equal("edit-#{revision}-#{name}", archive.get_entry(name).comment)
            assert_entry_representations(archive.get_entry(name), representations.fetch(name))
          end
        end
      end
    end
  end

  private

  def field(identifier, bytes)
    [identifier, bytes.bytesize].pack('vv') + bytes
  end

  def opaque_fields(bytes)
    fields = ''.b
    offset = 0
    while offset < bytes.bytesize
      identifier, length = bytes.byteslice(offset, 4).unpack('vv')
      assert_operator(offset + 4 + length, :<=, bytes.bytesize)
      fields << bytes.byteslice(offset, 4 + length) if [0xfefe, 0xfdfd].include?(identifier)
      offset += 4 + length
    end
    fields
  end

  def assert_entry_representations(entry, expected)
    assert_equal(expected.first, opaque_fields(entry.extra.to_local_bin))
    assert_equal(expected.last, opaque_fields(entry.extra.to_c_dir_bin))
  end

  def assert_wire_representations(bytes, expected)
    eocd = bytes.rindex([0x06054b50].pack('V'))
    count = bytes.byteslice(eocd + 10, 2).unpack1('v')
    offset = bytes.byteslice(eocd + 16, 4).unpack1('V')
    observed = {}
    count.times do
      assert_equal(0x02014b50, bytes.byteslice(offset, 4).unpack1('V'))
      name_length, extra_length, comment_length = bytes.byteslice(offset + 28, 6).unpack('vvv')
      local_offset = bytes.byteslice(offset + 42, 4).unpack1('V')
      name = bytes.byteslice(offset + 46, name_length)
      central_extra = bytes.byteslice(offset + 46 + name_length, extra_length)
      assert_equal(0x04034b50, bytes.byteslice(local_offset, 4).unpack1('V'))
      local_name_length, local_extra_length = bytes.byteslice(local_offset + 26, 4).unpack('vv')
      local_extra = bytes.byteslice(local_offset + 30 + local_name_length, local_extra_length)
      observed[name] = [opaque_fields(local_extra), opaque_fields(central_extra)]
      offset += 46 + name_length + extra_length + comment_length
    end
    assert_equal(expected, observed)
  end
end
