import assert from 'node:assert/strict';
import { load } from '../support/load.mjs';

const { Random } = await load('packages/transformers/src/transformers.js');
const vectors = [
    [42, [0.6394267984578837, 0.025010755222666936, 0.27502931836911926]],
    [0, [0.8444218515250481, 0.7579544029403025, 0.420571580830845]],
    [17, [0.5219839097124932, 0.8066907771186791, 0.9604947743238768]],
];
for (const [seed, expected] of vectors) {
    const generator = new Random(seed);
    const independent = new Random(seed);
    for (const value of expected) {
        const actual = generator.random();
        assert.equal(typeof actual, 'number');
        assert.equal(actual, value);
    }
    assert.equal(independent.random(), expected[0]);
    generator.seed(seed);
    assert.equal(generator.random(), expected[0]);
}
const generator = new Random(42);
for (let index = 0; index < 1000; index += 1) {
    const value = generator.random();
    assert.ok(value >= 0 && value < 1);
}
assert.equal(generator.random(), 0.09935462460613032);

const wide = await import('../support/random-vectors.mjs');
for (const [seed, expected] of wide.vectors) {
    const rng = new Random(seed);
    const independent = new Random(Math.abs(seed));
    let index = 0;
    for (let i = 0; i <= wide.indices.at(-1); ++i) {
        const actual = rng.random();
        assert.equal(typeof actual, 'number');
        assert.equal(actual, independent.random(), `signed integer seed ${seed}, draw ${i}`);
        if (wide.indices[index] === i) {
            assert.equal(actual, expected[index++], `Python seed ${seed}, draw ${i}`);
        }
    }
    rng.seed(seed);
    assert.equal(rng.random(), expected[0]);
}
const { random } = await load('packages/transformers/src/transformers.js');
random.seed(-42);
assert.equal(random.random(), vectors[0][1][0]);
const local = new Random(-17);
random.seed(0);
assert.equal(local.random(), vectors[2][1][0]);
assert.equal(random.random(), vectors[1][1][0]);
