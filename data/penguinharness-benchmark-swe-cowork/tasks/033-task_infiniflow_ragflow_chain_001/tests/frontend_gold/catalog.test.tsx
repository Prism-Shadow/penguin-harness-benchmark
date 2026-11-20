import {act, renderHook, waitFor} from '@testing-library/react';
import {useModelsCatalog, useModelVerify} from '@/pages/user-setting/setting-model/instance-card/models-section/hooks';
import {LLMFactory} from '@/constants/llm';
const mockList=jest.fn(),mockVerify=jest.fn();
jest.mock('@/hooks/use-llm-request',()=>({useListProviderModels:()=>({listProviderModels:mockList}),useVerifyProviderConnection:()=>({verifyProviderConnection:mockVerify})}));
jest.mock('@/services/llm-service',()=>({__esModule:true,default:{}}));
jest.mock('@/pages/user-setting/setting-model/instance-card/available-models',()=>({sortModelTypes:(x:any)=>x}));
jest.mock('@/pages/user-setting/setting-model/instance-card/use-custom-model-fields',()=>({useCustomModelFields:()=>[]}));
beforeEach(()=>{jest.clearAllMocks();mockList.mockResolvedValue({code:0,data:[{name:'model',model_types:['embedding']}]});mockVerify.mockResolvedValue({code:0});});
test('saved Bedrock catalog waits for details and actual key/region; rerender triggers one request',async()=>{
 let creds:any={apiKey:{auth_mode:'bedrock_api_key',bedrock_api_key:'',bedrock_region:''},baseUrl:undefined};
 const resolveCreds=()=>creds;
 const {result,rerender}=renderHook(({loaded,key})=>useModelsCatalog({providerName:LLMFactory.Bedrock,instanceName:'saved',hideActions:false,resolveCreds,instanceModels:[],apiKeyValue:key,baseUrlValue:undefined,instanceDetailsLoaded:loaded}),{initialProps:{loaded:false,key:creds.apiKey}});
 expect(mockList).not.toHaveBeenCalled();
 rerender({loaded:true,key:creds.apiKey});expect(mockList).not.toHaveBeenCalled();
 creds={apiKey:{auth_mode:'bedrock_api_key',bedrock_api_key:'key',bedrock_region:'region'},baseUrl:undefined};
 rerender({loaded:true,key:creds.apiKey});await waitFor(()=>expect(result.current.catalog).toHaveLength(1));
 expect(mockList).toHaveBeenCalledTimes(1);expect(mockList).toHaveBeenCalledWith(expect.objectContaining({api_key:creds.apiKey}));
 rerender({loaded:true,key:{...creds.apiKey}});expect(mockList).toHaveBeenCalledTimes(1);
});
test('URL-based provider fetches when the form gains a URL',async()=>{
 let url='';const resolveCreds=()=>({apiKey:'',baseUrl:url});
 const {result,rerender}=renderHook(({base})=>useModelsCatalog({providerName:LLMFactory.Ollama,instanceName:'saved',hideActions:false,resolveCreds,instanceModels:[],apiKeyValue:'',baseUrlValue:base,instanceDetailsLoaded:true}),{initialProps:{base:''}});
 expect(mockList).not.toHaveBeenCalled();url='http://model.local';rerender({base:url});
 await waitFor(()=>expect(result.current.catalog).toHaveLength(1));expect(mockList).toHaveBeenCalledWith(expect.objectContaining({base_url:url}));
});
test('selected model verification sends its type and retained credentials',async()=>{
 const {result}=renderHook(()=>useModelVerify({providerName:'LocalAI',resolveCreds:()=>({apiKey:'key',baseUrl:'http://models'}),instanceModels:[],instance:{id:'instance'} as any}));
 await act(async()=>{await result.current.handleVerify({name:'embed-small',model_types:['embedding'],max_tokens:512});});
 expect(mockVerify).toHaveBeenCalledWith({provider_name:'LocalAI',api_key:'key',base_url:'http://models',instance_id:'instance',model_info:[{model_name:'embed-small',model_type:['embedding'],max_tokens:512}]});
 expect(result.current.verify['embed-small']).toBe('success');
 mockVerify.mockRejectedValueOnce(new Error('provider unavailable'));
 await act(async()=>{await result.current.handleVerify({name:'embed-small'});});expect(result.current.verify['embed-small']).toBe('error');
});
test('saved Bedrock never fetches restored credentials before instance details are authoritative',async()=>{
 const creds:any={apiKey:{auth_mode:'bedrock_api_key',bedrock_api_key:'restored',bedrock_region:'region'},baseUrl:undefined};
 const {rerender}=renderHook(({loaded})=>useModelsCatalog({providerName:LLMFactory.Bedrock,instanceName:'saved',hideActions:false,resolveCreds:()=>creds,instanceModels:[],apiKeyValue:creds.apiKey,baseUrlValue:undefined,instanceDetailsLoaded:loaded}),{initialProps:{loaded:false}});
 expect(mockList).not.toHaveBeenCalled();rerender({loaded:true});await waitFor(()=>expect(mockList).toHaveBeenCalledTimes(1));
});
