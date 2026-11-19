import { defineConfig } from 'vitest/config'
import path from 'node:path'

export default defineConfig({
  root: process.cwd(),
  resolve: {
    alias: {
      '@tanstack/query-core': path.resolve(process.cwd(), 'packages/query-core/src/index.ts'),
    },
  },
  test: {
    environment: 'jsdom',
    testTimeout: 30_000,
    setupFiles: ['packages/angular-query-experimental/task_tests/angular.setup.ts'],
    watch: false,
    typecheck: { enabled: false },
    globals: true,
    restoreMocks: true,
    pool: 'forks',
    minWorkers: 1,
    maxWorkers: 1,
  },
})
