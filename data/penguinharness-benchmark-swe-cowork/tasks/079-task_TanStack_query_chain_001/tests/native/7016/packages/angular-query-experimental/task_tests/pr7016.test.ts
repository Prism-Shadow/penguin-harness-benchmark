import { Component, input } from '@angular/core'
import { TestBed } from '@angular/core/testing'
import { SIGNAL, signalSetFn } from '@angular/core/primitives/signals'
import { afterEach, expect, it, vi } from 'vitest'
import { QueryClient } from '../../query-core/src/index'
import { injectMutation } from '../src/inject-mutation'
import { provideAngularQuery } from '../src/providers'

afterEach(() => TestBed.resetTestingModule())

it('7016 supports a required input signal in injectMutation options', async () => {
  const client = new QueryClient()
  TestBed.configureTestingModule({ providers: [provideAngularQuery(client)] })

  @Component({ standalone: true, template: '' })
  class Host {
    name = input.required<string>()
    mutation = injectMutation(() => ({
      mutationKey: ['required-input', this.name()],
      mutationFn: async () => this.name(),
    }))
  }

  const fixture = TestBed.createComponent(Host)
  signalSetFn((fixture.componentInstance.name as any)[SIGNAL], 'ready')
  fixture.detectChanges()
  fixture.componentInstance.mutation.mutate()
  await vi.waitFor(() => {
    expect(fixture.componentInstance.mutation.data()).toBe('ready')
  }, { timeout: 15000 })
  expect(client.getMutationCache().find({ mutationKey: ['required-input', 'ready'] })).toBeDefined()
})
