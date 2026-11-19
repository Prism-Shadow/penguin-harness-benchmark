require 'digest/md5'
require_relative '../http_support'

['auth', '"auth"'].each do |qop|
  request = Net::HTTP::Post.new('/unquoted?case=41')
  request.digest_auth('user', 'pass', {'www-authenticate' => %(Digest realm="demo", nonce="abc", qop=#{qop})})
  fields = HTTPProbe.digest_fields(request['Authorization'])
  raise 'unquoted qop was not retained in Authorization' unless fields['qop'] == 'auth' && !fields['cnonce'].to_s.empty? && fields['nc'] == '00000001'
  md5 = ->(value) { Digest::MD5.hexdigest(value) }
  expected = md5.call([md5.call('user:demo:pass'), 'abc', fields['nc'], fields['cnonce'], 'auth', md5.call('POST:/unquoted?case=41')].join(':'))
  raise 'unquoted qop authentication response was wrong' unless fields['response'] == expected
end
