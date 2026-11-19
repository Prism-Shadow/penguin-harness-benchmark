require_relative '../http_support'

expected = Net::HTTP::Get.new('/')['Accept-Encoding']
raise 'Net::HTTP runtime has no compression default' if expected.nil? || expected.empty?
HTTPProbe.capture(->(_request, _count) { [200, {}, 'ok'] }) do |url, requests|
  HTTParty.get(url, headers: {'User-Agent' => 'Party'}, timeout: 3)
  headers = requests.first[:headers]
  raise 'Accept-Encoding was lost when explicit headers were supplied' unless headers['accept-encoding'] == expected && headers['user-agent'] == 'Party'
end
