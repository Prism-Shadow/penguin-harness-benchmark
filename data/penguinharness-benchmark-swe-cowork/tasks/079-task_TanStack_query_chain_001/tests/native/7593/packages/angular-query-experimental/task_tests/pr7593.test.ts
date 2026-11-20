import { TestBed } from '@angular/core/testing'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '../../query-core/src/index'
import { injectInfiniteQuery } from '../src/inject-infinite-query'
import { provideAngularQuery } from '../src/providers'

afterEach(() => TestBed.resetTestingModule())

it('7593 keeps injectInfiniteQuery on the provided client and returns page parameters', async () => {
  const client = new QueryClient()
  TestBed.configureTestingModule({ providers: [provideAngularQuery(client)] })
  const query = TestBed.runInInjectionContext(() => injectInfiniteQuery(() => ({
    queryKey: ['angular-infinite'],
    queryFn: async ({ pageParam }: { pageParam: number }) => `page:${pageParam}`,
    initialPageParam: 7,
    getNextPageParam: () => undefined,
  })))
  await vi.waitFor(() => expect(query.isSuccess()).toBe(true), { timeout: 5000 })
  expect(query.data()).toEqual({ pages: ['page:7'], pageParams: [7] })
  expect(client.getQueryData(['angular-infinite'])).toEqual({ pages: ['page:7'], pageParams: [7] })
})
