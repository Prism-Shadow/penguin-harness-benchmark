# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require "json"
require_relative "../transport_harness"

class EventHandlerProductCatalogIntegrationTest < Minitest::Test
  include TransportHarness

  def payload(identifier, context, suffix = "succeeded")
    { id: identifier, object: "v2.core.event", type: "v2.commerce.product_catalog.imports.#{suffix}",
      context: context, related_object: { id: "pci_dynamic", type: "v2.commerce.product_catalog_import",
                                        url: "/v2/commerce/product_catalog/imports/pci_dynamic" } }.to_json
  end

  def test_generated_routes_fetch_through_real_transport_without_context_leaks
    client = Stripe::StripeClient.new("sk_test_contract", stripe_context: "source_context")
    scoped_clients = []
    notifications = []
    handler = client.notification_handler_without_verification { flunk "typed event used fallback" }
    suffixes = %w[failed processing succeeded succeeded_with_errors]
    suffixes.each do |suffix|
      handler.public_send("on_v2_commerce_product_catalog_imports_#{suffix}") do |notification, scoped|
        notifications << notification
        scoped_clients << scoped
        assert_equal "pci_dynamic", notification.fetch_related_object.id
        assert_equal "pci_second", notification.fetch_related_object.id
        assert_equal "pci_scoped", scoped.v2.commerce.product_catalog.imports.retrieve("pci_scoped").id
      end
    end
    responses = suffixes.flat_map do |_suffix|
      [[200, import_payload("pci_dynamic")], [200, import_payload("pci_second")], [200, import_payload("pci_scoped")]]
    end
    responses += [[200, import_payload("pci_source")], [200, import_payload("pci_previous")]]
    with_http_responses(responses) do |requests|
      suffixes.each_with_index do |suffix, index|
        context = index == 2 ? nil : "acct_#{index}"
        handler.handle(payload("evt_#{index}", context, suffix))
        expected_class = "V2CommerceProductCatalogImports#{suffix.split('_').map(&:capitalize).join}EventNotification"
        assert_instance_of Stripe::Events.const_get(expected_class), notifications.last
        assert_equal context, notifications.last.context&.to_s
        assert_equal "pci_dynamic", notifications.last.related_object.id
        group = requests[index * 3, 3]
        assert_equal ["GET", "GET", "GET"], group.map { |request| request[:method] }
        group.each { |request| assert_equal context, request[:headers]["stripe-context"]&.first }
        group.first(2).each do |request|
          assert_equal ["event=evt_#{index}"], request[:headers]["stripe-request-trigger"]
          assert_equal "/v2/commerce/product_catalog/imports/pci_dynamic", URI.parse(request[:path]).path
        end
      end
      client.v2.commerce.product_catalog.imports.retrieve("pci_source")
      scoped_clients.first.v2.commerce.product_catalog.imports.retrieve("pci_previous")
      assert_equal ["source_context"], requests[-2][:headers]["stripe-context"]
      assert_equal ["acct_0"], requests[-1][:headers]["stripe-context"]
    end
  end

  def test_handler_registration_lifecycle_unknown_and_unregistered_fallback
    client = Stripe::StripeClient.new("sk_test_contract")
    assert_raises(ArgumentError) { client.notification_handler_without_verification }
    calls = []
    handler = client.notification_handler_without_verification do |notification, _scoped, details|
      calls << [notification.type, details.is_known_event_type]
    end
    assert_raises(ArgumentError) { handler.on_v2_commerce_product_catalog_imports_succeeded }
    handler.on_v2_commerce_product_catalog_imports_succeeded { calls << :typed }
    assert_raises(ArgumentError) { handler.on_v2_commerce_product_catalog_imports_succeeded {} }
    assert_equal ["v2.commerce.product_catalog.imports.succeeded"], handler.registered_event_types
    handler.handle(payload("evt_known", nil, "processing"))
    handler.handle(payload("evt_future", nil, "future_kind"))
    handler.handle(payload("evt_typed", nil))
    assert_equal [["v2.commerce.product_catalog.imports.processing", true],
                  ["v2.commerce.product_catalog.imports.future_kind", false], :typed], calls
    assert_raises(RuntimeError) { handler.on_v2_commerce_product_catalog_imports_failed {} }
  end

  def test_unverified_handler_routes_generated_commerce_event_with_context
    client = Stripe::StripeClient.new("sk_test_123", stripe_context: "original")
    fallback_calls = []
    callback_calls = []
    handler = client.notification_handler_without_verification do |notification, scoped_client, details|
      fallback_calls << [notification, scoped_client, details]
    end
    handler.on_v2_commerce_product_catalog_imports_succeeded do |notification, scoped_client|
      callback_calls << [notification, scoped_client]
    end
    payload = {
      id: "evt_catalog",
      object: "v2.core.event",
      type: "v2.commerce.product_catalog.imports.succeeded",
      context: "acct_context",
      related_object: { id: "pci_123", type: "v2.commerce.product_catalog_import", url: "/v2/commerce/product_catalog/imports/pci_123" },
    }.to_json

    handler.handle(payload)

    assert_empty fallback_calls
    assert_equal 1, callback_calls.length
    notification, scoped_client = callback_calls.first
    assert_instance_of Stripe::Events::V2CommerceProductCatalogImportsSucceededEventNotification, notification
    assert_equal "pci_123", notification.related_object.id
    assert_equal "acct_context", scoped_client.instance_variable_get(:@requestor).config.stripe_context.to_s
    assert_equal "original", client.instance_variable_get(:@requestor).config.stripe_context.to_s
  end
end
