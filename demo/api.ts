import defaults from './policy.json'
type Row=Record<string,any>
const now=()=>new Date().toISOString()
const id=()=>crypto.randomUUID()
const session={admin:true,can_edit:true,role:'Demo administrator'}
let signed=false
const settings:Row={admin:true,can_run:true,accounts:[],policy:{...defaults},runs:[],digests:[],versions:[],usage:{},credentials:{},connections:{},revision:1}
const projects:Row[]=[{id:'sample',name:'Client portal delivery',client:'Example client',created:now(),sources:1,drafts:1}]
const records=new Map<string,Row>()
function workspace(pid:string){
 if(!records.has(pid))records.set(pid,{sources:[],messages:[],plans:[],audit:[],actions:[],team:[],links:[],events:[],reviews:[],reports:[],rule:{frequency:'Off',weekday:0,hour:9,zone:'Asia/Karachi',audience:'CEO',heading:'Project progress report',recipient:''}})
 return records.get(pid)!
}
const w=workspace('sample')
w.sources.push({id:'scope',family:'scope',version:1,state:'approved',category:'Work scope',title:'Client portal agreement',description:'Sample scope for this demonstration.',origin:'Demo client',passages:[{id:'scope.1',body:'Deliver a customer sign-in page and an approval queue. QA must verify both flows.'}]})
w.plans.push({id:'plan',created:now(),state:'draft',content:'Milestone 1 · Customer sign-in\nDeliverable: sign-in form. Acceptance: approved users can enter. Estimate: 6 hours plus 2 hours QA.\nMilestone 2 · Approval queue\nDepends on sign-in. Confirm team capacity before setting dates.'})
w.team.push({id:'person',name:'Demo engineer',role:'Developer',skills:'React and QA',hours:6})
w.actions.push({id:'draft',status:'draft',revision:1,target:'Sample workspace',payload:{kind:'Jira issue',title:'Implement sign-in',destination:'DEMO',body:'Example approval record. No remote publication.'}})
export async function api(path:string,method='GET',body?:any):Promise<any>{
 const [route,query]=path.split('?')
 const f=body instanceof FormData?Object.fromEntries(body):body||{}
 if(route==='health')return {database:'offline'}
 if(route==='login'){signed=true;return {}}
 if(route==='logout'){signed=false;return {}}
 if(!signed)throw Error('Please sign in to the offline demonstration.')
 if(route==='session')return session
 if(route==='projects'){
  if(method==='GET')return projects.slice()
  const p={...f,id:id(),created:now(),sources:0,drafts:0};projects.push(p);return p
 }
 if(route==='agents/pm-ai-es')return structuredClone(settings)
 if(route==='agents/pm-ai-es/settings'){settings.policy=f.policy;settings.revision++;return {}}
 if(route.startsWith('connections/')||route.includes('/credentials/'))throw Error('Offline demonstration. Configure and test credentials in the local application.')
 const [,pid,op,key,step]=route.split('/')
 if(!projects.some(p=>p.id===pid))throw Error('Select a demo project.')
 const w=workspace(pid),p=projects.find(p=>p.id===pid)!
 if(!op){if(method==='PATCH'){Object.assign(p,{name:f.name,client:f.client,profile:{expertise:f.expertise}});return p}if(method==='DELETE'&&new URLSearchParams(query).get('confirm')===p.name){projects.splice(projects.indexOf(p),1);return {}}}
 if(op==='chats'){
  w.threads??=[]
  if(key==='context')return {eligible:w.sources.length,unready:0,approved_only:false}
  if(!key&&method==='POST'){const t={id:id(),title:f.title,created:now(),updated:now(),preview:'',messages:[],revision:0};w.threads.unshift(t);return t}
  if(!key)return w.threads.filter((t:Row)=>!t.archived&&[t.title,...t.messages.map((m:Row)=>m.body)].join(' ').toLowerCase().includes((new URLSearchParams(query).get('q')||'').toLowerCase()))
  const t=w.threads.find((t:Row)=>t.id===key);if(!t)throw Error('Sample chat unavailable.')
  if(method==='PATCH')Object.assign(t,f)
  if(step==='turn'){
   if(f.respond)throw Error('Connect a model in the installed application to generate a reply.')
   await api('projects/'+pid+'/messages','POST',f)
   t.messages.push({id:id(),role:'user',body:f.body,files:[],citations:[]});t.updated=now();t.preview=f.body.slice(0,160);t.revision++;if(t.title==='New chat')t.title=f.body.slice(0,70)
  }else if(step)throw Error('This action needs the installed application.')
  return structuredClone(t)
 }
 if(op==='workspace')return structuredClone(w)
 if(op==='delivery')return {team:w.team,links:w.links,events:w.events}
 if(op==='team'){w.team.push({...f,id:id()});return {}}
 if(op==='search'){const q=new URLSearchParams(query).get('q')?.toLowerCase()||'';return w.sources.flatMap((s:Row)=>s.passages.map((v:Row)=>({...s,...v}))).filter((s:Row)=>s.body.toLowerCase().includes(q))}
 if(op==='files'||op==='chat-import'||(op==='messages'&&!f.respond)){
  const file=f.file as File|undefined;if(file&&file.size>1048576)throw Error('Use a small sample text file under 1 MiB in the demo.')
  const text=file&&/\.(txt|json|md|csv)$/i.test(file.name)?await file.text():f.body||''
  const sid=id();w.sources.push({id:sid,family:sid,title:f.title||file?.name||text.slice(0,60),description:f.description||'',state:'draft',category:f.category||'Conversation',origin:'Demo',version:1,passages:text?[{id:sid+'.1',body:text}]:[]});p.sources=w.sources.length;return {indexed:!!text}
 }
 if(op==='sources'){const s=w.sources.find((v:Row)=>v.id===key);if(!s)throw Error('Sample source unavailable.');if(method==='PATCH')Object.assign(s,f);if(step==='approve')s.state='approved';return structuredClone(s)}
 if(op==='messages'||op==='agent')throw Error('No AI provider runs in the offline demonstration. Use Response OFF to save a sample note.')
 if(op==='plans'&&key&&!step){Object.assign(w.plans.find((v:Row)=>v.id===key),{content:f.content,state:f.decision});return {}}
 if(op==='report-rule'){if(method==='PUT')w.rule=f;return {...w.rule}}
 if(op==='report-drafts'){if(method==='GET')return w.reports.slice();if(key){const r=w.reports.find((x:Row)=>x.id===key);r.body=f.body;r.revision++}else w.reports.push({id:id(),period_start:f.start,period_end:f.end,audience:f.audience,body:'Sample report · No external activity imported.',revision:1});return {}}
 if(op==='conversation-feedback'){
  w.conversationFeedback??=[]
  if(!key&&method==='GET')return structuredClone(w.conversationFeedback)
  if(!key){
   const thread=w.threads?.find((t:Row)=>t.id===f.thread_id)
   const selected=thread?.messages.filter((m:Row)=>f.entire||f.message_ids.includes(m.id))
   if(!selected?.length)throw Error('Select messages from a saved conversation.')
   const item={id:id(),pid,thread_id:f.thread_id,message_ids:selected.map((m:Row)=>m.id),category:f.category,correction:f.body,policy_text:f.body,edit_version:1,status:'draft',applied:{}}
   w.conversationFeedback.unshift(item);return {id:item.id}
  }
  const item=w.conversationFeedback.find((r:Row)=>r.id===key)
  if(!item)throw Error('Feedback unavailable.')
  if(step==='evidence')return {messages:w.threads.find((t:Row)=>t.id===item.thread_id).messages.filter((m:Row)=>item.message_ids.includes(m.id)),versions:[{version:1,status:'draft',body:item.correction}]}
  throw Error('Analysis and approval require the installed application.')
 }
 if(op==='feedback'){w.reviews.push({id:id(),category:f.category,correction:f.body,evidence:['sample',f.target],policy_text:'Cross-check the answer against approved project sources.',status:'draft'});return {}}
 if(op==='improvements'){if(key){const r=w.reviews.find((x:Row)=>x.id===key);Object.assign(r,{status:f.approve?'approved':'rejected',evaluation:f.evaluation})}return w.reviews.slice()}
 if(op==='actions'){if(method==='GET')return w.actions.slice();if(!key)w.actions.push({id:id(),revision:1,status:'draft',target:'Offline demo',payload:f});else if(step==='reject')w.actions.find((x:Row)=>x.id===key).status='rejected';else throw Error('External publication requires the local application.');return {}}
 throw Error('This operation requires the running local backend.')
}

export async function chatTurn(path:string,data:Row,_signal:AbortSignal,_onDelta:(s:string)=>void){return api(path,"POST",data)}
