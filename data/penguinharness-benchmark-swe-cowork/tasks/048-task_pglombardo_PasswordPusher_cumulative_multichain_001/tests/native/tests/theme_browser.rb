require_relative "test/test_helper"
require "action_dispatch/system_test_case"

Capybara.register_driver :contract_chromium do |app|
  options = Selenium::WebDriver::Chrome::Options.new
  options.binary = ENV.fetch("CHROME_BIN", "/usr/bin/chromium")
  %w[--headless=new --no-sandbox --disable-dev-shm-usage --lang=en --disable-background-networking].each do |argument|
    options.add_argument(argument)
  end
  service = Selenium::WebDriver::Service.chrome(path: ENV.fetch("CHROMEDRIVER", "/usr/bin/chromedriver"))
  Capybara::Selenium::Driver.new(app, browser: :chrome, options: options, service: service)
end
Capybara.server = :puma, {Silent: true, Threads: "0:2"}
Capybara.enable_aria_label = true

class ThemeContractTest < ActionDispatch::SystemTestCase
  include Warden::Test::Helpers
  include ThemeSelector
  driven_by :contract_chromium
  parallelize(workers: 1)

  test "jobs and admin share browser theme state without prescribing a controller" do
    routes = case ENV["THEME_CONTRACT_SCOPE"]
    when "admin" then ["/admin?locale=en"]
    when "public" then ["/?locale=en", "/users/sign_in?locale=en"]
    else ["/admin/jobs?locale=en", "/admin?locale=en"]
    end
    Settings.theme_mode = "auto"
    login_as users(:mr_admin), scope: :user unless ENV["THEME_CONTRACT_SCOPE"] == "public"
    visit routes.first
    page.driver.browser.execute_cdp("Emulation.setEmulatedMedia", features: [{name: "prefers-color-scheme", value: "dark"}])
    page.execute_script("localStorage.removeItem('theme')")
    page.refresh
    assert_selector "html[data-bs-theme=dark]"

    %w[light dark system light].each do |preference|
      theme_button.click
      assert_selector "html[data-bs-theme=#{preference == 'system' ? 'dark' : preference}]"
      assert_equal preference, page.evaluate_script("localStorage.getItem('theme')")
    end

    visit routes.last
    assert_selector "html[data-bs-theme=light]"
    theme_button.click
    assert_selector "html[data-bs-theme=dark]"
    visit routes.first
    assert_selector "html[data-bs-theme=dark]"
    page.refresh
    assert_selector "html[data-bs-theme=dark]"

    page.execute_script("localStorage.setItem('theme', 'system')")
    page.driver.browser.execute_cdp("Emulation.setEmulatedMedia", features: [{name: "prefers-color-scheme", value: "light"}])
    page.refresh
    assert_selector "html[data-bs-theme=light]"

    # Invalid preference follows the OS, and system reacts without reloading.
    page.execute_script("localStorage.setItem('theme', 'not-a-mode')")
    page.refresh
    assert_selector "html[data-bs-theme=light]"
    page.driver.browser.execute_cdp("Emulation.setEmulatedMedia", features: [{name: "prefers-color-scheme", value: "dark"}])
    assert_selector "html[data-bs-theme=dark]"
    theme_button.click
    assert_selector "html[data-bs-theme=light]"
    page.driver.browser.execute_cdp("Emulation.setEmulatedMedia", features: [{name: "prefers-color-scheme", value: "light"}])
    assert_selector "html[data-bs-theme=light]"
    page.driver.browser.execute_cdp("Emulation.setEmulatedMedia", features: [{name: "prefers-color-scheme", value: "dark"}])
    assert_selector "html[data-bs-theme=light]"
    blocked = page.driver.browser.execute_cdp("Page.addScriptToEvaluateOnNewDocument", source: "Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})").fetch("identifier")
    page.refresh
    assert_selector "html[data-bs-theme=dark]"
    theme_button.click
    assert_selector "html[data-bs-theme=light]"
    theme_button.click
    assert_selector "html[data-bs-theme=dark]"
    page.driver.browser.execute_cdp("Page.removeScriptToEvaluateOnNewDocument", identifier: blocked)
    page.refresh

    %w[dark light].each do |locked|
      Settings.theme_mode = locked
      page.execute_script("localStorage.setItem('theme', arguments[0])", locked == "dark" ? "light" : "dark")
      routes.each do |route|
        visit route
        page.refresh
        assert_selector "html[data-bs-theme=#{locked}]"
        assert_no_theme_button
      end
    end
  ensure
    Settings.reload!
    Warden.test_reset!
  end
end
