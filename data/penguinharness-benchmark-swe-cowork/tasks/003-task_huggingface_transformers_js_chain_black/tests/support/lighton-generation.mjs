import assert from 'node:assert/strict';
import {api,ort,i64,tensor,withModel} from './inference.mjs';
import {ocrConfig} from './ocr-config.mjs';
let imageValue=23,visionCalls=0,releases=0;
const session=(inputNames,run)=>({inputNames,config:{kv_cache_dtype:'float32'},run,async release(){releases++;}});
const sessions={
 embed_tokens:session(['input_ids'],async({input_ids})=>({inputs_embeds:ort('float32',Float32Array.from({length:input_ids.data.length*8},(_,i)=>Number(input_ids.data[Math.floor(i/8)])),[...input_ids.dims,8])})),
 vision_encoder:session(['pixel_values'],async({pixel_values})=>{
  visionCalls++;return {image_features:ort('float32',Float32Array.from({length:8},(_,i)=>Number(pixel_values.data[0])+i),[1,1,8])};
 }),
 decoder_model_merged:session(['inputs_embeds','attention_mask','position_ids','past_key_values.0.key','past_key_values.0.value'],async feeds=>{
  const past=feeds['past_key_values.0.key'].dims[2],length=feeds.inputs_embeds.dims[1];
  if(!past)assert.deepEqual(Array.from(feeds.inputs_embeds.data.slice(8,16)),Array.from({length:8},(_,i)=>imageValue+i));
  assert.equal(feeds.attention_mask.dims[1],past+length);
  const next=Number(feeds.inputs_embeds.data[(length-1)*8])+1;
  const logits=new Float32Array(length*128).fill(-100);logits[(length-1)*128+next]=100;
  const total=past+length;
  return {logits:ort('float32',logits,[1,length,128]),'present.0.key':ort('float32',new Float32Array(total*8),[1,1,total,8]),'present.0.value':ort('float32',new Float32Array(total*8),[1,1,total,8])};
 }),
};
await withModel(api.AutoModelForImageTextToText,{...ocrConfig,model_type:'lighton_ocr',text_config:{...ocrConfig.text_config,model_type:'qwen2'}},sessions,async model=>{
 assert.equal(model.constructor,api.LightOnOcrForConditionalGeneration);
 for(const value of [23,47]) {
  imageValue=value;
  const output=await model.generate({input_ids:i64([11,71,12],[1,3]),attention_mask:i64([1,1,1],[1,3]),pixel_values:tensor('float32',new Float32Array([value]),[1,1,1,1]),max_new_tokens:3});
  assert.deepEqual(output.tolist(),[[11n,71n,12n,13n,14n,15n]]);
 }
 assert.equal(visionCalls,2);
});
assert.equal(releases,3);
