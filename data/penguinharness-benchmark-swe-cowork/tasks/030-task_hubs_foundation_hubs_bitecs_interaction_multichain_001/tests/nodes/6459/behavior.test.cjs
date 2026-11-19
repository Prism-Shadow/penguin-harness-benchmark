"use strict";

const test = require("node:test");
const { run } = require("../_support/contracts.cjs");

test("PR 6459 production behavior contract", () => run(6459));
