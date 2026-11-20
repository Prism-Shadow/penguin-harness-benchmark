# frozen_string_literal: true
require "delegate"
require "tempfile"
request = HTTParty::Request.new(Net::HTTP::Get, "http://example.test", query: { fake_array: [] })
decoded_query = URI.decode_www_form_component(request.uri.query.to_s)
raise "empty arrays were dropped" unless decoded_query == "fake_array[]="
