import { pathToFileURL } from 'node:url';
const write = process.stdout.write.bind(process.stdout);
const target = process.argv[2];
const nonce = process.env.COWORK_SCRIPT_NONCE;
process.argv = [process.execPath, target, ...process.argv.slice(3)];
await import(pathToFileURL(target).href);
write(`COWORK_SCRIPT_DONE=${nonce}\n`);
