import assert from 'node:assert/strict'
import { makeClient, metadata, ready, destroy, MemoryStore } from '../support/runtime.mjs'
const client = makeClient()
try {
  const empty = client.add(null, { store: MemoryStore })
  assert.equal(empty._hasAllPieces(), true)
  assert.equal(empty._hasNoPieces(), true)
  const torrent = await ready(client.add(await metadata(Buffer.alloc(32768, 7)), { store: MemoryStore }))
  assert.equal(torrent._hasAllPieces(), false)
  assert.equal(torrent._hasNoPieces(), true)
  torrent._markVerified(0)
  assert.equal(torrent._hasAllPieces(), false)
  assert.equal(torrent._hasNoPieces(), false)
  torrent._markVerified(1)
  assert.equal(torrent._hasAllPieces(), true)
  assert.equal(torrent._hasNoPieces(), false)
  torrent._markUnverified(0)
  assert.equal(torrent._hasAllPieces(), false)
  assert.equal(torrent._hasNoPieces(), false)
} finally { await destroy(client) }
console.log('piece predicates cover initialized empty, absent, mixed and complete states')
