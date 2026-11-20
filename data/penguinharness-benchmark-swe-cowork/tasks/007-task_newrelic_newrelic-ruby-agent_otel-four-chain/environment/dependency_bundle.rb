require 'digest'
require 'fileutils'
require 'json'
require 'net/http'
require 'rubygems/package'
require 'uri'

module DependencyBundle
  ROOT = File.expand_path(__dir__)

  def self.versions(path = File.join(ROOT, 'dependency-versions.json'))
    document = JSON.parse(File.read(path))
    raise 'Invalid dependency schema' unless document['schema'] == 'newrelic-offline-development-versions-v1'
    pins = document.fetch('gems')
    raise 'Empty dependency lock' if pins.empty?
    pins.each do |name, version|
      raise 'Invalid gem name/version' unless name.match?(/\A[a-zA-Z0-9_-]+\z/) && version.match?(/\A\d+(\.\d+)+\z/)
    end
    pins
  end

  def self.download(url)
    uri = URI(url)
    raise 'Non-registry dependency URL' unless uri.scheme == 'https' && uri.host == 'rubygems.org'
    response = Net::HTTP.start(uri.host, uri.port, :use_ssl => true, :open_timeout => 30, :read_timeout => 120) do |http|
      http.get(uri.request_uri)
    end
    raise "Registry request failed: #{url}: #{response.code}" unless response.is_a?(Net::HTTPSuccess)
    response.body
  end

  def self.acquire(directory, pins = versions)
    FileUtils.mkdir_p(directory)
    receipt = {'schema' => 'newrelic-offline-development-cache-v1', 'gems' => {}}
    pins.each do |name, version|
      metadata_url = "https://rubygems.org/api/v2/rubygems/#{name}/versions/#{version}.json?platform=ruby"
      metadata_body = download(metadata_url)
      metadata = JSON.parse(metadata_body)
      raise "Wrong registry identity: #{name}" unless metadata.values_at('name', 'version', 'platform') == [name, version, 'ruby']
      checksum = metadata.fetch('sha')
      raise "Invalid registry checksum: #{name}" unless checksum.match?(/\A[0-9a-f]{64}\z/)
      filename = "#{name}-#{version}.gem"
      package_url = "https://rubygems.org/gems/#{filename}"
      package = download(package_url)
      raise "Registry checksum mismatch: #{filename}" unless Digest::SHA256.hexdigest(package) == checksum
      File.binwrite(File.join(directory, filename), package)
      receipt['gems'][name] = {'version' => version, 'sha256' => checksum, 'url' => package_url,
                               'metadata_url' => metadata_url, 'metadata_sha256' => Digest::SHA256.hexdigest(metadata_body)}
      puts "Acquired #{filename} sha256=#{checksum}"
    end
    File.write(File.join(directory, 'inventory.json'), JSON.pretty_generate(receipt) + "\n")
    verify(directory, pins)
  end

  def self.verify(directory, pins = versions, ruby_version = RUBY_VERSION)
    receipt = JSON.parse(File.read(File.join(directory, 'inventory.json')))
    raise 'Invalid cache schema' unless receipt['schema'] == 'newrelic-offline-development-cache-v1'
    records = receipt.fetch('gems')
    raise 'Cache inventory differs from version lock' unless records.keys.sort == pins.keys.sort
    expected = pins.map { |name, version| "#{name}-#{version}.gem" }.sort
    raise 'Missing or extra cached gems' unless Dir.children(directory).grep(/\.gem\z/).sort == expected
    specifications = {}
    pins.each do |name, version|
      path = File.join(directory, "#{name}-#{version}.gem")
      record = records.fetch(name)
      raise "Invalid cached version: #{name}" unless record.fetch('version') == version
      raise "Symlink package: #{name}" if File.symlink?(path)
      raise "Package checksum mismatch: #{name}" unless Digest::SHA256.file(path).hexdigest == record.fetch('sha256')
      package = Gem::Package.new(path)
      package.verify
      specification = package.spec
      unless specification.name == name && specification.version.to_s == version && specification.platform.to_s == 'ruby'
        raise "Package identity mismatch: #{name}"
      end
      unless specification.required_ruby_version.satisfied_by?(Gem::Version.new(ruby_version))
        raise "Unsupported Ruby for #{name}: #{ruby_version}"
      end
      specifications[name] = specification
    end
    specifications.each_value do |specification|
      specification.runtime_dependencies.each do |dependency|
        target = specifications[dependency.name]
        unless target && dependency.requirement.satisfied_by?(target.version)
          raise "Unclosed runtime dependency: #{specification.full_name} -> #{dependency}"
        end
      end
    end
    puts "Verified #{specifications.length} exact packages, SHA256, Ruby compatibility and complete runtime dependency closure"
    specifications
  end

  def self.verify_upstream(directory, repository)
    document = JSON.parse(File.read(File.join(ROOT, 'dependency-versions.json')))
    requirement = Gem::Requirement.new(*document.fetch('ruby').split(',').map(&:strip))
    raise "Unsupported development Ruby: #{RUBY_VERSION}" unless requirement.satisfied_by?(Gem::Version.new(RUBY_VERSION))
    pins = versions
    specifications = verify(directory, pins)
    raise 'CI/ENABLE_PRY would change the pinned development profile' if ENV['CI'] || ENV['ENABLE_PRY']
    upstream = Dir.chdir(repository) { Gem::Specification.load(File.join(repository, 'newrelic_rpm.gemspec')) }
    raise 'Cannot load upstream gemspec' unless upstream
    upstream.dependencies.each do |dependency|
      target = specifications[dependency.name]
      unless target && dependency.requirement.satisfied_by?(target.version)
        raise "Unclosed upstream dependency: #{dependency}"
      end
    end
    puts "All #{upstream.dependencies.length} upstream development/runtime declarations are satisfied; no groups excluded"
  end
end

if $PROGRAM_NAME == __FILE__
  command, directory, repository = ARGV
  case command
  when 'acquire'
    DependencyBundle.acquire(File.expand_path(directory))
  when 'verify'
    DependencyBundle.verify(File.expand_path(directory))
  when 'upstream'
    DependencyBundle.verify_upstream(File.expand_path(directory), File.expand_path(repository))
  else
    abort 'Usage: ruby dependency_bundle.rb acquire|verify CACHE; upstream CACHE REPOSITORY'
  end
end
