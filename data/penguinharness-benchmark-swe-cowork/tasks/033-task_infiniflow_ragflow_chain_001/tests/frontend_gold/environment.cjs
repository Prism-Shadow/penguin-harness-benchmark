const {TestEnvironment} = require('jest-environment-jsdom');
module.exports = class extends TestEnvironment {
 async setup() {
  await super.setup();
  for (const name of ['Response','Request','Headers','ReadableStream','TransformStream','TextDecoderStream','TextEncoder','TextDecoder','AbortController','AbortSignal','DOMException']) this.global[name] = globalThis[name];
  this.global.IS_REACT_ACT_ENVIRONMENT = true;
 }
};
