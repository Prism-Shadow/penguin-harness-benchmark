import {act,renderHook,waitFor} from '@testing-library/react';
import {useSendMessage} from '@/pages/next-chats/hooks/use-send-chat-message';
import {useHandleClickConversationCard} from '@/pages/next-chats/hooks/use-click-card';
import {useChatStreamStore as store} from '@/pages/next-chats/chat-stream/store';
const mockCreate=jest.fn(),mockRoute=jest.fn(),mockError=jest.fn();
let mockConversation='A';
let mockRegenerateArgs:any;
jest.mock('@/utils/authorization-util',()=>({__esModule:true,default:{getThinkingLevel:()=> 'agentic'},getAuthorization:()=> 'token'}));
jest.mock('@/components/ui/message',()=>({__esModule:true,default:{error:(...a:any[])=>mockError(...a)}}));
jest.mock('@/hooks/use-chat-request',()=>({useGetChatSearchParams:()=>({conversationId:mockConversation,isNew:''}),useFetchChat:()=>({data:{llm_setting:{temperature:0}}})}));
jest.mock('react-router',()=>({useParams:()=>({id:'chat'})}));
jest.mock('react-i18next',()=>({useTranslation:()=>({t:(s:string)=>s})}));
jest.mock('@/pages/next-chats/hooks/use-chat-url',()=>({useCreateConversationBeforeSendMessage:()=>({createConversationBeforeSendMessage:mockCreate}),useChatUrlParams:()=>({setConversationBoth:mockRoute})}));
jest.mock('@/pages/next-chats/hooks/use-select-conversation-list',()=>({useFindPrologueFromDialogList:()=>''}));
jest.mock('@/pages/next-chats/hooks/use-upload-file',()=>({useUploadFile:()=>({files:[],clearFiles:()=>{}})}));
jest.mock('@/hooks/logic-hooks',()=>{
 const React=require('react');
 return {
  useHandleMessageInputChange:()=>{const [value,setValue]=React.useState('');return {value,setValue,handleInputChange:()=>{}};},
  useScrollToBottom:()=>({scrollRef:React.useRef(null)}),
  useRegenerateMessage:(args:any)=>{mockRegenerateArgs=args;return {regenerateMessage:()=>{}};},
 };
});
let output: ReadableStreamDefaultController<Uint8Array>;
function response() {return new Response(new ReadableStream({start(c){output=c;}}),{headers:{'content-type':'text/event-stream'}});}
function finish(text='answer') {output.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({code:0,data:{answer:text}})}\n\n`));output.close();}
beforeEach(()=>{jest.clearAllMocks();mockConversation='A';store.setState({sessions:{}});global.fetch=jest.fn().mockResolvedValue(response());mockCreate.mockResolvedValue({targetConversationId:'A',currentMessages:[]});});
test('real send hook creates once, sends once and preserves running session across navigation/unmount',async()=>{
 const control=new AbortController();const {result,rerender,unmount}=renderHook(()=>useSendMessage(control));
 act(()=>result.current.setValue('Ask once'));
 await act(async()=>{await Promise.all([result.current.handlePressEnter({agentMode:'smart-reasoning',enableThinking:'agentic'}),result.current.handlePressEnter({})]);});
 expect(mockCreate).toHaveBeenCalledTimes(1);expect(fetch).toHaveBeenCalledTimes(1);
 const body=JSON.parse((fetch as jest.Mock).mock.calls[0][1].body);
 expect(body.messages).toHaveLength(1);expect(body).toMatchObject({agent_mode:'smart-reasoning',reasoning:0,temperature:0});
 mockConversation='B';rerender();expect(result.current.sendLoading).toBe(false);expect(result.current.derivedMessages).toEqual([]);
 unmount();finish();await waitFor(()=>expect(store.getState().sessions.A.controller).toBeUndefined());
 expect(store.getState().sessions.A.messages.at(-1)?.content).toBe('answer');expect(store.getState().sessions.B).toBeUndefined();
});
test('real resend callback honors explicitly empty history and retained smart-reasoning options',async()=>{
 store.getState().setMessages('A',[{id:'old',role:'user',content:'stale'} as any]);
 renderHook(()=>useSendMessage(new AbortController()));
 let promise:Promise<void>;
 act(()=>{promise=mockRegenerateArgs.sendMessage({message:{id:'first',role:'user',content:'first'},messages:[]});});
 expect(JSON.parse((fetch as jest.Mock).mock.calls[0][1].body).messages).toEqual([{id:'first',role:'user',content:'first'}]);
 await act(async()=>{finish();await promise;});
});
test('failure during another conversation restores text only when original session is selected',async()=>{
 let resolve:(r:Response)=>void;(fetch as jest.Mock).mockImplementation(()=>new Promise(r=>{resolve=r;}));
 const {result,rerender}=renderHook(()=>useSendMessage(new AbortController()));
 act(()=>result.current.setValue('recover me'));await act(async()=>{await result.current.handlePressEnter({});});
 mockConversation='B';rerender();act(()=>result.current.setValue('B draft'));
 await act(async()=>{resolve(new Response('unavailable',{status:503}));});
 expect(result.current.value).toBe('B draft');expect(store.getState().sessions.A.failedText).toBe('recover me');
 expect(store.getState().sessions.A.messages).toEqual([]);
 mockConversation='A';rerender();await waitFor(()=>expect(result.current.value).toBe('recover me'));expect(store.getState().sessions.A.failedText).toBeUndefined();
});
test('conversation click preserves existing stream and stop affects only selected session',()=>{
 const a=new AbortController(),b=new AbortController();store.getState().beginStream('A',a,[]);store.getState().beginStream('B',b,[]);
 const {result,rerender}=renderHook(useHandleClickConversationCard);
 act(()=>result.current.handleConversationCardClick('B',false));expect(a.signal.aborted).toBe(false);expect(b.signal.aborted).toBe(false);expect(mockRoute).toHaveBeenCalledWith('B','');
 mockConversation='B';rerender();act(()=>result.current.stopOutputMessage());expect(b.signal.aborted).toBe(true);expect(a.signal.aborted).toBe(false);
});
