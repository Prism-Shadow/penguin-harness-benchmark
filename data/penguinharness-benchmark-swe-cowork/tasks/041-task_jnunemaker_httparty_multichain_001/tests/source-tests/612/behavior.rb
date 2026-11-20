# frozen_string_literal: true
require "delegate"
require "tempfile"
logger = HTTParty::Logger.build(Object.new, :info, :logstash)
raise "logstash formatter was not registered" unless logger.is_a?(HTTParty::Logger::LogstashFormatter)
