import { describe, expect, it } from 'vitest';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.env.REPO_DIR ?? process.cwd();
const load = (file: string) => import(pathToFileURL(path.join(root, file)).href);

describe('SDK connection compatibility', () => {
  it('continues to expose a stable connection identifier', async () => {
    const { ConnectionId } = await load('src/lib/connection_id.ts');
    const id = ConnectionId.random();
    expect(ConnectionId.fromString(id.toHexString()).toHexString()).toBe(id.toHexString());
  });
});
