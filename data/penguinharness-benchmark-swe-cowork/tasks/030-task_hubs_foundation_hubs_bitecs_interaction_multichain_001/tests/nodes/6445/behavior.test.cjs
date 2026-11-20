"use strict";

const test = require("node:test");
const { run } = require("../_support/contracts.cjs");

test("PR 6445 production behavior contract", () => run(6445));
