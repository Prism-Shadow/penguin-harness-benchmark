require_relative '../http_support'

HTTPProbe.redirect(307) do |url, requests|
  request = HTTParty::Request.new(Net::HTTP::Post, "#{url}/start", body: 'temporary-redirect-body', maintain_method_across_redirects: false, timeout: 3)
  raise '307 request did not finish' unless request.perform.code == 200
  raise '307 redirect changed method or payload' unless requests.map { |r| [r[:method],r[:body]] } == [['POST','temporary-redirect-body'],['POST','temporary-redirect-body']]
end
