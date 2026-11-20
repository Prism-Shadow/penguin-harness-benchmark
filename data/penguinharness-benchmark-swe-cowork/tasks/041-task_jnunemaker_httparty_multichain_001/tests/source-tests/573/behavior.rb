# frozen_string_literal: true
require "delegate"
require "tempfile"
format = HTTParty::Parser.format_from_mimetype("application/hal+json; charset=utf-8")
raise "HAL JSON media type was not recognized" unless format == :json
parsed = HTTParty::Parser.call('{"hal":true}', format)
raise "HAL JSON dispatch returned the wrong value" unless parsed == { "hal" => true }

require_relative '../http_support'
HTTPProbe.capture(->(_request, _count) { [200, {'Content-Type' => 'application/hal+json; charset=utf-8'}, '{"actual":"wire","number":41}'] }) do |url, _requests|
  response = HTTParty.get(url, timeout: 3)
  raise 'vendor JSON response bypassed parser' unless response.parsed_response == {'actual' => 'wire', 'number' => 41}
end
