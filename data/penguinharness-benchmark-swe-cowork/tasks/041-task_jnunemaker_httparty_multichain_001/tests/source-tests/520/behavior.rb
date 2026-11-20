# frozen_string_literal: true
require "delegate"
require "tempfile"
body = "\xEF\xBB\xBF{\"hi\":\"yo\"}".dup.force_encoding(Encoding::UTF_8)
original = body.dup
parsed = HTTParty::Parser.call(body, :json)
raise "UTF-8 BOM was not ignored" unless parsed == { "hi" => "yo" }
raise 'parser mutated caller body' unless body == original
