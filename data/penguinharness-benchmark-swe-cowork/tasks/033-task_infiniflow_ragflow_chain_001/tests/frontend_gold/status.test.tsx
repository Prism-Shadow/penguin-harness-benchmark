import React from 'react';
import {renderHook,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {useTraceRunData,useGenerateStatus} from '@/hooks/use-dataset-generate';
import {GenerateType,GenerateStatus} from '@/constants/knowledge';
const mockGet=jest.fn();
jest.mock('@/utils/request',()=>({__esModule:true,default:{get:(...args:any[])=>mockGet(...args)}}));
jest.mock('@/utils/next-request',()=>({__esModule:true,default:{}}));
jest.mock('@/components/ui/message',()=>({__esModule:true,default:{success:()=>{}}}));
jest.mock('@/services/agent-service',()=>({__esModule:true,default:{}}));
jest.mock('react-router',()=>({useParams:()=>({id:'dataset/id'})}));
jest.mock('react-i18next',()=>({useTranslation:()=>({t:(s:string)=>s})}));
beforeEach(()=>{jest.clearAllMocks();(globalThis as any).__API_PROXY_SCHEME__='go';});
test.each([
 ['pending','',0.2,GenerateStatus.Running],['running','retryable write failure',0.5,GenerateStatus.Failed],['completed','',1,GenerateStatus.Completed],['idle','',0,GenerateStatus.Start],
])('real status hook requests Go route and maps %s with independent diagnostic',async(state,error,progress,status)=>{
 mockGet.mockResolvedValue({data:{code:0,data:{state,error,progress,inflight:2,backlog:3,current_phase:'writing',progress_msg:'details'}}});
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
 const wrapper=({children}:any)=><QueryClientProvider client={client}>{children}</QueryClientProvider>;
 const {result,unmount}=renderHook(()=>{const query=useTraceRunData(GenerateType.Artifact);return {query,...useGenerateStatus(query.data)};},{wrapper});
 await waitFor(()=>expect(result.current.query.isSuccess).toBe(true));
 expect(mockGet).toHaveBeenCalledWith('/api/v1/datasets/dataset%2Fid/compilation/status');
 expect(result.current.query.data).toMatchObject({compilationState:state,compilationError:error,inflight:2,backlog:3,currentPhase:'writing'});
 expect(result.current.status).toBe(status);unmount();client.clear();
});
test('authorization business error cannot become idle or successful status',async()=>{
 mockGet.mockResolvedValue({data:{code:403,message:'no authorization'}});
 const client=new QueryClient();const wrapper=({children}:any)=><QueryClientProvider client={client}>{children}</QueryClientProvider>;
 const {result,unmount}=renderHook(()=>useTraceRunData(GenerateType.Artifact),{wrapper});
 await waitFor(()=>expect(result.current.isError).toBe(true),{timeout:5000});
 expect(result.current.data).toBeUndefined();expect(result.current.error?.message).toBe('no authorization');unmount();client.clear();
});
