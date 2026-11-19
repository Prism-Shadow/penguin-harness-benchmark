import { sourceContainer, serviceGraphs } from './source_container.mjs';
import { exportsOf, mod } from './contract_runtime.mjs';
import { debugSession } from './debug_session.mjs';

export async function publicWasmSession({
  enableDWARF,
  rpc,
  url = 'wasm://module.wasm',
  debugSymbols,
  codeOffset = 0,
  scriptId = 'script-1',
  disassembly = ['(module)', '  (func)'],
  bytecode = 'AA==',
} = {}) {
  const calls = [];
  let spawned = 0;
  let loaded = 0;
  let disposed = 0;
  const dwarfModule = {
    load: async () => { loaded++; return ({ spawn: () => {
      spawned++;
      return {
        rpc: { sendMessage: async (...args) => {
          calls.push(args);
          return rpc ? rpc(...args) : undefined;
        } },
        dispose: async () => { disposed++; },
      };
    } }); },
    prompt() {},
  };
  const cdp = {
    Debugger: {
      getScriptSource: async () => ({ bytecode, scriptSource: 'binary' }),
      disassembleWasmModule: async () => ({
        chunk: { lines: disassembly, bytecodeOffsets: disassembly.map((_, index) => index * 2) },
      }),
      nextWasmDisassemblyChunk: async () => undefined,
    },
  };
  const events = [];
  const launchConfig = { sourceMaps: true, ...(enableDWARF === undefined ? {} : { enableDWARF }) };
  const container = await sourceContainer(events, { cdp, dwarfModule, launchConfig });
  const session = await debugSession({ container, cdp, launchConfig });
  await session.emit('Debugger.scriptParsed', {
    url,
    scriptId,
    executionContextId: 1,
    startLine: 0,
    startColumn: 0,
    endLine: 1,
    endColumn: 0,
    hash: '',
    scriptLanguage: 'WebAssembly',
    debugSymbols,
    codeOffset,
  });
  const compiled = await container.getScriptById(scriptId).source;
  const mapped = await container.waitForSourceMapSources(compiled);
  const { disposeContainer } = exportsOf(await mod('src/ioc-extras.ts'));
  return {
    ...session,
    workerDisposals: () => disposed,
    loadCalls: () => loaded,
    dispose: async () => {
      await session.dispose();
      disposeContainer(serviceGraphs.get(container));
      await new Promise(resolve => setImmediate(resolve));
    }, calls, compiled, container, cdp, sourceEvents: events, mapped, spawned,
    pause: async (offset = codeOffset + 7, frameId = 'frame') => {
      await session.emit('Debugger.paused', { reason: 'other', callFrames: [{
        callFrameId: frameId, functionName: 'main', url,
        location: { scriptId, lineNumber: 0, columnNumber: offset },
        scopeChain: [], this: { type: 'undefined' },
      }] });
      return session.thread.stackTrace({ threadId: session.thread.id });
    },
  };
}
