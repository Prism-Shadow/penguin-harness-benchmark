# frozen_string_literal: true
require "delegate"
require "tempfile"
body = [255].pack("C").force_encoding(Encoding::UTF_8)
result = HTTParty::Parser.new(body, :plain).parse
raise "invalid encoding raised or changed the body" unless result == body
