require 'bundler'
require 'json'

raise 'Development/test groups must not be excluded' unless Bundler.settings[:without].empty?
pins = JSON.parse(File.read(File.join(__dir__, 'dependency-versions.json'))).fetch('gems')
actual = Bundler.load.specs.reject { |specification| specification.name == 'newrelic_rpm' }
resolved = actual.to_h { |specification| [specification.name, specification.version.to_s] }
raise "Resolved dependency graph differs from lock: #{resolved}" unless resolved == pins
%w[warning feedjira httparty minitest/autorun minitest/stub_const mocha/minitest
   mutex_m ostruct rack rake rubocop rubocop/ast simplecov thor yard opentelemetry].each do |feature|
  require feature
end
repository = ENV.fetch('WORKPLACE_REPOSITORY_DIR', '/app/code')
production = Bundler.load.specs.find { |specification| specification.name == 'newrelic_rpm' }
raise 'Bundler did not select the editable production repository' unless production.full_gem_path == File.realpath(repository)
puts "Full development bundle loaded: #{resolved.length} pinned dependencies; production repository #{repository}"
