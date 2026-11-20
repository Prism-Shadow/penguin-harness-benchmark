# frozen_string_literal: true
require "delegate"
require "tempfile"
body = "\xEF\xBB\xBFplain".dup.force_encoding(Encoding::UTF_8)
original = body.dup
parsed = HTTParty::Parser.call(body, :plain)
raise "parser did not normalize the UTF-8 BOM" unless parsed == "plain"
raise 'parser mutated caller body' unless body == original
