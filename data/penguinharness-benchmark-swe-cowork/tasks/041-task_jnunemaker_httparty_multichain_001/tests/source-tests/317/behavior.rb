require_relative '../http_support'

[[false, false], [true, false], [true, true]].each do |maintain, resend|
  client = Class.new { include HTTParty }
  client.maintain_method_across_redirects(maintain)
  client.resend_on_redirect if resend
  2.times do |iteration|
    HTTPProbe.redirect(303) do |url, requests|
      payload = "iteration=#{iteration}"
      client.post("#{url}/start", body: payload, timeout: 3)
      expected_method = maintain && resend ? 'POST' : 'GET'
      expected_body = expected_method == 'POST' ? payload : ''
      raise '303 method policy failed' unless requests.map { |request| request[:method] } == ['POST', expected_method]
      raise '303 body transition failed' unless requests.last[:body] == expected_body
    end
  end
end
