# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class RestoreOptionSharingContract < Minitest::Test
  def test_entry_reads_the_shared_restore_mapping
    options = Zip::DEFAULT_RESTORE_OPTIONS
    assert(options.frozen?)
    assert_equal(options[:restore_times], Zip::Entry.new.restore_times)
    assert_equal(options[:restore_permissions], Zip::Entry.new.restore_permissions)
    assert_equal(options[:restore_ownership], Zip::Entry.new.restore_ownership)
  end
end
