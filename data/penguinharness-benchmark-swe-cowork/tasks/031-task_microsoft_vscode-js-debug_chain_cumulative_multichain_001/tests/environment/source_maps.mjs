import { exportsOf, mod, logger } from './contract_runtime.mjs';
import { fileURLToPath, pathToFileURL } from 'node:url';

export async function sourceMapServices(maps) {
  const { SourceMapFactory } = exportsOf(await mod('src/common/sourceMaps/sourceMapFactory.ts'));
  const resolver = {
    urlToAbsolutePath: async ({ url }) => url.startsWith('file:') ? fileURLToPath(url) : undefined,
    shouldResolveSourceMap: () => true,
    rebaseRemoteToLocal: value => value,
  };
  const resource = { fetch: async url => {
    const key = maps.has(url) ? url : pathToFileURL(url).href;
    if (!maps.has(key)) throw new Error(`Unexpected source map ${url}`);
    return { ok: true, url, statusCode: 200, body: JSON.stringify(maps.get(key)) };
  } };
  const dap = { output: event => { throw new Error(event.output); } };
  return { resolver, resource, sourceMapFactory: new SourceMapFactory(resolver, resource, dap, logger()),
    launchConfig: { sourceMaps: true } };
}
