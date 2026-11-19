# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class FileSplitModuleContract < Minitest::Test
  def test_file_delegates_to_the_split_module
    assert_includes(Zip::File.singleton_class.ancestors, Zip::FileSplit)
    assert_equal(65_536, Zip::File.get_segment_size_for_split(1))
  end
end
