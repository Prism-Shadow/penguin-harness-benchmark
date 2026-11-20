import { render, waitFor } from '@solidjs/testing-library'
import { expect, it } from 'vitest'
import { QueryClient, QueryClientProvider, createQuery } from '../src/index'

it('7272 preserves public placeholder state while the query is pending', async () => {
  const client = new QueryClient()
  function Page() {
    const query = createQuery(() => ({
      queryKey: ['solid-placeholder'],
      queryFn: () => new Promise<string>(() => undefined),
      placeholderData: 'waiting',
    }))
    return <div>{query.status}:{String(query.isPlaceholderData)}:{query.data}</div>
  }
  const rendered = render(() => (
    <QueryClientProvider client={client}><Page /></QueryClientProvider>
  ))
  await waitFor(() => expect(rendered.getByText('success:true:waiting')).toBeTruthy(), { timeout: 5000 })
})
