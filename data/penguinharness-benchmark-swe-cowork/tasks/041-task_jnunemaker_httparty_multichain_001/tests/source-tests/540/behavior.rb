# frozen_string_literal: true
require "delegate"
require "tempfile"
body = "\xEF\xBB\xBF{\"a\":1}".dup.force_encoding(Encoding::UTF_8).freeze
parsed = HTTParty::Parser.call(body, :json)
raise "frozen parser body was not accepted" unless parsed == { "a" => 1 }
