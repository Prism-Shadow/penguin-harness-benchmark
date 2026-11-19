# frozen_string_literal: true
require "httparty"
payload = "plain-response"
raise "plain parser no longer passes bodies through" unless HTTParty::Parser.call(payload, :plain) == payload
raise "JSON format disappeared" unless HTTParty::Parser.supported_formats.include?(:json)

