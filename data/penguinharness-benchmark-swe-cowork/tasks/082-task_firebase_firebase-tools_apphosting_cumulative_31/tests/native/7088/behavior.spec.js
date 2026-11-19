"use strict";
const { assert, sinon, load, fresh, backendSetup } = require("../support.cjs");
const nock = require("nock");
const origin = "https://mobilesdk-pa.googleapis.com";
const route = "/v1/accessmanagement/tos:getStatus";
const response = (status) => ({ perServiceStatus: [
  { tosId: "APP_CHECK", serviceStatus: { status: "ACCEPTED" } },
  { tosId: "APP_HOSTING_TOS", serviceStatus: { status } },
] });

function endpoint(body, code = 200) {
  return nock(origin, { reqheaders: { authorization: "Bearer fixture-token" } }).get(route).reply(function (_uri, requestBody) {
    assert.ok(requestBody === "" || requestBody === undefined, "ToS status request has no body");
    return [code, body];
  });
}

describe("Terms of Service wire protocol and backend-create gate", function () {
  beforeEach(function () {
    nock.disableNetConnect();
    load("src/apiv2.ts").setAccessToken("fixture-token");
  });
  afterEach(function () {
    load("src/apiv2.ts").setAccessToken("");
    nock.cleanAll();
    nock.enableNetConnect();
  });
  it("honors the documented Firedata origin override", async function () {
    const previous = process.env.FIREBASE_FIREDATA_URL;
    process.env.FIREBASE_FIREDATA_URL = "https://tos-fixture.example";
    const body = response("ACCEPTED");
    const http = nock("https://tos-fixture.example", { reqheaders: { authorization: "Bearer fixture-token" } }).get(route).reply(200, body);
    try {
      assert.deepEqual(await fresh("src/gcp/firedata.ts").getTosStatus(), body);
      http.done();
    } finally {
      if (previous === undefined) delete process.env.FIREBASE_FIREDATA_URL;
      else process.env.FIREBASE_FIREDATA_URL = previous;
      fresh("src/gcp/firedata.ts");
    }
  });
  for (const state of ["ACCEPTED", "TERMS_UPDATED", null]) {
    it(`makes the authenticated GET and interprets product status ${state}`, async function () {
      const body = response(state);
      const http = endpoint(body);
      const firedata = fresh("src/gcp/firedata.ts");
      assert.equal(firedata.APPHOSTING_TOS_ID, "APP_HOSTING_TOS");
      assert.equal(firedata.APP_CHECK_TOS_ID, "APP_CHECK");
      const actual = await firedata.getTosStatus();
      assert.deepEqual(actual, body);
      assert.equal(firedata.getAcceptanceStatus(actual, firedata.APPHOSTING_TOS_ID), state);
      assert.equal(firedata.isProductTosAccepted(actual, firedata.APPHOSTING_TOS_ID), state === "ACCEPTED");
      http.done();
    });
  }
  it("rejects a missing product rather than borrowing another product's acceptance", async function () {
    const body = { perServiceStatus: [{ tosId: "APP_CHECK", serviceStatus: { status: "ACCEPTED" } }] };
    const http = endpoint(body);
    const firedata = fresh("src/gcp/firedata.ts");
    const actual = await firedata.getTosStatus();
    assert.throws(() => firedata.getAcceptanceStatus(actual, "APP_HOSTING_TOS"), /Missing terms of service status/);
    assert.throws(() => firedata.isProductTosAccepted(actual, "APP_HOSTING_TOS"), /Missing terms of service status/);
    http.done();
  });
  for (const code of [401, 403, 500]) {
    it(`propagates HTTP ${code}`, async function () {
      const http = endpoint({ error: { code, message: "ToS unavailable" } }, code);
      await assert.rejects(fresh("src/gcp/firedata.ts").getTosStatus());
      http.done();
    });
  }
  it("propagates transport failure", async function () {
    const http = nock(origin).get(route).replyWithError("connection reset");
    await assert.rejects(fresh("src/gcp/firedata.ts").getTosStatus());
    http.done();
  });
  for (const state of ["ACCEPTED", "TERMS_UPDATED", null, "missing", "transport"]) {
    it(`runs the real command before/action chain for ${state}`, async function () {
      const calls = backendSetup();
      const http = state === "transport" ? endpoint({ error: { message: "unavailable" } }, 503)
        : endpoint(state === "missing" ? { perServiceStatus: [] } : response(state));
      const command = fresh("src/commands/apphosting-backends-create.ts").command;
      const pending = command.runner()({ project: "demo", interactive: true, app: "dashboard", location: "us-central1", serviceAccount: "custom@demo" });
      if (state === "ACCEPTED") {
        await pending;
        assert.equal(calls.create.callCount, 1);
      } else {
        await assert.rejects(pending);
        assert.equal(calls.create.callCount, 0);
        assert.equal(calls.permissions.callCount, 0);
        assert.equal(calls.provision.callCount, 0);
        assert.equal(calls.createApp.callCount, 0);
        assert.equal(calls.developer.callCount + calls.cloudBuild.callCount, 0);
      }
      http.done();
    });
  }
});
