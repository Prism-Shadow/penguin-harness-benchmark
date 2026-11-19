import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
export async function runMcpHttp(m) {
  const [exe, ...args] = JSON.parse(process.env.PUERTS_HTTP_HOST);
  const child = spawn(exe, args, {stdio: ['pipe', 'pipe', 'inherit']});
  const lines = createInterface({input: child.stdout});
  let next = 0, failure, openingSession;
  const pending = new Map();
  const begun = [];
  let readyResolve, initializedResolve;
  const initialized = new Promise(resolve => { initializedResolve = resolve; });
  const ready = new Promise(resolve => { readyResolve = resolve; });
  const send = (method, ...args) => new Promise((resolve, reject) => {
    const id = ++next;
    const timer = setTimeout(() => reject(new Error('HTTP bridge acknowledgement deadline: ' + method)), 5000);
    pending.set(id, {resolve, timer}); child.stdin.write(JSON.stringify({id, method, args}) + '\n');
  });
  lines.on('line', line => {
    try {
      const row = JSON.parse(line);
      if (row.kind === 'ready') readyResolve(row.port);
      else if (row.kind === 'module') assert.equal(row.module, 'McpServer/main.mjs', 'production manager loads generated public entry');
      else if (row.kind === 'initialize') m.onInitialize(row.root, bridge, {Invoke: (ok,error) => {send('Ready',ok,error).catch(e=>{failure=e;});}});
      else if (row.kind === 'initialized') { assert.equal(row.ok,true,row.error); initializedResolve(); }
      else if (row.kind === 'shutdown') m.onShutdown();
      else if (row.kind === 'post') m.handleHttpPost(row.context, row.method, row.body, row.session);
      else if (row.kind === 'stream') send('SendGetSseEventForSession', openingSession, JSON.stringify({jsonrpc:'2.0',method:'notifications/probe'}));
      else if (row.kind === 'delete') m.handleHttpDelete(row.session);
      else if (row.kind === 'ack') {const p = pending.get(row.id); clearTimeout(p.timer); pending.delete(row.id); p.resolve(row.result);}
      else throw new Error(row.error);
    } catch (e) { failure = e; }
  });
  const bridge = {};
  for (const name of ['AddSession','RemoveSession','BeginSseStream','SendSseEvent','ClosePostStream','SendGetSseEventForSession','SendJsonResponse','Send202','AddSessionHeaderForContext']) {
    bridge[name] = (...args) => {if (name === 'BeginSseStream') begun.push(args[0]); send(name,...args).catch(error => {failure = error;});};
  }
  async function boundary(promise, label) {
    let timer;
    try {
      return await Promise.race([promise, new Promise((_, reject) => {
        timer=setTimeout(() => reject(new Error(label + ': ' + (failure?.message || 'production callback did not arrive'))), 3500);
      })]);
    } finally { clearTimeout(timer); }
  }
  const ticker = setInterval(() => {send('EditorTick').catch(error=>{failure=error;});}, 10);
  try {
    const port = await boundary(ready, 'manager HTTP listener startup');
    const url = `http://127.0.0.1:${port}/mcp`;
    await boundary(initialized, 'manager module initialization');
    const options = await fetch(url, {method: 'OPTIONS', signal: AbortSignal.timeout(3000)});
    assert.equal(options.status, 204);
    assert.match(options.headers.get('access-control-allow-headers'), /mcp-session-id/i);
    const post = (body, session) => fetch(url, {method:'POST', headers:{'content-type':'application/json', ...(session ? {'mcp-session-id':session} : {})}, body:JSON.stringify(body), signal:AbortSignal.timeout(4000)});
    const init = {jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'socket-test',version:'1'}}};
    const sessions = [];
    for (let n=0;n<2;n++) {
      const res = await post(init); assert.equal(res.status,200);
      const id = res.headers.get('mcp-session-id'); assert.ok(id); sessions.push(id);
      const text = await res.text(); assert.match(text,/serverInfo/); assert.match(text,/data:/);
    }
    assert.notEqual(...sessions);
    openingSession = sessions[0];
    const stream = await fetch(url,{headers:{'mcp-session-id':sessions[0]},signal:AbortSignal.timeout(6000)});
    assert.equal(stream.status,200); const reader = stream.body.getReader(); await reader.read();
    const started = begun.length;
    const hanging = post({jsonrpc:'2.0',id:70,method:'tools/call',params:{name:'evalJsCode',arguments:{code:'async function execute() { return await new Promise(() => {}); }',timeout:3}}},sessions[0]).then(async r => ({status:r.status,body:await r.text()}));
    while (begun.length === started) await new Promise(resolve => setTimeout(resolve,5));
    const removed = await fetch(url,{method:'DELETE',headers:{'mcp-session-id':sessions[0]},signal:AbortSignal.timeout(3000)});
    assert.equal(removed.status,200); await removed.text();
    const pendingClosed = await Promise.race([hanging, new Promise(resolve => setTimeout(() => resolve(null),350))]);
    assert.ok(pendingClosed, 'DELETE closes pending POST without waiting for user code deadline');
    const closed = await reader.read(); assert.equal(closed.done,true,'DELETE closes active session socket');
    const stale = await post({jsonrpc:'2.0',id:2,method:'ping'},sessions[0]); assert.equal(stale.status,404); await stale.text();
    const survivor = await post({jsonrpc:'2.0',id:2,method:'ping'},sessions[1]); assert.equal(survivor.status,200); assert.match(await survivor.text(),/result/);
    openingSession = sessions[1];
    const active = await fetch(url,{headers:{'mcp-session-id':sessions[1]},signal:AbortSignal.timeout(6000)}); const activeReader=active.body.getReader(); await activeReader.read();
    await send('Shutdown');
    assert.equal((await activeReader.read()).done,true,'shutdown closes active streams');
    await assert.rejects(fetch(url,{signal:AbortSignal.timeout(1500)}),'shutdown stops listener');
    const stats = await send('Stats');
    assert.equal(stats.created,stats.disposed); assert.equal(stats.deadTouches,0); assert.equal(stats.initialized,false);
    if (failure) throw failure;
    console.log('production McpHttpServer socket lifecycle passed');
  } finally { clearInterval(ticker); for (const p of pending.values()) clearTimeout(p.timer); child.stdin.end(); child.kill(); lines.close(); }
}
