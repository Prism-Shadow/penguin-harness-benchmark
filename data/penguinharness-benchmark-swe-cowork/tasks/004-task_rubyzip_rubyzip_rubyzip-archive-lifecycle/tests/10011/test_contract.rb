# frozen_string_literal: true
require "minitest/autorun"
require "zip"

class RestoreDefaultContract < Minitest::Test
  def test_permissions_and_times_are_enabled_by_default
    Zip.reset!
    assert_equal(true, Zip::DEFAULT_RESTORE_OPTIONS[:restore_permissions])
    assert_equal(true, Zip::DEFAULT_RESTORE_OPTIONS[:restore_times])
    assert_equal(false, Zip::DEFAULT_RESTORE_OPTIONS[:restore_ownership])
  end
end
