import { QueryClient, hydrate } from '../packages/query-core/src/index'
import type { DefaultOptions, HydrateOptions } from '../packages/query-core/src/index'

const defaults: DefaultOptions = {
  hydrate: {
    transformPromise: (promise: Promise<any>): Promise<any> => promise.then((value) => ({ transformed: value })),
    deserializeData: (value: any): any => ({ decoded: value }),
  },
}
const client = new QueryClient({ defaultOptions: defaults })
const overrides: HydrateOptions = {
  defaultOptions: {
    transformPromise: (promise: Promise<any>): Promise<any> => promise.then((value) => [value]),
    deserializeData: (value: any): any => ({ decoded: value }),
  },
}
hydrate(client, { mutations: [], queries: [] }, overrides)
hydrate(client, { mutations: [], queries: [] }, { defaultOptions: {
  transformPromise: (promise: Promise<any>) => promise,
} })
hydrate(client, { mutations: [], queries: [] }, { defaultOptions: {
  deserializeData: (value: any) => value,
} })
