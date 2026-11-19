import { checkResource } from '../../environment/resource_contract.mjs';

await checkResource({ chunks: [{ data: 'é', eof: false }],
  headers: { 'Content-Length': '2' }, expected: 'é', offsets: [0] });
await checkResource({ chunks: [{ data: 'é', eof: false }, { data: '漢', eof: false }],
  headers: { 'content-length': '5' }, expected: 'é漢', offsets: [0, 2] });
await checkResource({ chunks: [{ data: '8J8=', base64Encoded: true, eof: false },
  { data: 'mIA=', base64Encoded: true, eof: true }], expected: '😀', offsets: [0, 2] });
await checkResource({ chunks: [{ data: 'YQ==', base64Encoded: true, eof: false },
  { data: 'é', eof: true }], expected: 'aé', offsets: [0, 1] });
await checkResource({ chunks: [{ data: 'valid', eof: true }],
  headers: { 'Content-Length': 'invalid' }, expected: 'valid', offsets: [0] });
