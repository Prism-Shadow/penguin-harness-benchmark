import assert from 'node:assert/strict'
import { makeClient, seed, readFile, destroy, load, assertBytes } from '../support/runtime.mjs'
const client = makeClient()
try {
  const data = Buffer.from('module composition fixture')
  const torrent = await seed(client, data)
  const File = await load('lib/file.js')
  const Torrent = await load('lib/torrent.js')
  assert.ok(torrent instanceof Torrent)
  assert.ok(torrent.files[0] instanceof File)
  assertBytes(await readFile(torrent.files[0]), data)
  await destroy(client)
  assert.equal(torrent.destroyed, true)
} finally { await destroy(client) }
console.log('ESM client, torrent and file modules compose through actual byte reads')
