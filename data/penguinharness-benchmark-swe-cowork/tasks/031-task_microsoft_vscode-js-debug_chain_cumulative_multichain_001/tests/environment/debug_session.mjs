import { exportsOf, mod, logger } from './contract_runtime.mjs';

export async function debugSession({ container, cdp, launchConfig = {}, evaluator, shutdown } = {}) {
  const { Thread } = exportsOf(await mod('src/adapter/threads.ts'));
  const { ShutdownParticipants } = exportsOf(await mod('src/ui/shutdownParticipants.ts'));
  const { baseDefaults } = exportsOf(await mod('src/configuration.ts'));
  const listeners = new Map();
  const events = [];
  for (const domain of ['Runtime', 'Debugger', 'Inspector', 'Profiler']) {
    cdp[domain] ||= {};
    cdp[domain].on = (name, listener) => listeners.set(`${domain}.${name}`, listener);
  }
  cdp.Runtime.enable ||= async () => ({});
  cdp.Profiler.enable ||= async () => ({});
  cdp.Debugger.enable ||= async () => ({ debuggerId: 'public-contract' });
  const contents = new Map();
  cdp.Debugger.getScriptSource ||= async ({ scriptId }) => ({ scriptSource: contents.get(scriptId) });
  const thread = new Thread(
    container, cdp,
    { thread() {}, stopped: event => events.push(event), continued() {}, output() {} },
    { name: () => 'contract', initialize() {}, scriptUrlToUrl: url => url },
    {}, logger(), evaluator || { setReturnedValue() {} }, {},
    { ...baseDefaults, ...launchConfig },
    { executionContextWasCleared() {}, isEntrypointBreak: () => false,
      shouldPauseAt: async () => true,
      isEntrypointCdpBreak: () => false, _resolvedBreakpoints: new Map() },
    {}, { apply() {} }, { getSmartStepDirection: async () => undefined },
    shutdown || new ShutdownParticipants(),
  );
  thread.dapInitialized();
  return {
    thread, events,
    emit: async (name, event) => {
      const listener = listeners.get(name);
      if (!listener) throw new Error(`No production listener for ${name}`);
      return listener(event);
    },
    discover: async (event, content = '') => {
      const script = { executionContextId: 1, startLine: 0, startColumn: 0,
        endLine: 1, endColumn: 0, hash: '', scriptLanguage: 'JavaScript', ...event };
      contents.set(script.scriptId, content);
      await listeners.get('Debugger.scriptParsed')(script);
      return container.getScriptById(script.scriptId).source;
    },
    dispose: () => thread.dispose(),
  };
}
