import { describe, expect, it } from 'vitest';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.env.REPO_DIR ?? process.cwd();
const load = (file: string) => import(pathToFileURL(path.join(root, file)).href);

describe('server function registration compatibility', () => {
  it('keeps reducer exports callable after registration', async () => {
    const { SchemaInner, Schema } = await load('src/server/schema.ts');
    const { ModuleContext, tablesToSchema } = await load('src/lib/schema.ts');
    const { table } = await load('src/lib/table.ts');
    const { t } = await load('src/lib/type_builders.ts');
    const { moduleHooks } = await import('spacetime:sys@2.0');
    let called = false;
    const ctx = new SchemaInner((inner: any) => tablesToSchema(inner, { items: table({ name: 'items' }, { id: t.u32() }) }));
    const schema: any = new Schema(ctx);
    const reducer = schema.reducer((reducerCtx: any) => { called = !!reducerCtx.db.items; });
    const hooks: any = schema[moduleHooks]({ run: reducer });
    hooks.__call_reducer__(0, 0n, 0n, 0n, new DataView(new ArrayBuffer(0)));
    expect(called).toBe(true);
  });
});
