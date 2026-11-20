import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { load } from './load.mjs';
export async function nativeModelBehavior(api, { failureRecovery = false } = {}) {
// A complete ONNX Add graph (IR 8, opset 13), encoded from its public
// protobuf schema. This tiny real model requires no downloaded weights.
const vint = (n) => { const a=[];do {let b=n&127;n>>>=7;a.push(b|(n?128:0));}while(n);return Buffer.from(a); };
const field = (n, value) => typeof value === 'number'
    ? Buffer.concat([vint(n*8),vint(value)])
    : Buffer.concat([vint(n*8+2),vint(Buffer.byteLength(value)),Buffer.from(value)]);
const join=(...a)=>Buffer.concat(a);
const info=(name)=>field(2,field(1,join(field(1,7),field(2,join(field(1,field(1,1)),field(1,field(1,3)))))));
const value=(name)=>join(field(1,name),info(name));
const offset=join(field(1,1),field(1,3),field(2,7),field(7,10),field(7,20),field(7,30),field(8,'offset'));
const graph=join(field(1,join(field(1,'input_ids'),field(1,'offset'),field(2,'last_hidden_state'),field(4,'Add'))),
    field(2,'offline_add'),field(5,offset),field(11,value('input_ids')),field(12,value('last_hidden_state')));
const model=join(field(1,8),field(2,'behavior-test'),field(7,graph),field(8,field(2,13)));
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'real-onnx-'));
const old=api.env.allowRemoteModels;
try {
    api.env.allowRemoteModels=false;
    await fs.mkdir(path.join(dir,'onnx'));
    await fs.writeFile(path.join(dir,'config.json'),JSON.stringify({model_type:'bert',architectures:['BertModel'],hidden_size:3,num_hidden_layers:1,num_attention_heads:1}));
    await fs.writeFile(path.join(dir,'onnx/model.onnx'),model);
    if (failureRecovery) {
        const bad = path.join(dir, 'broken');
        await fs.mkdir(path.join(bad, 'onnx'), {recursive:true});
        await fs.copyFile(path.join(dir, 'config.json'), path.join(bad, 'config.json'));
        await fs.writeFile(path.join(bad, 'onnx/model.onnx'), new Uint8Array([1,2,3]));
        await assert.rejects(api.AutoModel.from_pretrained(bad,{dtype:'fp32',device:'cpu',local_files_only:true}));
    }
    let loaded;
    await assert.doesNotReject(async () => {
        loaded=await api.AutoModel.from_pretrained(dir,{dtype:'fp32',device:'cpu',local_files_only:true});
    }, 'a failed model load must not poison a later model load');
    try {
        for(const values of [[1n,7n,3n],[8n,2n,5n]]) {
            const result=await loaded({input_ids:new api.Tensor('int64',BigInt64Array.from(values),[1,3])});
            assert.deepEqual(result.last_hidden_state.tolist(),[values.map((x,i)=>x+BigInt((i+1)*10))]);
        }
        await assert.rejects(loaded({}),/Missing|missing/);
        if (failureRecovery) {
            await assert.rejects(loaded({input_ids:new api.Tensor('int64',BigInt64Array.from([1n,2n]),[1,2])}));
            await assert.doesNotReject(async () => {
                const recovered=await loaded({input_ids:new api.Tensor('int64',BigInt64Array.from([1n,2n,3n]),[1,3])});
                assert.deepEqual(recovered.last_hidden_state.tolist(),[[11n,22n,33n]]);
            }, 'a failed inference must not poison a later inference');
        }
    } finally { await loaded.dispose(); }
} finally {api.env.allowRemoteModels=old;await fs.rm(dir,{recursive:true,force:true});}

}
await nativeModelBehavior(await load('packages/transformers/src/transformers.js'));
