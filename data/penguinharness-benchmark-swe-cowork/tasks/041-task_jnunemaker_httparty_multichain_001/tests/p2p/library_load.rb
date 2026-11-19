# frozen_string_literal: true
require "httparty"
raise "HTTParty request API is unavailable" unless defined?(HTTParty::Request)
raise "HTTParty version is unavailable" if HTTParty::VERSION.to_s.empty?

