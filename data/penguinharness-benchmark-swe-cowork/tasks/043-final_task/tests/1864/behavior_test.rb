# frozen_string_literal: true

require "minitest/autorun"
require "stripe"
require_relative "../transport_harness"

class ProductCatalogImportApiTest < Minitest::Test
  include TransportHarness

  def test_all_declared_status_details_hydrate_through_real_transport
    client = Stripe::StripeClient.new("sk_test_contract")
    namespace = Stripe::V2::Commerce::ProductCatalogImport::StatusDetails
    [false, true].each do |integer_wire|
      wire = ->(number) { integer_wire ? number : number.to_s }
      cases = [
        ["awaiting_upload", { awaiting_upload: { upload_url: { expires_at: "2026-10-01T00:00:00Z", url: "https://upload.example.test/catalog" } } }],
        ["failed", { failed: { code: "invalid_feed", failure_message: "bad row", type: "validation_error" } }],
        ["processing", { processing: { error_count: wire.call(3), success_count: wire.call(9007199254740993) } }],
        ["succeeded", { succeeded: { success_count: wire.call(17) } }],
        ["succeeded_with_errors", { succeeded_with_errors: {
          error_count: wire.call(2), success_count: wire.call(31),
          error_file: { content_type: "text/csv", size: wire.call(1048577),
                        download_url: { expires_at: "2026-10-02T00:00:00Z", url: "https://download.example.test/errors" } },
          samples: [{ error_message: "bad quantity", field: "quantity", id: "row_a", row: wire.call(4) },
                    { error_message: "bad price", field: "price", id: "row_b", row: wire.call(9) }],
        } }],
      ]
      responses = cases.map.with_index do |(status, details), index|
        [200, import_payload("pci_schema_#{index}").merge(status: status, status_details: details)]
      end
      with_http_responses(responses) do |requests|
        cases.each_with_index do |(status, _details), index|
          resource = client.v2.commerce.product_catalog.imports.retrieve("pci_schema_#{index}")
          assert_instance_of Stripe::V2::Commerce::ProductCatalogImport, resource
          assert_instance_of namespace, resource.status_details
          assert_equal status, resource.status
          assert_equal "GET", requests[index][:method]
          assert_equal "/v2/commerce/product_catalog/imports/pci_schema_#{index}", URI.parse(requests[index][:path]).path
          detail = resource.status_details.public_send(status)
          case status
          when "awaiting_upload"
            assert_instance_of namespace::AwaitingUpload, detail
            assert_instance_of namespace::AwaitingUpload::UploadUrl, detail.upload_url
            assert_equal "2026-10-01T00:00:00Z", detail.upload_url.expires_at
            assert_equal "https://upload.example.test/catalog", detail.upload_url.url
          when "failed"
            assert_instance_of namespace::Failed, detail
            assert_equal ["invalid_feed", "bad row", "validation_error"], [detail.code, detail.failure_message, detail.type]
          when "processing"
            assert_instance_of namespace::Processing, detail
            assert_equal [3, 9007199254740993], [detail.error_count, detail.success_count]
          when "succeeded"
            assert_instance_of namespace::Succeeded, detail
            assert_equal 17, detail.success_count
          when "succeeded_with_errors"
            assert_instance_of namespace::SucceededWithErrors, detail
            assert_equal [2, 31], [detail.error_count, detail.success_count]
            assert_instance_of namespace::SucceededWithErrors::ErrorFile, detail.error_file
            assert_equal ["text/csv", 1048577], [detail.error_file.content_type, detail.error_file.size]
            assert_instance_of namespace::SucceededWithErrors::ErrorFile::DownloadUrl, detail.error_file.download_url
            assert_equal "2026-10-02T00:00:00Z", detail.error_file.download_url.expires_at
            assert_equal "https://download.example.test/errors", detail.error_file.download_url.url
            assert_equal 2, detail.samples.length
            detail.samples.each { |sample| assert_instance_of namespace::SucceededWithErrors::Sample, sample }
            assert_equal [["bad quantity", "quantity", "row_a", 4], ["bad price", "price", "row_b", 9]],
                         detail.samples.map { |sample| [sample.error_message, sample.field, sample.id, sample.row] }
          end
        end
        assert_equal 5, requests.length
      end
    end
  end

  def test_typed_params_reach_json_transport_and_registry
    client = Stripe::StripeClient.new("sk_test_contract", stripe_context: "catalog_owner")
    service = client.v2.commerce.product_catalog.imports
    params = Stripe::V2::Commerce::ProductCatalog::ImportCreateParams.new(
      feed_type: "pricing", metadata: nil, mode: "merge"
    )
    identifier = "pci_contract_87"
    replies = [[200, import_payload(identifier)],
               [200, { object: "list", data: [import_payload(identifier)], next_page_url: nil }],
               [200, import_payload(identifier)],
               [400, { error: { type: "invalid_request_error", message: "invalid feed", param: "feed_type" } }]]
    with_http_responses(replies) do |requests|
      created = service.create(params)
      assert_instance_of Stripe::V2::Commerce::ProductCatalogImport, created
      assert_equal identifier, created.id
      assert_equal 23, created.status_details.succeeded.success_count
      assert_equal "POST", requests[0][:method]
      assert_equal "/v2/commerce/product_catalog/imports", requests[0][:path]
      assert_equal({ "feed_type" => "pricing", "metadata" => nil, "mode" => "merge" },
                   JSON.parse(requests[0][:body]))
      listed = service.list(Stripe::V2::Commerce::ProductCatalog::ImportListParams.new(limit: 2, status: "succeeded"))
      assert_instance_of Stripe::V2::Commerce::ProductCatalogImport, listed.data.first
      assert_equal identifier, listed.data.first.id
      assert_equal "GET", requests[1][:method]
      assert_equal({ "limit" => "2", "status" => "succeeded" }, URI.decode_www_form(URI.parse(requests[1][:path]).query).to_h)
      assert_equal identifier, service.retrieve("pci/odd", Stripe::V2::Commerce::ProductCatalog::ImportRetrieveParams.new).id
      assert_equal "/v2/commerce/product_catalog/imports/pci%2Fodd", URI.parse(requests[2][:path]).path
      assert_raises(Stripe::InvalidRequestError) { service.create(feed_type: "invalid") }
      assert_equal ["catalog_owner"], requests[0][:headers]["stripe-context"]
    end
  end

  def test_v2_commerce_exposes_typed_import_resource_and_service
    client = Stripe::StripeClient.new("sk_test_123")
    service = client.v2.commerce.product_catalog.imports
    resource = Stripe::V2::Commerce::ProductCatalogImport.construct_from(
      id: "pci_123",
      object: "v2.commerce.product_catalog_import",
      feed_type: "pricing",
      status: "awaiting_upload"
    )

    assert_instance_of Stripe::V2::Commerce::ProductCatalog::ImportService, service
    assert_equal "v2.commerce.product_catalog_import", resource.class.object_name
    assert_equal "pricing", resource.feed_type
    assert_equal "awaiting_upload", resource.status
  end
end
