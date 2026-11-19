function project(exportName, left, right, candidates) {
  const values = candidates || [left];
  if (exportName === "contains") return [values, right];
  if (exportName === "toBeOneOf" || exportName === "default") return [right, values];
  const object = {};
  values.forEach((value, index) => { object[`entry${index}`] = value; });
  if (exportName === "toContainValues") return [object, [right]];
  return [object, right];
}

function* deepEqualityCases(exportName) {
  const shared = { count: 7, tags: ["blue"] };
  const aliased = { first: shared, second: shared };
  const independent = { first: { count: 7, tags: ["blue"] }, second: { count: 7, tags: ["blue"] } };
  const pair = (name, left, right, expected) => ({ name, args: project(exportName, left, right), expected });
  yield pair("shared-left", aliased, independent, true);
  yield pair("shared-right", independent, aliased, true);
  yield pair("unequal-nested", aliased, { first: shared, second: { count: 8, tags: ["blue"] } }, false);
  yield pair("missing-key", { count: 7 }, { count: 7, extra: 1 }, false);
  yield pair("extra-key", { count: 7, extra: 1 }, { count: 7 }, false);
  yield pair("array-order", { items: [1, 2] }, { items: [2, 1] }, false);
  yield pair("sparse-length", { items: [] }, { items: new Array(2) }, false);
  yield pair("sparse-length-reversed", { items: new Array(2) }, { items: [] }, false);
  yield pair("same-sparse-length", { items: new Array(2) }, { items: new Array(2) }, true);
  const leftCycle = { count: 7 };
  const rightCycle = { count: 7 };
  leftCycle.self = leftCycle;
  rightCycle.self = rightCycle;
  yield pair("equal-cycles", leftCycle, rightCycle, true);
  rightCycle.count = 8;
  yield pair("unequal-cycles", leftCycle, rightCycle, false);
  yield {
    name: "search-after-miss",
    args: project(exportName, null, independent, [{ count: 8 }, aliased]),
    expected: true
  };
  yield { name: "empty-candidates", args: project(exportName, null, independent, []), expected: false };
  const mutableLeft = { count: 1 };
  const mutableRight = { count: 2 };
  yield pair("before-mutation", mutableLeft, mutableRight, false);
  mutableRight.count = 1;
  yield pair("after-mutation", mutableLeft, mutableRight, true);
  mutableLeft.count = 3;
  yield pair("after-second-mutation", mutableLeft, mutableRight, false);
}

module.exports = { deepEqualityCases };
