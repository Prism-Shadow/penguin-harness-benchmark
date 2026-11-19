require 'socket'
require 'timeout'

module HTTPProbe
  def self.capture(handler)
    server = TCPServer.new('127.0.0.1', 0)
    requests = []
    worker = Thread.new do
      loop do
        socket = server.accept
        begin
          Timeout.timeout(8) do
            method, path, = socket.gets.split(' ')
            headers = {}
            while (line = socket.gets) && line != "\r\n"
              key, value = line.split(':', 2)
              headers[key.downcase] = value.strip
            end
            body = ''.b
            if headers['transfer-encoding'] == 'chunked'
              loop do
                length = socket.gets.to_i(16)
                break if length.zero?
                body << socket.read(length)
                socket.read(2)
              end
              socket.gets
            elsif headers['content-length']
              body = socket.read(headers['content-length'].to_i) || ''.b
            end
            request = {method: method, path: path, headers: headers, body: body}
            requests << request
            code, response_headers, payload = handler.call(request, requests.length)
            payload = payload.b
            response_headers = {'Content-Length' => payload.bytesize.to_s, 'Connection' => 'close'}.merge(response_headers)
            socket.write("HTTP/1.1 #{code} Probe\r\n")
            response_headers.each { |key, value| socket.write("#{key}: #{value}\r\n") }
            socket.write("\r\n")
            socket.write(payload) unless method == 'HEAD'
          end
        ensure
          socket.close
        end
      end
    end
    worker.report_on_exception = false
    yield "http://127.0.0.1:#{server.addr[1]}", requests
    worker.value unless worker.alive?
  ensure
    worker&.kill
    worker&.join
    server&.close
  end

  def self.redirect(code)
    handler = lambda do |request, _count|
      request[:path] == '/start' ? [code, {'Location' => '/finish'}, ''] : [200, {}, 'finished']
    end
    capture(handler) { |url, requests| yield url, requests }
  end

  # Parse the actual multipart bytes without assuming a boundary spelling,
  # field order, encoder helper, or buffered/streaming implementation.
  def self.multipart_parts(request)
    content_type = request[:headers].fetch('content-type')
    match = /\Amultipart\/form-data\s*;\s*boundary=(?:"([^"]+)"|([^;\s]+))/i.match(content_type)
    raise 'multipart Content-Type/boundary missing' unless match
    boundary = (match[1] || match[2]).b
    bytes = request[:body].b
    raise 'multipart terminator missing' unless bytes.end_with?("--#{boundary}--\r\n".b)
    segments = bytes.split("--#{boundary}".b, -1)
    raise 'multipart prefix/terminator invalid' unless segments.shift == '' && segments.pop == "--\r\n"
    segments.map do |segment|
      raise 'multipart part framing invalid' unless segment.start_with?("\r\n") && segment.end_with?("\r\n")
      header_text, payload = segment.byteslice(2, segment.bytesize - 4).split("\r\n\r\n", 2)
      raise 'multipart part separator missing' unless payload
      headers = header_text.split("\r\n").to_h { |line| key, value = line.split(':', 2); [key.downcase, value.strip] }
      disposition = headers.fetch('content-disposition')
      name = disposition[/\bname="([^"]*)"/, 1]
      raise 'multipart field name missing' unless name
      {name: name, filename: disposition[/\bfilename="([^"]*)"/, 1], headers: headers, body: payload}
    end
  end

  def self.digest_fields(header)
    header.to_s.sub(/\ADigest\s+/i, '').scan(/([\w-]+)\s*=\s*(?:"([^"]*)"|([^,\s]+))/).to_h do |key, quoted, token|
      [key, quoted || token]
    end
  end
end
