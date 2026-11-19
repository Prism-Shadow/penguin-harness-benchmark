# frozen_string_literal: true
require 'stringio'
require 'zlib'

module ArchiveFixture
  def archive_bytes(entries, comment: '', zip64: false, extra_fields: {})
    local = ''.b
    central = ''.b
    entries.each do |name, payload|
      local_extra, central_extra = extra_fields.fetch(name, [''.b, ''.b])
      offset = local.bytesize
      crc = Zlib.crc32(payload)
      local << [0x04034b50, 20, 0, 0, 0, 33, crc, payload.bytesize,
                payload.bytesize, name.bytesize, local_extra.bytesize].pack('VvvvvvVVVvv') << name << local_extra << payload
      central << [0x02014b50, 20, 20, 0, 0, 0, 33, crc, payload.bytesize,
                  payload.bytesize, name.bytesize, central_extra.bytesize, 0, 0, 0, 0, offset].pack('VvvvvvvVVVvvvvvVV') << name << central_extra
    end
    bytes = local + central
    if zip64
      record_offset = bytes.bytesize
      bytes << [0x06064b50, 44, 45, 45, 0, 0, entries.size, entries.size,
                central.bytesize, local.bytesize].pack('VQ<vvVVQ<Q<Q<Q<')
      bytes << [0x07064b50, 0, record_offset, 1].pack('VVQ<V')
    end
    count = zip64 ? 0xffff : entries.size
    size = zip64 ? 0xffffffff : central.bytesize
    offset = zip64 ? 0xffffffff : local.bytesize
    bytes << [0x06054b50, 0, 0, count, count, size, offset, comment.bytesize].pack('VvvvvVVv') << comment
  end

  def output_archive_bytes(entries, comment:, zip64: false)
    previous = Zip.write_zip64_support
    Zip.write_zip64_support = zip64
    Zip::OutputStream.write_buffer do |output|
      output.comment = comment
      entries.each do |name, payload|
        output.put_next_entry(name, '', nil, Zip::Entry::STORED)
        output.write(payload)
      end
    end.string
  ensure
    Zip.write_zip64_support = previous
  end

  def assert_entry_counts(bytes, expected)
    counter = Zip::CentralDirectory.new
    2.times do
      io = StringIO.new(bytes.dup)
      assert_equal(expected, counter.count_entries(io))
      assert_equal(expected, Zip::File.count_entries(io))
      refute(io.closed?)
      assert_equal(bytes, io.string)
    end
  end

  def assert_archive(bytes, entries, comment)
    directory = Zip::CentralDirectory.new
    directory.read_from_stream(StringIO.new(bytes))
    assert_equal(comment, directory.comment)
    assert_equal(entries.keys.sort, directory.entries.map(&:name).sort)
    assert_equal(entries.values.map(&:bytesize).sort, directory.entries.map(&:size).sort)
    Zip::File.open_buffer(StringIO.new(bytes)) do |archive|
      assert_equal(comment, archive.comment)
      assert_equal(entries.size, archive.size)
      entries.each { |name, payload| assert_equal(payload, archive.read(name)) }
    end
  end
end
