"use strict";
const { assert, fs, os, path, sinon, load, fresh } = require("../support.cjs");

describe("default Compute Engine identity", function () {
  it("uses the Compute Engine service-account domain", function () {
    const compute = load("src/gcp/computeEngine.ts");
    assert.ok(compute && typeof compute.getDefaultServiceAccount === "function", "compute identity helper must exist");
    for (const number of ["123456", "987654321"]) {
      assert.equal(compute.getDefaultServiceAccount(number), `${number}-compute@developer.gserviceaccount.com`);
    }
  });
});
