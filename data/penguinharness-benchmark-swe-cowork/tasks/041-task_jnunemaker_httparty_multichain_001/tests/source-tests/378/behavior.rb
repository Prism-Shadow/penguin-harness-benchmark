require_relative '../http_support'

[['/start', 'bar/', '/bar/'],
 ['/directory/start', 'next?x=1', '/directory/next?x=1'],
 ['/directory/', 'child/', '/directory/child/']].each do |start, location, destination|
  handler = ->(_request, count) { count == 1 ? [302, {'Location' => location}, ''] : [200, {}, 'arrived'] }
  HTTPProbe.capture(handler) do |url, requests|
    request = HTTParty::Request.new(Net::HTTP::Get, "#{url}#{start}", timeout: 3)
    response = request.perform
    raise 'relative redirect did not complete' unless response.body == 'arrived'
    raise 'relative Location resolved incorrectly' unless requests.map { |entry| entry[:path] } == [start, destination]
    raise 'final absolute URI is wrong' unless request.last_uri.to_s == "#{url}#{destination}"
  end
end
