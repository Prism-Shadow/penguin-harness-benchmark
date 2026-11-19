import { QueryClient, QueryObserver } from '../packages/query-core/src/index'
const client = new QueryClient()
client.fetchQuery({
  queryKey: ['ttl', 7] as const,
  queryFn: async () => 17,
  staleTime: (query) => {
    const value: number | undefined = query.state.data
    const tag: 'ttl' = query.queryKey[0]
    return value === undefined && tag === 'ttl' ? 0 : Infinity
  },
})
new QueryObserver(client, {
  queryKey: ['observer-ttl'] as const,
  queryFn: async () => 'data',
  staleTime: (query) => query.state.data === 'data' ? Infinity : 0,
})
