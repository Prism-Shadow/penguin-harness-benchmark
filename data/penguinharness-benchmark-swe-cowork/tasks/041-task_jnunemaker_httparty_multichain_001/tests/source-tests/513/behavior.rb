# frozen_string_literal: true
require "delegate"
require "tempfile"
request = Net::HTTP::Get.new("/")
request["cookie"] = "sid=abc"
request.digest_auth("user", "pass", { "www-authenticate" => 'Digest realm="demo", nonce="abc"' })
raise "authorization header was not normalized" unless request.to_hash.key?("authorization")
raise "cookie header was lost" unless request.to_hash.key?("cookie")
