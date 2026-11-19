import { requestChatCompletionStream, parseCompletionEventStream } from '@/services/chat-completion-stream';
import { runChatCompletionStream } from '@/pages/next-chats/chat-stream/run-stream';
import { useChatStreamStore as store } from '@/pages/next-chats/chat-stream/store';

jest.mock('@/utils/authorization-util', () => ({getAuthorization:()=> 'test-token'}));
const question = (id='q') => ({id, role:'user', content:'question'} as any);
function source() {
 let controller: ReadableStreamDefaultController<Uint8Array>;
 const cancel = jest.fn();
 const stream = new ReadableStream<Uint8Array>({start(c){controller=c;}, cancel});
 return {response:new Response(stream, {headers:{'content-type':'text/event-stream'}}), cancel,
  send:(data:any)=>controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(data)}\n\n`)),
  close:()=>controller.close(), error:(e:Error)=>controller.error(e)};
}
const tick = ()=>new Promise(r=>setTimeout(r,10));
beforeEach(()=>{store.setState({sessions:{}});global.fetch=jest.fn();});

test('production request preserves agent mode, parameters, and plain numeric reasoning', async()=>{
 (fetch as jest.Mock).mockResolvedValue(new Response());
 const controller=new AbortController();
 await requestChatCompletionStream({chatId:'chat',sessionId:'session',messages:[question()],agentMode:'agentic',enableThinking:'3',enableInternet:true,llmSetting:{temperature:0,max_tokens:512,thinking:'disabled'}},controller.signal);
 const [url, options]=(fetch as jest.Mock).mock.calls[0];
 expect(url).toContain('completions');
 expect(options.signal).toBe(controller.signal);
 expect(JSON.parse(options.body)).toMatchObject({session_id:'session',chat_id:'chat',reasoning:0,agent_mode:'agentic',internet:true,temperature:0,max_tokens:512,thinking:'disabled',pass_all_history_messages:true});
 await requestChatCompletionStream({sessionId:'s',messages:[],enableThinking:'2'},controller.signal);
 expect(JSON.parse((fetch as jest.Mock).mock.calls[1][1].body)).toMatchObject({reasoning:2});
});

test('two production streams isolate sessions and reject duplicate sends and stale hydration', async()=>{
 const a=source(),b=source();(fetch as jest.Mock).mockResolvedValueOnce(a.response).mockResolvedValueOnce(b.response);
 const pa=runChatCompletionStream({conversationId:'A',messages:[question('a')]}),pb=runChatCompletionStream({conversationId:'B',messages:[question('b')]});
 expect(await runChatCompletionStream({conversationId:'A',messages:[question('duplicate')]})).toEqual({ok:false,aborted:false});
 store.getState().setMessages('A',[]);
 a.send({code:0,data:{answer:'alpha',reference:{chunks:['source-a']}}});b.send({code:0,data:{answer:'beta'}});
 await tick();a.send({code:0,data:{answer:'alpha complete'}});b.send({code:0,data:{answer:' tail'}});a.close();b.close();
 expect(await pa).toEqual({ok:true,aborted:false});expect(await pb).toEqual({ok:true,aborted:false});
 expect(fetch).toHaveBeenCalledTimes(2);
 expect(store.getState().sessions.A.messages.at(-1)).toMatchObject({content:'alpha complete',reference:{chunks:['source-a']}});
 expect(store.getState().sessions.B.messages.at(-1)?.content).toBe('beta tail');
 expect(store.getState().sessions.A.controller).toBeUndefined();
});

test.each(['http','business','json','empty','read'])('failure %s never reports successful stream and releases session',async(kind)=>{
 const s=source();let response=s.response;
 if(kind==='http') response=new Response('unavailable',{status:503});
 if(kind==='json') response=new Response('{"code":500,"message":"rejected"}',{headers:{'content-type':'application/json'}});
 (fetch as jest.Mock).mockResolvedValue(response);
 const result=runChatCompletionStream({conversationId:'A',messages:[question()]});
 if(kind==='business') s.send({code:500,message:'rejected'});
 if(kind==='read') {await tick();s.error(new Error('broken transport'));} else if(kind==='empty') s.close();
 expect(await result).toEqual({ok:false,aborted:false});
 expect(store.getState().sessions.A.controller).toBeUndefined();
 if(kind==='business') expect(s.cancel).toHaveBeenCalledTimes(1);
});

test('abort preserves partial answer and detaches external signal', async()=>{
 const s=source(),external=new AbortController();
 const remove=jest.spyOn(external.signal,'removeEventListener');
 (fetch as jest.Mock).mockImplementation(async(_url, options)=>{options.signal.addEventListener('abort',()=>s.error(new DOMException('stopped','AbortError')));return s.response;});
 const result=runChatCompletionStream({conversationId:'A',messages:[question()],signal:external.signal});
 s.send({code:0,data:{answer:'partial'}});await tick();external.abort();
 expect(await result).toEqual({ok:true,aborted:true});
 expect(store.getState().sessions.A.messages.at(-1)?.content).toBe('partial');
 expect(store.getState().sessions.A.controller).toBeUndefined();expect(remove).toHaveBeenCalledWith('abort',expect.any(Function));
});

test('parser releases a partially consumed stream on generator return',async()=>{
 const s=source();s.send({code:0,data:{answer:'one'}});
 const parser=parseCompletionEventStream(s.response);
 expect((await parser.next()).value).toEqual({answer:'one'});await parser.return(undefined);
 expect(s.cancel).toHaveBeenCalledTimes(1);
});
