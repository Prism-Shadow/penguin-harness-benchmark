# Real optional decoder boundary backed by the image's native libzstd. This
# creates and decodes actual zstd frames; it does not model expected output.
require 'fiddle/import'
module NativeZstdProbe
  extend Fiddle::Importer
  begin
    dlload 'libzstd.so.1'
  rescue Fiddle::DLError => error
    raise LoadError, "native zstd validation dependency missing: #{error.message}"
  end
  extern 'size_t ZSTD_compressBound(size_t)'
  extern 'size_t ZSTD_compress(void*, size_t, const void*, size_t, int)'
  extern 'unsigned long long ZSTD_getFrameContentSize(const void*, size_t)'
  extern 'size_t ZSTD_decompress(void*, size_t, const void*, size_t)'
  extern 'unsigned int ZSTD_isError(size_t)'
  extern 'unsigned int ZSTD_versionNumber()'
  def self.compress(input)
    output = "\x00".b * ZSTD_compressBound(input.bytesize)
    size = ZSTD_compress(output, output.bytesize, input, input.bytesize, 3)
    raise 'native zstd compression failed' unless ZSTD_isError(size).zero?
    output.byteslice(0, size)
  end
end
module Zstd
  def self.decompress(frame)
    size = NativeZstdProbe.ZSTD_getFrameContentSize(frame, frame.bytesize)
    raise ArgumentError, 'invalid zstd frame' unless size.between?(0, 10_000_000)
    output = "\x00".b * size
    actual = NativeZstdProbe.ZSTD_decompress(output, size, frame, frame.bytesize)
    raise ArgumentError, 'native zstd rejected frame' unless NativeZstdProbe.ZSTD_isError(actual).zero?
    output.byteslice(0, actual)
  end
end
