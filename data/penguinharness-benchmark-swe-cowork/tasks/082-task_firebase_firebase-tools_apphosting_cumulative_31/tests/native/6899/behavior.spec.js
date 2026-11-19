"use strict";
const { assert, fs, os, path, sinon, load, fresh } = require("../support.cjs");

describe("grant-access CLI registration", function () {
  it("registers its positional argument and backend selectors", function () {
    sinon.stub(load("src/experiments.ts"), "isEnabled").callsFake((name) => name === "apphosting");
    const Commander = require("commander").Command;
    const cli = new Commander();
    const client = { cli, errorOut(error) { throw error; } };
    load("src/commands/index.ts").load(client);
    assert.equal(typeof client.apphosting.secrets.grantaccess, "function");
    const registered = cli.commands.find((candidate) => candidate.name() === "apphosting:secrets:grantaccess");
    assert.ok(registered, "command must register with Commander");
    assert.equal(registered._args.length, 1);
    assert.equal(registered._args[0].name, "secretName");
    assert.equal(registered._args[0].required, true);
    const longFlags = registered.options.map((option) => option.long);
    assert.ok(longFlags.includes("--location"));
    assert.ok(longFlags.includes("--backend"));
  });
});
