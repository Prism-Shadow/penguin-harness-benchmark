import assert from 'node:assert/strict'
import { makeClient, metadata, ready, destroy, MemoryStore } from '../support/runtime.mjs'
const client = makeClient()
try {
  const torrent = await ready(client.add(await metadata(Buffer.from('completion fixture')), { store: MemoryStore }))
  let events = 0
  torrent.on('done', () => { events++ })
  torrent._checkDone()
  assert.equal(torrent.done, false)
  torrent._markVerified(0)
  for (let repeat = 0; repeat < 4; repeat++) {
    torrent._checkDone()
    assert.equal(torrent.done, true)
    assert.equal(events, 1)
  }
  torrent._markUnverified(0)
  torrent.select(0, 0)
  torrent._checkDone()
  assert.equal(torrent.done, false)
  torrent._markVerified(0)
  torrent._checkDone()
  torrent._checkDone()
  assert.equal(torrent.done, true)
  assert.equal(events, 2)
} finally { await destroy(client) }
console.log('completion remains stable and emits once per incomplete-to-complete transition')
