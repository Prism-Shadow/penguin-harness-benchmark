# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class DirectoryFacadeModuleContract < Minitest::Test
  def test_dir_facade_exposes_mapper_working_directory
    loaded = begin
      require "zip/filesystem/dir"
      true
    rescue LoadError
      false
    end
    assert(loaded, "dedicated FileSystem::Dir module must be loadable")
    mapper = Object.new
    def mapper.pwd
      "/"
    end
    facade = Zip::FileSystem::Dir.new(mapper)
    assert_equal("/", facade.pwd)
    assert_equal("/", facade.getwd)
  end
end
