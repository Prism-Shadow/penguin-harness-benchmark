import { NgZone } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '../../query-core/src/index'
import { injectIsFetching } from '../src/inject-is-fetching'
import { provideAngularQuery } from '../src/providers'

afterEach(() => {
  TestBed.resetTestingModule()
  vi.restoreAllMocks()
})

it('7040 runs fetching-counter cache notifications inside NgZone', async () => {
  const client = new QueryClient()
  TestBed.configureTestingModule({ providers: [provideAngularQuery(client)] })
  const zone = TestBed.inject(NgZone)
  const run = vi.spyOn(zone, 'run')
  const fetching = TestBed.runInInjectionContext(() => injectIsFetching())
  run.mockClear()

  let resolve!: (value: string) => void
  const pending = new Promise<string>((done) => { resolve = done })
  const request = client.fetchQuery({ queryKey: ['zone-counter'], queryFn: () => pending })
  await vi.waitFor(() => expect(fetching()).toBe(1), { timeout: 15000 })
  expect(run).toHaveBeenCalled()
  resolve('done')
  await request
  await vi.waitFor(() => expect(fetching()).toBe(0), { timeout: 15000 })
})
