require_relative '../http_support'

["body\x00\xff".b, ''.b, 'second-payload'.freeze].each do |payload|
  snapshot = payload.dup
  [nil, '', 'identity', 'none'].each do |encoding|
    raise 'identity bytes changed' unless HTTParty::Decompressor.call(payload, encoding) == payload
  end
  raise 'unknown encoding should return nil' unless HTTParty::Decompressor.call(payload, 'unknown').nil?
  raise 'input mutated' unless payload == snapshot
end
raise 'nil body should return nil' unless HTTParty::Decompressor.call(nil, 'identity').nil?
HTTPProbe.capture(->(_request, _count) { [200, {'Content-Encoding' => 'identity'}, "wire\x00body"] }) do |url, _requests|
  response = HTTParty.get(url, format: :plain, timeout: 3)
  raise 'request decompression integration failed' unless response.body == "wire\x00body" && response.parsed_response == "wire\x00body"
end
