require_relative '../http_support'

formatter = Class.new do
  def initialize(logger, level)
    @logger, @level = logger, level
  end
  def format(request, response)
    @logger.public_send(@level, [request.http_method, request.path.to_s, response.code, response.body])
  end
end
HTTParty::Logger.add_formatter(:custom_probe, formatter)
logger = Object.new
messages = []
logger.define_singleton_method(:info) { |message| messages << message }
raise 'custom formatter was not built' unless HTTParty::Logger.build(logger, :info, :custom_probe).is_a?(formatter)
client = Class.new { include HTTParty }
client.logger(logger, :info, :custom_probe)
HTTPProbe.capture(->(_request, _count) { [202, {}, 'custom-response'] }) do |url, _requests|
  client.get("#{url}/custom-formatter", timeout: 3)
  raise 'registered formatter was not called on request' unless messages.length == 1
  method, path, code, body = messages.first
  raise 'registered formatter received wrong request/response' unless method == Net::HTTP::Get && path.end_with?('/custom-formatter') && code.to_s == '202' && body == 'custom-response'
end
