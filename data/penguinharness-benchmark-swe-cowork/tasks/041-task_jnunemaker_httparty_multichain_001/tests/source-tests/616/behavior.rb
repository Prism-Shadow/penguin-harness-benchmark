require 'tempfile'
require_relative '../http_support'

cases = [['.json', nil, 'application/json'], ['.txt', nil, 'text/plain'],
         ['.png', nil, 'image/png'], ['.pdf', nil, 'application/pdf'],
         ['.svg', nil, 'image/svg+xml'], ['.css', nil, 'text/css'],
         ['.webp', nil, 'image/webp'], ['.mp3', nil, 'audio/mpeg'],
         ['.unknown041', nil, 'application/octet-stream'],
         ['', nil, 'application/octet-stream'], ['.json', 'application/x-explicit', 'application/x-explicit'],
         ['.png', 'text/custom-image', 'text/custom-image']]
cases.each do |extension, explicit, expected|
  Tempfile.create(['mime', extension]) do |file|
    payload = "content-for-#{extension}\x00".b
    file.binmode
    file.write(payload)
    file.rewind
    file.define_singleton_method(:content_type) { explicit } if explicit
    HTTPProbe.capture(->(_request, _count) { [200, {}, 'ok'] }) do |url, requests|
      HTTParty.post(url, body: {'upload' => file}, timeout: 3)
      parts = HTTPProbe.multipart_parts(requests.fetch(0))
      raise 'file part missing' unless parts.length == 1 && parts.first[:name] == 'upload'
      part = parts.first
      raise "MIME precedence wrong for #{extension}/#{explicit}" unless part[:headers]['content-type'] == expected
      raise 'MIME lookup changed file bytes' unless part[:body] == payload
      raise 'upload filename missing' unless part[:filename] == File.basename(file.path)
    end
  end
end
