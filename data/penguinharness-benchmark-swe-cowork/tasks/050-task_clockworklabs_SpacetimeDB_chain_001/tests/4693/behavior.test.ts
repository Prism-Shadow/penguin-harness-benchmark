import { describe, expect, it } from 'vitest';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = process.env.REPO_DIR ?? process.cwd();
const load = (file: string) => import(pathToFileURL(path.join(root, file)).href);

describe('timestamp query values', () => {
  it('compares timestamps by microseconds and renders RFC3339 literals', async () => {
    const { Timestamp } = await load('src/lib/timestamp.ts');
    const { eq, evaluate, toString } = await load('src/lib/filter.ts');
    const { ModuleContext, tablesToSchema } = await load('src/lib/schema.ts');
    const { table } = await load('src/lib/table.ts');
    const { t } = await load('src/lib/type_builders.ts');
    const timestamp = Timestamp.fromDate(new Date('2024-01-01T00:00:00.123Z'));
    expect(evaluate(eq('createdAt', timestamp), { createdAt: timestamp })).toBe(true);
    expect(evaluate(eq('createdAt', timestamp), { createdAt: new Timestamp(timestamp.microsSinceUnixEpoch + 1n) })).toBe(false);
    const schema: any = tablesToSchema(new ModuleContext(), { people: table({ name: 'people' }, { createdAt: t.timestamp() }) });
    expect(toString(schema.tables.people, eq('createdAt', timestamp))).toBe("createdAt = '2024-01-01T00:00:00.123000Z'");
  });
});
