import { runScript } from '../support/run-script.mjs';
runScript(new URL('../support/wasm-loader.mjs', import.meta.url), ['blob']);
runScript(new URL('../support/wasm-loader.mjs', import.meta.url), ['relative']);
