import assert from 'node:assert/strict';
import {api,ort,i64,withModel} from './inference.mjs';
const config={model_type:'qwen3_5',image_token_id:71,vision_config:{spatial_merge_size:2},text_config:{
    model_type:'qwen3_5_text',layer_types:['full_attention','linear_attention','full_attention'],num_hidden_layers:3,
    num_attention_heads:8,num_key_value_heads:2,hidden_size:64,head_dim:8,
    linear_num_value_heads:4,linear_num_key_heads:2,linear_key_head_dim:4,linear_value_head_dim:4,linear_conv_kernel_dim:3,
}};
let releases=0,step=0,failed=false;
const session=(inputNames,run)=>({inputNames,config:{kv_cache_dtype:'float32'},run,async release(){releases++;}});
const inputs=['inputs_embeds','attention_mask','position_ids','past_key_values.0.key','past_key_values.0.value','past_conv.1','past_recurrent.1','past_key_values.2.key','past_key_values.2.value'];
const sessions={
    embed_tokens:session(['input_ids'],async({input_ids})=>({inputs_embeds:ort('float32',Float32Array.from({length:input_ids.data.length*64},(_,i)=>Number(input_ids.data[Math.floor(i/64)])),[...input_ids.dims,64])})),
    decoder_model_merged:session(inputs,async(feeds)=>{
        if(failed){failed=false;throw new Error('hybrid inference failure');}
        const past=feeds['past_key_values.0.key'].dims[2],length=feeds.inputs_embeds.dims[1];
        assert.deepEqual(feeds['past_conv.1'].dims,[1,32,3]);
        assert.deepEqual(feeds['past_recurrent.1'].dims,[1,4,4,4]);
        const expected=past?past+10:0;
        for(const name of ['past_conv.1','past_recurrent.1'])assert.ok(Array.from(feeds[name].data).every(x=>x===expected),'linear state progresses and resets between requests');
        for(const name of ['past_key_values.0.key','past_key_values.2.value'])assert.deepEqual(feeds[name].dims,[1,2,past,8]);
        assert.equal(feeds.attention_mask.dims[1],past+length);
        const logits=new Float32Array(length*128).fill(-100);
        logits[(length-1)*128+Number(feeds.inputs_embeds.data[(length-1)*64])+1]=100;
        const total=past+length;
        const result={logits:ort('float32',logits,[1,length,128]),
            'present_conv.1':ort('float32',new Float32Array(96).fill(total+10),[1,32,3]),
            'present_recurrent.1':ort('float32',new Float32Array(64).fill(total+10),[1,4,4,4])};
        for(const layer of [0,2])for(const part of ['key','value'])result[`present.${layer}.${part}`]=ort('float32',new Float32Array(2*total*8).fill(total),[1,2,total,8]);
        step++;return result;
    }),
};
await withModel(api.AutoModelForCausalLM,config,sessions,async model=>{
    for(const values of [[3,7],[13,14]]) {
        const result=await model.generate({input_ids:i64(values,[1,2]),attention_mask:i64([1,1],[1,2]),max_new_tokens:3});
        assert.deepEqual(result.tolist(),[[...values,values[1]+1,values[1]+2,values[1]+3].map(BigInt)]);
    }
    failed=true;
    await assert.rejects(model.generate({input_ids:i64([1,2],[1,2]),attention_mask:i64([1,1],[1,2]),max_new_tokens:1}),/hybrid inference failure/);
    const result=await model.generate({input_ids:i64([1,2],[1,2]),attention_mask:i64([1,1],[1,2]),max_new_tokens:2});
    assert.deepEqual(result.tolist(),[[1n,2n,3n,4n]]);
});
assert.equal(step,8);assert.equal(releases,2);
