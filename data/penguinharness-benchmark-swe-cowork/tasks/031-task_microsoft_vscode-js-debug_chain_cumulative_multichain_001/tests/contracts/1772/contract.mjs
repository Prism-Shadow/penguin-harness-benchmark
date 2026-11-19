import { checkResource } from '../../environment/resource_contract.mjs';

await checkResource({ chunks: [{ data: 'hello', eof: false }],
  headers: { 'Content-Length': '5' }, expected: 'hello', offsets: [0] });
await checkResource({ chunks: [{ data: 'legacy caller', eof: true }],
  expected: 'legacy caller', offsets: [0], legacy: true });
await checkResource({ chunks: [{ data: 'without length', eof: true }],
  expected: 'without length', offsets: [0] });
await checkResource({ directStatus: 200, expected: 'direct-body' });
await checkResource({ noCdp: true });
await checkResource({ networkFailure: true });
await checkResource({ noResource: true });
await checkResource({ noStream: true });
await checkResource({ success: false, resourceStatus: 403 });
await checkResource({ chunks: [undefined], offsets: [0] });
await checkResource({ chunks: [new Error('read rejected')], offsets: [0] });
await checkResource({ chunks: [{ data: '', eof: false }], offsets: [0] });
await checkResource({ chunks: [{ data: '', eof: true }], expected: '', offsets: [0] });
await checkResource({ headers: { 'Content-Length': '0' }, expected: '' });
await checkResource({ chunks: [{ data: 'body', eof: true }],
  expected: 'body', closeFailure: true, offsets: [0] });
