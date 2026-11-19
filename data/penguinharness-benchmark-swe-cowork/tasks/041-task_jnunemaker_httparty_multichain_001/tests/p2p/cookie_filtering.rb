# frozen_string_literal: true
require "httparty"
cookies = HTTParty::CookieHash.new
cookies.add_cookies("session=abc; Path=/; Secure=true")
raise "application cookie was lost" unless cookies.to_cookie_string == "session=abc"

