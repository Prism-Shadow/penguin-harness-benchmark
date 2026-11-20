require 'digest'

# External dependency versions remain frozen. The local project version and
# runtime dependencies are read from its current source gemspec, not a reference
# implementation fingerprint. Missing offline dependencies fail explicitly.
module HTTPartyHistoricalLock
  def self.resolve(repository, root, profile)
    entries = profile.fetch('locks').select do |entry|
      entry.fetch('source_hashes').all? do |relative, expected|
        path = File.join(repository, relative)
        File.file?(path) && Digest::SHA256.file(path).hexdigest == expected
      end
    end
    raise 'No unique verified dependency template matches the current Gemfile' unless entries.length == 1
    entry = entries.first
    template = File.binread(File.join(root, entry.fetch('file')))
    raise 'Frozen dependency template hash mismatch' unless Digest::SHA256.hexdigest(template) == entry.fetch('sha256')
    specification = Dir.chdir(repository) { Gem::Specification.load('httparty.gemspec') }
    raise 'Cannot load the local HTTParty gemspec' unless specification && specification.name == 'httparty'
    additions = profile.fetch('additional_locked_gems', []).map do |item|
      "    #{item.fetch('name')} (#{item.fetch('version')})\n"
    end.join
    contents = template.sub(/^GEM\n(.*?)  specs:\n/m) { |header| header + additions }
    frozen_versions = contents.scan(/^    ([\w-]+) \(([^\n)]+)\)$/).to_h
    dependencies = specification.runtime_dependencies.sort_by(&:name).map do |dependency|
      version = frozen_versions[dependency.name]
      unless version && dependency.requirement.satisfied_by?(Gem::Version.new(version))
        raise "Runtime dependency unavailable in the frozen offline closure: #{dependency}"
      end
      requirement = dependency.requirement.to_s
      "      #{dependency.name}#{requirement == '>= 0' ? '' : " (#{requirement})"}\n"
    end.join
    pattern = /^    httparty \([^\n]+\)\n(?:      [^\n]+\n)*/
    raise 'Invalid local project lock template' unless contents.scan(pattern).size == 1
    contents = contents.sub(pattern, "    httparty (#{specification.version})\n#{dependencies}")
    selected = entry.merge('project_version' => specification.version.to_s,
                           'project_gemspec_sha256' => Digest::SHA256.file(File.join(repository, 'httparty.gemspec')).hexdigest,
                           'template_sha256' => entry.fetch('sha256'),
                           'sha256' => Digest::SHA256.hexdigest(contents))
    [selected, contents]
  end
end
