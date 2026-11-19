import { defineConfig } from 'vitest/config'
import solid from '../node_modules/vite-plugin-solid/dist/esm/index.mjs'
import path from 'node:path'

export default defineConfig({
  root: process.cwd(),
  plugins: [solid({ ssr: true, hot: false })],
  resolve: {
    conditions: ['browser', 'development'],
    alias: {
      'solid-js/web': path.resolve(process.cwd(), 'node_modules/solid-js/web/dist/web.js'),
      'solid-js/store': path.resolve(process.cwd(), 'node_modules/solid-js/store/dist/store.js'),
      'solid-js': path.resolve(process.cwd(), 'node_modules/solid-js/dist/solid.js'),
      '@tanstack/query-core': path.resolve(process.cwd(), 'packages/query-core/src/index.ts'),
      '@tanstack/solid-query': path.resolve(process.cwd(), 'packages/solid-query/src/index.ts'),
    },
  },
  test: {
    environment: 'jsdom',
    testTimeout: 30_000,
    watch: false,
    typecheck: { enabled: false },
    pool: 'forks',
    minWorkers: 1,
    maxWorkers: 1,
  },
})
