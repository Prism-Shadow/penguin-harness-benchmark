import { renderToStringAsync, generateHydrationScript } from 'solid-js/web'
import { QueryClient } from '../src/index'
import { App } from './hydration-app'
export async function render() {
  const client = new QueryClient()
  let calls = 0
  const html = await renderToStringAsync(() => <App client={client} queryFn={async () => {
    calls++
    await Promise.resolve()
    return { value: 71 }
  }} />)
  client.clear()
  return { html, script: generateHydrationScript(), calls }
}
