require 'json'

repository = ENV.fetch('WORKPLACE_REPOSITORY_DIR', '/app/code')
eval_gemfile File.join(repository, 'Gemfile')

JSON.parse(File.read(File.join(__dir__, 'dependency-versions.json'))).fetch('gems').each do |name, version|
  gem name, "= #{version}"
end
