import { createServer } from 'vite'
import solid from '../node_modules/vite-plugin-solid/dist/esm/index.mjs'
import path from 'node:path'
const server = await createServer({
  configFile: false, root: process.cwd(), logLevel: 'error',
  plugins: [solid({ ssr: true, hot: false })],
  resolve: { alias: { '@tanstack/query-core': path.resolve('packages/query-core/src/index.ts') } },
  ssr: { noExternal: ['@tanstack/query-core', '@tanstack/solid-query'] },
  server: { middlewareMode: true, watch: null, hmr: false },
})
try {
  const { render } = await server.ssrLoadModule('/packages/solid-query/task_tests/render-hydration.tsx')
  console.log(JSON.stringify(await render()))
} finally {
  await server.close()
}
