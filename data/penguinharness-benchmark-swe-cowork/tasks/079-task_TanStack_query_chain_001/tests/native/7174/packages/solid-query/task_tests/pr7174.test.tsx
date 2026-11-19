import { render, waitFor } from '@solidjs/testing-library'
import { expect, it } from 'vitest'
import { QueryClient, QueryClientProvider, createQuery } from '../src/index'

it('7174 keeps a Solid query bound to its declared cache key', async () => {
  const client = new QueryClient()
  function Page() {
    const query = createQuery(() => ({
      queryKey: ['solid-declared-key'],
      queryFn: async () => ({ value: 7 }),
    }))
    return <div>{query.data?.value ?? 'pending'}</div>
  }
  const rendered = render(() => (
    <QueryClientProvider client={client}><Page /></QueryClientProvider>
  ))
  await waitFor(() => expect(rendered.getByText('7')).toBeTruthy(), { timeout: 5000 })
  expect(client.getQueryData(['solid-declared-key'])).toEqual({ value: 7 })
  expect(client.getQueryData(['negative-control-key'])).toBeUndefined()
})
