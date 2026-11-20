import { createSignal, Suspense } from 'solid-js'
import { isServer } from 'solid-js/web'
import { QueryClientProvider, createQuery } from '../src/index'

export const originalKey = ['ssr-original', { id: 7 }]
export const changedKey = ['ssr-changed', { id: 9 }]
export const hash = (key: readonly unknown[]) => `custom:${JSON.stringify(key)}`

export function App(props: any) {
  function Page() {
    const [key, setKey] = createSignal(originalKey)
    const query = createQuery(() => ({
      queryKey: key(), queryKeyHashFn: hash,
      queryFn: props.queryFn, retry: false,
      staleTime: Infinity,
      enabled: isServer,
    }))
    // Options change after resource creation, before Solid's hydration microtask.
    if (!isServer && props.changeKey) setKey(changedKey)
    return <div id="query-value">{query.data?.value ?? 'pending'}</div>
  }
  return <QueryClientProvider client={props.client}>
    <Suspense fallback={<div>loading</div>}><Page /></Suspense>
  </QueryClientProvider>
}
