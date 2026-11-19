repo = ENV.fetch('REPO_DIR', Dir.pwd)
$LOAD_PATH.unshift(File.join(repo, 'lib'))
require 'minitest/autorun'
require 'xcodeproj'

class DeploymentTargetWriterTest < Minitest::Test
  def test_deployment_target_writer_updates_every_configuration
    project = Xcodeproj::Project.new('/tmp/Deployment.xcodeproj')
    target = project.new(Xcodeproj::Project::Object::PBXNativeTarget)
    configuration_list = project.new(Xcodeproj::Project::Object::XCConfigurationList)
    %w[Debug Release].each do |name|
      configuration = project.new(Xcodeproj::Project::Object::XCBuildConfiguration)
      configuration.name = name
      configuration.build_settings = { 'SDKROOT' => 'appletvos' }
      configuration_list.build_configurations << configuration
    end
    target.build_configuration_list = configuration_list
    target.deployment_target = '9.2'

    assert_equal '9.2', target.deployment_target
    assert_equal ['9.2'], target.build_configurations.map { |config| config.build_settings['TVOS_DEPLOYMENT_TARGET'] }.uniq
  end
end
