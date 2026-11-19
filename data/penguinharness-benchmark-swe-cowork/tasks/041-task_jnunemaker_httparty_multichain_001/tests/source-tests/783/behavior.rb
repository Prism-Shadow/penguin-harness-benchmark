require_relative '../http_support'

HTTPProbe.redirect(303) do |url, requests|
  request = HTTParty::Request.new(Net::HTTP::Post, "#{url}/start", body: 'caller-payload', timeout: 3)
  raise '303 request did not finish' unless request.perform.code == 200
  raise '303 did not switch to an empty GET' unless requests.map { |r| [r[:method],r[:body]] } == [['POST','caller-payload'],['GET','']]
  raise 'redirect left options body in place' unless request.options[:body].nil?
  raise 'redirect left raw request body in place' unless request.raw_body.nil?
  request.perform
  raise 'reused redirected request resent stale body' unless requests.last[:method] == 'GET' && requests.last[:body] == ''
end
