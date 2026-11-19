require "rbconfig"

ENV["RUBY"] ||= RbConfig.ruby
exec("python3", File.join(__dir__, "grader.py"), *ARGV)
