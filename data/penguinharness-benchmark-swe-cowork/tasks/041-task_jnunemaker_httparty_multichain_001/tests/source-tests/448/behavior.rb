# frozen_string_literal: true
require "delegate"
require "tempfile"
response = { "www-authenticate" => 'WWW-Authenticate: Basic realm="testrealm.com""' }
auth = Net::HTTPHeader::DigestAuthenticator.new("user", "pass", "GET", "/", response)
raise "malformed Basic challenge was not ignored" unless auth.send(:parse, response) == {}
