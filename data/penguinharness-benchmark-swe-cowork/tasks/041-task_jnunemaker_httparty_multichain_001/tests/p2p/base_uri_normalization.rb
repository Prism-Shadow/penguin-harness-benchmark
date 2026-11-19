# frozen_string_literal: true
require "httparty"
raise "scheme normalization regressed" unless HTTParty.normalize_base_uri("example.test/") == "http://example.test"
raise "TLS normalization regressed" unless HTTParty.normalize_base_uri("example.test:443/") == "https://example.test:443"

