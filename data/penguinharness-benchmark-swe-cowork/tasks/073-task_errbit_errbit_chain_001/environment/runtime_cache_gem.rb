require 'bundler'
require 'digest'
require 'fileutils'
require 'json'
require 'net/http'
require 'openssl'
require 'optparse'
require 'rubygems/package'
require 'tempfile'
require 'tmpdir'
require 'uri'

module TaskLockedGemCache
  ORIGIN = 'https://rubygems.org/'.freeze
  MAX_BYTES = 32 * 1024 * 1024

  class PublisherMetadataError < RuntimeError
    attr_reader :receipt

    def initialize(receipt)
      @receipt = receipt
      super "Publisher metadata must identify one exact locked gem version and platform; " \
            "#{receipt.fetch(:reason)} for #{receipt.fetch(:required_archive)}. " \
            'Provide an independently reviewed exact archive and checksum; do not change the lockfile.'
    end
  end

  def self.publisher_record(raw_metadata, expected, filename, lock_contents, metadata_uri)
    raw_contents = File.binread(raw_metadata)
    receipt = {
      schema: 'task-publisher-metadata-failure-v1', status: 'environment_error',
      source: metadata_uri.to_s, publisher_metadata_sha256: Digest::SHA256.hexdigest(raw_contents),
      lock_sha256: Digest::SHA256.hexdigest(lock_contents), required_archive: filename,
      expected: { name: expected.name, version: expected.version.to_s, platform: expected.platform.to_s }
    }
    begin
      document = JSON.parse(raw_contents)
    rescue JSON::ParserError
      raise PublisherMetadataError.new(receipt.merge(reason: 'invalid_json'))
    end
    unless document.is_a?(Array)
      raise PublisherMetadataError.new(receipt.merge(reason: 'invalid_document_type'))
    end
    candidates = document.select do |record|
      next false unless record.is_a?(Hash)
      next false if record['name'] && record['name'] != expected.name
      version = record['version'] || record['number']
      version == expected.version.to_s && record['platform'] == 'ruby'
    end
    unless candidates.length == 1
      identities = document.select { |record| record.is_a?(Hash) }.map do |record|
        record.select { |key, _value| %w[name version number platform yanked].include?(key) }
      end
      reason = candidates.empty? ? 'missing_exact_record' : 'ambiguous_exact_record'
      raise PublisherMetadataError.new(receipt.merge(
        reason: reason, record_count: document.length, match_count: candidates.length,
        observed_identities: identities.first(64), identities_truncated: identities.length > 64
      ))
    end
    metadata = candidates.fetch(0)
    unless metadata['sha'].is_a?(String) && metadata['sha'].match(/\A[0-9a-f]{64}\z/) &&
           metadata['yanked'] != true
      raise PublisherMetadataError.new(receipt.merge(reason: 'invalid_checksum_or_yanked_record'))
    end
    metadata
  end

  def self.download(uri, output, redirects: 3, max_bytes: MAX_BYTES)
    unless uri.scheme == 'https' && uri.host == 'rubygems.org' && uri.port == 443 && !uri.userinfo && !uri.fragment
      raise 'Only the canonical HTTPS RubyGems origin is allowed'
    end
    connection = Net::HTTP.new(uri.host, uri.port)
    connection.use_ssl = true
    connection.verify_mode = OpenSSL::SSL::VERIFY_PEER
    connection.open_timeout = 30
    connection.read_timeout = 60
    connection.start do |http|
      http.request(Net::HTTP::Get.new(uri.request_uri)) do |response|
        if response.is_a?(Net::HTTPRedirection)
          raise 'RubyGems redirect limit exceeded' unless redirects > 0
          location = response['location']
          raise 'RubyGems redirect has no location' unless location && !location.empty?
          return download(URI.join(uri.to_s, location), output, redirects: redirects - 1, max_bytes: max_bytes)
        end
        unless response.is_a?(Net::HTTPSuccess)
          raise "Gem download failed: HTTP #{response.code} for #{uri}; " \
                'provide an independently reviewed exact archive and checksum in the build archive manifest'
        end
        response.read_body do |chunk|
          raise 'Gem download exceeds size limit' if output.size + chunk.bytesize > max_bytes
          output.write(chunk)
        end
      end
    end
  end

  def self.locked_gem(lockfile, name)
    lock_contents = File.binread(lockfile)
    lock_directory = File.dirname(File.expand_path(lockfile))
    lock = Dir.chdir(lock_directory) { Bundler::LockfileParser.new(lock_contents) }
    matches = lock.specs.select { |spec| spec.name == name }
    raise "Expected one locked platform for #{name}" unless matches.length == 1
    expected = matches.fetch(0)
    unless expected.source.is_a?(Bundler::Source::Rubygems) && expected.source.remotes.map(&:to_s) == [ORIGIN]
      raise 'Locked gem must come only from the canonical HTTPS RubyGems origin'
    end
    filename = "#{expected.full_name}.gem"
    raise 'Unsafe locked gem filename' unless filename.match(/\A[A-Za-z0-9][A-Za-z0-9_.-]*\.gem\z/)
    [lock_contents, expected, filename]
  end

  def self.prepare_archive(lockfile:, cache_dir:, name:, archive_manifest:,
                           metadata_fetcher: nil, gem_fetcher: method(:download))
    raise 'An archive manifest is required for preparation' unless archive_manifest
    lock_contents, expected, filename = locked_gem(lockfile, name)
    pin = archive_pin(archive_manifest, filename, lock_contents)
    if pin
      return cache(lockfile: lockfile, cache_dir: cache_dir, name: name,
                   archive_manifest: archive_manifest, require_archive: true)
    end
    raise 'Publisher acquisition requires the locked ruby platform' unless expected.platform.to_s == 'ruby'
    metadata_uri = URI("#{ORIGIN}api/v1/versions/#{expected.name}.json")
    gem_uri = URI("#{ORIGIN}downloads/#{filename}")
    directory = File.dirname(archive_manifest)
    archive_path = File.join(directory, filename)
    metadata_path = File.join(directory, "#{expected.full_name}.publisher.json")
    [archive_path, metadata_path].each do |path|
      raise 'Refusing to overwrite an unpinned archive or publisher record' if File.exist?(path) || File.symlink?(path)
    end
    manifest = JSON.parse(File.read(archive_manifest))
    Dir.mktmpdir('publisher-', directory) do |staging|
      raw_metadata = File.join(staging, 'publisher.json')
      File.open(raw_metadata, 'w+b') do |output|
        if metadata_fetcher
          metadata_fetcher.call(metadata_uri, output)
        else
          download(metadata_uri, output, max_bytes: 1024 * 1024)
        end
      end
      raise 'Publisher metadata exceeds size limit' if File.size(raw_metadata) > 1024 * 1024
      metadata = publisher_record(raw_metadata, expected, filename, lock_contents, metadata_uri)
      downloaded = File.join(staging, filename)
      File.open(downloaded, 'w+b') { |output| gem_fetcher.call(gem_uri, output) }
      unless Digest::SHA256.file(downloaded).hexdigest == metadata.fetch('sha')
        raise 'Archive SHA256 does not match the publisher metadata'
      end
      verify(downloaded, expected)
      manifest['archives'][filename] = {
        'sha256' => metadata.fetch('sha'),
        'lock_sha256' => Digest::SHA256.hexdigest(lock_contents),
        'provenance' => metadata_uri.to_s
      }
      staged_manifest = File.join(staging, 'manifest.json')
      File.write(staged_manifest, JSON.pretty_generate(manifest) + "\n")
      receipt = cache(lockfile: lockfile, cache_dir: cache_dir, name: name,
                      archive_manifest: staged_manifest, require_archive: true)
      File.rename(downloaded, archive_path)
      File.rename(raw_metadata, metadata_path)
      File.rename(staged_manifest, archive_manifest)
      return receipt.merge(publisher_metadata_sha256: Digest::SHA256.file(metadata_path).hexdigest,
                           publisher_metadata: metadata_uri.to_s, archive_endpoint: gem_uri.to_s)
    end
  end

  def self.dependencies(spec)
    spec.dependencies.select { |dependency| dependency.type == :runtime }.map do |dependency|
      [dependency.name, dependency.requirement.requirements.map { |operator, version| [operator, version.to_s] }.sort]
    end.sort
  end

  def self.verify(path, expected)
    raise 'Gem download exceeds size limit' if File.size(path) > MAX_BYTES
    package = Gem::Package.new(path)
    package.verify
    actual = package.spec
    unless actual.name == expected.name && actual.version == expected.version && actual.platform == expected.platform
      raise "Gem identity does not match lock: #{expected.full_name}"
    end
    raise 'Gem runtime dependencies do not match lock' unless dependencies(actual) == dependencies(expected)
  end

  def self.archive_pin(manifest_path, filename, lock_contents)
    return unless manifest_path
    raise 'Archive manifest must be a regular file, not a symlink' unless File.file?(manifest_path) && !File.symlink?(manifest_path)
    manifest = JSON.parse(File.read(manifest_path))
    unless manifest.is_a?(Hash) && manifest.keys.sort == %w[archives schema] &&
           manifest['schema'] == 'task-locked-gem-archives-v1' && manifest['archives'].is_a?(Hash)
      raise 'Invalid independent archive manifest'
    end
    return unless manifest['archives'].key?(filename)
    pin = manifest['archives'].fetch(filename)
    unless pin.is_a?(Hash) && pin.keys.sort == %w[lock_sha256 provenance sha256] &&
           %w[sha256 lock_sha256].all? { |key| pin[key].is_a?(String) && pin[key].match(/\A[0-9a-f]{64}\z/) }
      raise 'Invalid independent archive pin'
    end
    unless pin['lock_sha256'] == Digest::SHA256.hexdigest(lock_contents)
      raise 'Archive pin does not match the current lockfile'
    end
    provenance = URI.parse(pin['provenance']) if pin['provenance'].is_a?(String)
    unless provenance.is_a?(URI::HTTPS) && provenance.host && !provenance.userinfo && !provenance.fragment
      raise 'Archive provenance must be a reviewed HTTPS source'
    end
    archive = File.join(File.dirname(manifest_path), filename)
    raise 'Pinned archive must be a regular file, not a symlink' unless File.file?(archive) && !File.symlink?(archive)
    pin.merge('path' => archive)
  rescue JSON::ParserError, URI::InvalidURIError => error
    raise "Invalid independent archive manifest: #{error.message}"
  end

  def self.copy_archive(pin, output)
    File.open(pin.fetch('path'), 'rb') do |archive|
      while (chunk = archive.read(64 * 1024))
        raise 'Gem download exceeds size limit' if output.size + chunk.bytesize > MAX_BYTES
        output.write(chunk)
      end
    end
    output.flush
    unless Digest::SHA256.file(output.path).hexdigest == pin.fetch('sha256')
      raise 'Archive SHA256 does not match its independent pin'
    end
  end

  def self.cache(lockfile:, cache_dir:, name:, archive_manifest: nil, require_archive: false, fetcher: method(:download))
    lock_contents, expected, filename = locked_gem(lockfile, name)
    uri = URI("#{ORIGIN}gems/#{filename}")
    pin = archive_pin(archive_manifest, filename, lock_contents)
    if require_archive && !pin
      raise "Required independently pinned archive is missing: #{filename}; " \
            "lock SHA256 #{Digest::SHA256.hexdigest(lock_contents)}. " \
            'Supply the reviewed exact archive and manifest before building; network fallback is disabled'
    end
    FileUtils.mkdir_p(cache_dir)
    target = File.join(cache_dir, filename)
    receipt = nil
    temporary = Tempfile.new(['locked-gem-', '.partial'], cache_dir)
    begin
      temporary.binmode
      if pin
        copy_archive(pin, temporary)
      else
        fetcher.call(uri, temporary)
      end
      temporary.flush
      verify(temporary.path, expected)
      receipt = {
        name: expected.name, version: expected.version.to_s, platform: expected.platform.to_s,
        source: pin ? pin.fetch('provenance') : uri.to_s,
        transport: pin ? 'audited_archive' : 'canonical_https',
        sha256: Digest::SHA256.file(temporary.path).hexdigest,
        lock_sha256: Digest::SHA256.hexdigest(lock_contents),
        integrity: "#{pin ? 'Independently SHA256-pinned archive' : 'TLS-authenticated download'}; " \
                   'RubyGems package checksums and exact locked metadata'
      }
      File.rename(temporary.path, target)
    ensure
      temporary.close!
    end
    File.write("#{target}.receipt.json", JSON.pretty_generate(receipt) + "\n")
    receipt
  end
