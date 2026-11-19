require "minitest/autorun"
require "capybara"
require_relative "native/tests/theme_selector"

class ThemeSelectorTest < Minitest::Test
  def document(markup)
    Capybara.string(markup).extend(ThemeSelector)
  end

  def test_icon_button_with_changing_accessible_label
    ["Use light theme", "Use dark theme", "Use system theme"].each do |label|
      page = document(%(<button>Refresh</button><button aria-label="#{label}">◐</button>))
      assert_equal label, page.theme_button["aria-label"]
      assert_raises(Capybara::ExpectationNotMet) { page.assert_no_theme_button }
    end
  end

  def test_text_and_title_buttons_without_controller_or_id
    ["THEME", "Appearance", "Color scheme", "Colour mode"].each do |label|
      assert_equal label, document("<button>#{label}</button>").theme_button.text
      assert_equal label, document(%(<button title="#{label}">◐</button>)).theme_button["title"]
    end
  end

  def test_negative_assertion_rejects_present_control
    page = document('<button aria-label="Theme">◐</button>')
    assert_raises(Capybara::ExpectationNotMet) { page.assert_no_theme_button }
  end

  def test_input_button_value
    page = document('<input type="button" value="Theme">')
    assert_equal "Theme", page.theme_button["value"]
    assert_raises(Capybara::ExpectationNotMet) { page.assert_no_theme_button }
  end

  def test_non_buttons_and_unrelated_buttons_do_not_match
    page = document('<span>Theme</span><button aria-label="Refresh">↻</button>')
    assert_raises(Capybara::ElementNotFound) { page.theme_button }
    page.assert_no_theme_button
  end

  def test_absent_control_passes_negative_assertion
    page = document('<main>Locked appearance</main>')
    page.assert_no_theme_button
    assert_raises(Capybara::ElementNotFound) { page.theme_button }
  end
end
