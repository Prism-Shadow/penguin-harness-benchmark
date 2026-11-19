# frozen_string_literal: true
require "httparty"
parent = Class.new do
  include HTTParty
  base_uri "api.example.test"
  default_timeout 9
  headers "Accept" => "application/json"
end
child = Class.new(parent)
raise "base URI inheritance regressed" unless child.default_options[:base_uri] == "http://api.example.test"
raise "timeout inheritance regressed" unless child.default_options[:timeout] == 9
raise "header inheritance regressed" unless child.default_options[:headers]["Accept"] == "application/json"