end

if $PROGRAM_NAME == __FILE__
  options = { require_archive: false }
  prepare_archive = false
  parser = OptionParser.new do |arguments|
    arguments.banner = 'Usage: runtime_cache_gem.rb [--require-archive | --prepare-archive] GEMFILE_LOCK CACHE_DIRECTORY GEM_NAME [ARCHIVE_MANIFEST]'
    arguments.on('--require-archive', 'Require an independently pinned local archive; never fall back to a download') do
      options[:require_archive] = true
    end
    arguments.on('--prepare-archive', 'Acquire an exact archive using an independent canonical publisher checksum') do
      prepare_archive = true
    end
  end
  begin
    parser.parse!(ARGV)
  rescue OptionParser::ParseError => error
    abort "#{error.message}\n#{parser}"
  end
  abort parser.to_s unless [3, 4].include?(ARGV.length)
  abort 'Archive preparation and strict offline restoration are separate modes' if prepare_archive && options[:require_archive]
  arguments = { lockfile: ARGV[0], cache_dir: ARGV[1], name: ARGV[2], archive_manifest: ARGV[3] }
  begin
    receipt = if prepare_archive
                TaskLockedGemCache.prepare_archive(**arguments)
              else
                TaskLockedGemCache.cache(**arguments.merge(options))
              end
  rescue TaskLockedGemCache::PublisherMetadataError => error
    warn JSON.generate(error.receipt)
    warn error.message
    exit 2
  end
  puts JSON.pretty_generate(receipt)
end
