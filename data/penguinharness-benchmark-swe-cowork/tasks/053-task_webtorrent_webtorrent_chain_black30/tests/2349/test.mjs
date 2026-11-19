import assert from 'node:assert/strict'
import { makeClient, metadata, ready, destroy, CountingStore, readFile, assertBytes } from '../support/runtime.mjs'
const client = makeClient()
try {
  const data = Buffer.alloc(16389, 91)
  const torrent = await ready(client.add(await metadata(data), { store: CountingStore, storeCacheSlots: 0 }))
  const raw = CountingStore.instances.at(-1)
  async function * first () { yield data.subarray(0, 3); yield data.subarray(3, 16380) }
  async function * second () { yield data.subarray(16380) }
  let callbacks = 0
  await new Promise((resolve, reject) => torrent.load([first(), second()], err => {
    callbacks++
    if (err) reject(err)
    else resolve()
  }))
  assert.equal(callbacks, 1)
  assert.equal(raw.puts, 2)
  assert.equal(raw.closes, 0)
  assertBytes(await readFile(torrent.files[0]), data)
  assert.equal(torrent.done, true)
  await destroy(client)
  assert.equal(raw.closes, 1)
} finally { await destroy(client) }
console.log('async load preserves readable storage until destroy callback')
