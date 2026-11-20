require_relative '../http_support'

['first', 'second'].each do |value|
  payload = %({"value":"#{value}"})
  HTTPProbe.capture(->(_request, _count) { [200, {'Content-Type' => 'application/json'}, payload] }) do |url, _requests|
    original = HTTParty.get(url, timeout: 3)
    # Serialize before asking for parsed_response: real lazy parsing must survive.
    restored = Marshal.load(Marshal.dump(original))
    raise 'response marshal lost status or body' unless restored.code == 200 && restored.body == payload
    raise 'response marshal lost lazy parsed data' unless restored.parsed_response == {'value' => value}
    again = Marshal.load(Marshal.dump(restored))
    raise 'parsed response cannot be serialized again' unless again.parsed_response == {'value' => value}
  end
end
