import { defineConfig } from 'vitest/config'
import path from 'node:path'

export default defineConfig({
  root: process.cwd(),
  resolve: {
    alias: {
      '@tanstack/query-core': path.resolve(process.cwd(), 'packages/query-core/src/index.ts'),
      '@tanstack/solid-query': path.resolve(process.cwd(), 'packages/solid-query/src/index.ts'),
      '@tanstack/vue-query': path.resolve(process.cwd(), 'packages/vue-query/src/index.ts'),
      'vue-demi': path.resolve(process.cwd(), 'packages/vue-query/node_modules/vue-demi'),
      'solid-js': path.resolve(process.cwd(), 'node_modules/solid-js'),
    },
  },
  test: {
    environment: 'node',
    watch: false,
    typecheck: { enabled: false },
    restoreMocks: true,
    pool: 'forks',
    minWorkers: 1,
    maxWorkers: 1,
  },
})
