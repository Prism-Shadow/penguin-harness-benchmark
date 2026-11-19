// Construct legal objects whose own properties cannot be queried through an
// untrusted receiver.hasOwnProperty member. No production helpers are imported.
function* ownKeyCases(name) {
  const args = (object, keys) => [object, name === 'toContainKey' ? keys[0] : keys];
  const objects = [
    ['null-prototype', Object.assign(Object.create(null), { present: 1 })],
    ['shadow-zero', { present: 1, hasOwnProperty: 0 }],
    ['shadow-string', { present: 1, hasOwnProperty: 'data' }],
    ['lying-false', { present: 1, hasOwnProperty: () => false }],
    ['lying-true', { present: 1, hasOwnProperty: () => true }],
    ['inherited-key', Object.assign(Object.create({ inherited: 1 }), { present: 1 })]
  ];
  for (const [label, object] of objects) {
    yield { name: label + '-hit', args: args(object, ['present']), expected: true };
    yield { name: label + '-miss', args: args(object, ['absent']), expected: false };
    yield { name: label + '-inherited', args: args(object, ['inherited']), expected: false };
    if (name !== 'toContainKey') {
      yield { name: label + '-mixed', args: args(object, ['absent', 'present']), expected: name === 'toContainAnyKeys' };
      yield { name: label + '-empty', args: args(object, []), expected: name === 'toContainKeys' };
    }
  }
  const special = Object.defineProperty({}, 'hidden', { value: 1 });
  const key = Symbol('own');
  special[key] = 1;
  yield { name: 'non-enumerable-own-key', args: args(special, ['hidden']), expected: true };
  yield { name: 'symbol-own-key', args: args(special, [key]), expected: true };
  if (name === 'toContainKeys') {
    const object = Object.assign(Object.create(null), { present: 1 });
    for (const keys of [['present'], ['present', 'missing']]) {
      yield {
        name: 'custom-every-' + keys.length,
        args: [object, { every: callback => keys.every(callback) }],
        expected: keys.length === 1
      };
    }
  }
}
module.exports = { ownKeyCases };
