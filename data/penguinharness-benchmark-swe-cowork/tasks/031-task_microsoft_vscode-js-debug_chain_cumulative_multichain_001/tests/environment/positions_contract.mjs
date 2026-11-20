import assert from 'node:assert/strict';

export function base0Position(lineNumber, columnNumber) {
  return {
    base0: { lineNumber, columnNumber },
    base1: { lineNumber: lineNumber + 1, columnNumber: columnNumber + 1 },
    base01: { lineNumber, columnNumber: columnNumber + 1 },
  };
}

export function assertPositionProjections({ Base0Position }) {
  for (const [lineNumber, columnNumber] of [[0, 0], [2, 4], [8, 11]]) {
    const position = new Base0Position(lineNumber, columnNumber);
    const fixture = base0Position(lineNumber, columnNumber);
    for (const projection of ['base0', 'base1', 'base01']) {
      assert.equal(position[projection].lineNumber, fixture[projection].lineNumber);
      assert.equal(position[projection].columnNumber, fixture[projection].columnNumber);
    }
    assert.equal(position.compare(new Base0Position(lineNumber, columnNumber)), 0);
    assert.ok(position.compare(new Base0Position(lineNumber, columnNumber + 1)) < 0);
    assert.ok(position.compare(new Base0Position(lineNumber + 1, 0)) < 0);
  }
}
