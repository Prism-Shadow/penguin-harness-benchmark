require "minitest/mock"
require "json"

module TransportHarness
  def with_http_responses(payloads)
    requests = []
    original_new = Net::HTTP.method(:new)
    factory = lambda do |*arguments|
      connection = original_new.call(*arguments)
      connection.define_singleton_method(:start) { self }
      connection.define_singleton_method(:finish) { nil }
      connection.define_singleton_method(:request) do |request, body = nil, &block|
        requests << { method: request.method, path: request.path, body: body,
                      headers: request.to_hash }
        raise "unexpected HTTP request" if payloads.empty?

        status, payload = payloads.shift
        response = Net::HTTPResponse::CODE_TO_OBJ.fetch(status.to_s).new("1.1", status.to_s, "fixture")
        response["content-type"] = "application/json"
        response["request-id"] = "req_contract"
        response.body = JSON.generate(payload)
        response.instance_variable_set(:@read, true)
        block.call(response) if block
        response
      end
      connection
    end
    Stripe::APIRequestor.clear_all_connection_managers
    Net::HTTP.stub(:new, factory) { yield requests }
    assert_empty payloads, "all planned wire exchanges must occur"
  ensure
    Stripe::APIRequestor.clear_all_connection_managers
  end

  def import_payload(identifier, status = "succeeded")
    { object: "v2.commerce.product_catalog_import", id: identifier, status: status,
      feed_type: "pricing", metadata: {}, status_details: { succeeded: { success_count: "23" } } }
  end
end
