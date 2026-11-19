require_relative "test/test_helper"
require "action_dispatch/system_test_case"

Capybara.register_driver :contract_chromium do |app|
  options = Selenium::WebDriver::Chrome::Options.new
  options.binary = ENV.fetch("CHROME_BIN", "/usr/bin/chromium")
  %w[--headless=new --no-sandbox --disable-dev-shm-usage --lang=en --disable-background-networking].each { |arg| options.add_argument(arg) }
  options.add_option("goog:loggingPrefs", {browser: "ALL"})
  service = Selenium::WebDriver::Service.chrome(path: ENV.fetch("CHROMEDRIVER", "/usr/bin/chromedriver"))
  Capybara::Selenium::Driver.new(app, browser: :chrome, options: options, service: service)
end
Capybara.server = :puma, {Silent: true, Threads: "0:4"}
Capybara.default_max_wait_time = 8
Capybara.enable_aria_label = true

class BrowserContractTest < ActionDispatch::SystemTestCase
  include Warden::Test::Helpers
  driven_by :contract_chromium
  parallelize(workers: 1)

  teardown do
    if passed? == false
      warn page.driver.browser.logs.get(:browser).map(&:message).join("\n") rescue nil
    end
    Settings.reload!
    Rails.application.reload_routes!
    Warden.test_reset!
    Capybara.reset_sessions!
  end

  def labelled_button(pattern)
    matches = proc do |button|
      [button.text, button["aria-label"], button["title"], button["value"]].compact.any? { |label| pattern.match?(label) }
    end
    assert_selector(:button, &matches)
    find(:button, &matches)
  end

  def css_value(element, property)
    page.evaluate_script("getComputedStyle(arguments[0]).getPropertyValue(arguments[1])", element, property)
  end

  def async_js(source)
    result = page.evaluate_async_script(<<~JS, source)
      const done = arguments[arguments.length - 1];
      (new Function('return (async () => {' + arguments[0] + '})()'))()
        .then(value => done({ok: true, value}), error => done({ok: false, error: String(error)}));
    JS
    assert result["ok"], result["error"]
    result["value"]
  end
end
