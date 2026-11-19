import { defineConfig } from 'vitest/config'
import solid from '../packages/solid-query/node_modules/vite-plugin-solid/dist/esm/index.mjs'
import path from 'node:path'

export default defineConfig({
  root: process.cwd(),
  plugins: [solid()],
  resolve: {
    alias: {
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
