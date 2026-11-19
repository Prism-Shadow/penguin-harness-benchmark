require 'tempfile'
require_relative '../http_support'

Tempfile.create(['upload', '.txt']) do |file|
  file.write('file-payload')
  file.rewind
  headers = {'Content-Type' => 'text/plain', 'X-Original' => 'preserved'}.freeze
  HTTPProbe.capture(->(_request, _count) { [200, {}, 'ok'] }) do |url, requests|
    HTTParty.post(url, body: {'upload' => file}, headers: headers, timeout: 3)
    request = requests.fetch(0)
    parts = HTTPProbe.multipart_parts(request)
    raise 'multipart upload payload missing' unless parts.length == 1 && parts.first[:name] == 'upload' && parts.first[:body] == 'file-payload'
    raise 'caller header changed' unless headers == {'Content-Type' => 'text/plain', 'X-Original' => 'preserved'}
    raise 'unrelated header dropped' unless request[:headers]['x-original'] == 'preserved'
  end
end
