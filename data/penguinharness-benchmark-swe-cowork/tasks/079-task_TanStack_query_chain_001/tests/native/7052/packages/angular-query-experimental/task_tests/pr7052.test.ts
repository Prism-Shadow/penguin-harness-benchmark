import { TestBed } from '@angular/core/testing'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '../../query-core/src/index'
import { injectQuery } from '../src/inject-query'
import { provideAngularQuery } from '../src/providers'

afterEach(() => TestBed.resetTestingModule())

it('7052 evaluates the Angular throwOnError callback with the failed query', async () => {
  const client = new QueryClient()
  const boundary = vi.fn(() => false)
  TestBed.configureTestingModule({ providers: [provideAngularQuery(client)] })
  const query = TestBed.runInInjectionContext(() => injectQuery(() => ({
    queryKey: ['angular-error'],
    queryFn: async () => { throw new Error('angular failure') },
    retry: false,
    throwOnError: boundary,
  })))
  void query.status()
  await vi.waitFor(() => expect(boundary).toHaveBeenCalledTimes(1), { timeout: 15000 })
  expect(boundary).toHaveBeenCalledWith(
    expect.objectContaining({ message: 'angular failure' }),
    expect.objectContaining({ queryKey: ['angular-error'] }),
  )
  expect(query.isError()).toBe(true)
})
