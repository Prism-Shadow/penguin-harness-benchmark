import assert from 'node:assert/strict'
import { makeClient, seed, destroy, CountingStore, readFile, tick, assertBytes } from '../support/runtime.mjs'
const client = makeClient()
try {
  const data = Buffer.from('duplicate seed fixture')
  const existing = await seed(client, data, { store: CountingStore })
  const raw = CountingStore.instances.at(-1)
  const writes = raw.puts
  const stores = CountingStore.instances.length
  let calls = 0
  let transient
  await new Promise(resolve => {
    transient = client.seed(data, { store: CountingStore, name: 'fixture.bin', announceList: [] }, torrent => {
      calls++
      assert.equal(torrent, existing)
      assert.equal(torrent.ready, true)
      resolve()
    })
  })
  await tick()
  assert.equal(calls, 1)
  if (transient !== existing) assert.equal(transient.destroyed, true)
  assert.equal(raw.puts, writes)
  assert.equal(CountingStore.instances.length, stores)
  assert.deepEqual(client.torrents, [existing])
  assertBytes(await readFile(existing.files[0]), data)
  const other = await seed(client, Buffer.from('new seed fixture'), { store: CountingStore })
  assert.notEqual(other, existing)
  assert.equal(client.torrents.length, 2)
} finally { await destroy(client) }
console.log('duplicate seed callback, data preservation and transient cleanup passed')
