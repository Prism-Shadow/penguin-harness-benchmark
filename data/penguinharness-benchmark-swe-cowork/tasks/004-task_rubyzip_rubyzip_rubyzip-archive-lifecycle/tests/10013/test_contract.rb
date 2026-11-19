# frozen_string_literal: true
require "minitest/autorun"
require "zip"
require_relative '../support/archive_fixture'

class CentralParserOwnershipContract < Minitest::Test
  include ArchiveFixture

  def test_binary_parsing_is_owned_by_central_directory
    assert_raises(NoMethodError) { Zip::Entry.read_zip_short(StringIO.new("\x01\x00")) }
    entries = {'alpha' => 'one', 'beta' => 'longer payload'}
    assert_archive(archive_bytes(entries, comment: 'owned'), entries, 'owned')
  end
end
