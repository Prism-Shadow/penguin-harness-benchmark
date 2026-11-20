const { createRequire } = require('node:module');
const path = require('node:path');
const repository = process.argv[2];
const client = process.argv[3];
const resolver = createRequire(path.join(repository, 'src/Web/ClientApp/package.json'));
const esbuild = resolver('esbuild');
const angular = client === 'ClientApp';
const fs = require('node:fs');
const clientRoot = path.join(repository, 'src/Web', client);
const configurations = [path.join(clientRoot, 'nswag.json'), path.join(repository, 'src/Web', angular ? 'config.nswag' : 'config-react.nswag')];
const configurationPath = configurations.find(p => fs.existsSync(p));
if (!configurationPath) throw new Error('Configured TypeScript client generator is missing');
const configuration = JSON.parse(fs.readFileSync(configurationPath, 'utf8'));
const generator = configuration.codeGenerators.openApiToTypeScriptClient;
const source = path.relative(clientRoot, path.resolve(path.dirname(configurationPath), generator.output)).split(path.sep).join('/');
const imports = angular ? `import '@angular/compiler';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { createApplication } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';` : '';
const construction = angular ? 'createApplication({ providers: [provideHttpClient()] }).then(app => new TodoListsClient(app.injector.get(HttpClient), location.origin))' : 'Promise.resolve(new TodoListsClient(location.origin))';
const invoke = callArguments => angular ? `firstValueFrom(client.getTodoLists(${callArguments}))` : `client.getTodoLists(${callArguments})`;
esbuild.build({
  stdin: {
    contents: `${imports}
import { TodoListsClient } from './${source}';
const ready = ${construction};
window.qualityTodosDefault = () => ready.then(client => ${invoke('')});
window.qualityTodosPage = (number, size) => ready.then(client => ${invoke('number, size')});`,
    resolveDir: path.join(repository, 'src/Web', client),
    loader: 'ts'
  },
  bundle: true,
  platform: 'browser',
  format: 'iife',
  tsconfigRaw: { compilerOptions: { experimentalDecorators: true } },
  outfile: process.argv[4]
}).catch(error => { console.error(error); process.exitCode = 3; });
