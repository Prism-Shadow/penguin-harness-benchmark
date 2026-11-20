require 'tempfile'
require_relative '../http_support'

Tempfile.create('boolean-multipart') do |file|
  file.binmode
  file.write("payload\x00\xff".b)
  file.rewind
  HTTPProbe.capture(->(_request, _count) { [200, {}, 'ok'] }) do |url, requests|
    HTTParty.post(url, body: {'enabled' => true, 'disabled' => false, 'upload' => file}, timeout: 3)
    parts = HTTPProbe.multipart_parts(requests.fetch(0))
    raise 'multipart fields lost or duplicated' unless parts.map { |part| part[:name] }.sort == %w[disabled enabled upload]
    values = parts.to_h { |part| [part[:name], part[:body]] }
    raise 'boolean true value changed' unless values['enabled'] == 'true'
    raise 'boolean false value changed' unless values['disabled'] == 'false'
    raise 'file bytes changed' unless values['upload'] == "payload\x00\xff".b
  end
end
