"use strict";
const { assert, fs, os, path, sinon, load, fresh } = require("../support.cjs");

describe("no-backend secret guidance", function () {
  it("returns empty account groups and uses consolidated warning output", async function () {
    const api = load("src/gcp/apphosting.ts");
    const utils = load("src/utils.ts");
    sinon.stub(api, "listBackends").resolves({ backends: [], unreachable: [] });
    const warning = sinon.stub(utils, "logWarning");
    try {
      const dialogs = fresh("src/apphosting/secrets/dialogs.ts");
      const result = await dialogs.selectBackendServiceAccounts("123", "demo", {});
      assert.deepEqual(result, { buildServiceAccounts: [], runServiceAccounts: [] });
      assert.equal(warning.callCount, 1);
      assert.equal(warning.firstCall.args[0], dialogs.WARN_NO_BACKENDS);
      assert.ok(dialogs.WARN_NO_BACKENDS.includes("apphosting:secrets:grantaccess"));
    } finally { sinon.restore(); }
  });
});
