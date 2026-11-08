import React,{useEffect,useState} from 'react'
import {api} from './api'

type Row=Record<string,any>
export type FeedbackFocus={thread:string,message:string}
const categories=['Response style','Project knowledge','Retrieval','Planning','Reasoning']
function Proposal({row,admin,run,busy}:{row:Row,admin:boolean,run:(fn:()=>Promise<any>)=>void,busy:boolean}){
 const [text,edit]=useState(row.policy_text),[global,scope]=useState(!!row.applied?.proposed_global),[pref,prefer]=useState(row.applied?.preference||'Concise')
 const [detail,show]=useState<Row|null>(null),[error,fail]=useState('')
 const base='projects/'+row.pid+'/conversation-feedback/'+row.id
 const decide=(action:string)=>run(()=>api(base+'/decision','POST',{action,text,version:row.edit_version,global_style:global,preference:pref}))
 return <details><summary>{row.category} · {row.status} · {row.correction.slice(0,70)}</summary>
 <button onClick={async()=>{try{show(await api(base+'/evidence'));fail('')}catch(e){fail((e as Error).message)}}}>Review selected messages and versions</button>{error&&<p role="alert">{error}</p>}{detail&&<div className="feedback-thread">{detail.messages.map((m:Row)=><p key={m.id}><b>{m.role}</b> {m.body}</p>)}{detail.versions.map((v:Row)=><p key={v.version}>v{v.version} · {v.status} · {v.body}</p>)}</div>}<p>{row.correction}</p><small>{row.message_ids.length} selected messages · v{row.edit_version}</small>
 {row.analysis&&<><h3>Likely cause</h3><p>{row.analysis}</p></>}
 {row.status==='draft'&&<button disabled={busy} onClick={()=>run(()=>api(base+'/analyse','POST'))}>{row.analysis?'Analyse again':'Analyse feedback'}</button>}
 {row.status==='draft'&&admin?<><label>Proposed correction<textarea value={text} maxLength={3000} onChange={e=>edit(e.target.value)}/></label>
 {row.category==='Response style'&&<><label><input type="checkbox" checked={global} onChange={e=>scope(e.target.checked)}/> Apply an agent-wide response preference</label>{global&&<label>Global preference (only this setting will change)<select value={pref} onChange={e=>prefer(e.target.value)}>{['Concise','Balanced','Detailed'].map(p=><option key={p}>{p}</option>)}</select></label>}</>}
 {row.category==='Project knowledge'&&<p>Approval creates a draft under Documents. Review the source there before making it authoritative.</p>}
 {row.category==='Retrieval'&&<p>Approval records an indexing or retrieval investigation for follow-up.</p>}
 <div className="chattools">{['save','approve','reject'].map(a=><button key={a} disabled={busy||!text.trim()} onClick={()=>decide(a)}>{a==='save'?'Save for later':a==='approve'?'Approve change':'Reject'}</button>)}</div></>:<p>{row.policy_text}</p>}
 {row.applied?.source&&<p>Knowledge source · {row.applied.source}</p>}{row.applied?.task&&<p>{row.applied.task}</p>}{row.applied?.scope==='agent'&&<p>Agent preference · {row.applied.preference} · revision {row.applied.revision}</p>}
 {row.status==='approved'&&admin&&<button disabled={busy} onClick={()=>decide('rollback')}>Roll back change</button>}
 </details>
}

export default function ConversationFeedback({pid,project,canEdit,focus}:{pid:string,project:string,canEdit:boolean,focus:FeedbackFocus|null}){
 const base='projects/'+pid+'/',[query,search]=useState(''),[threads,setThreads]=useState<Row[]>([]),[tid,choose]=useState(focus?.thread||''),[chat,setChat]=useState<Row|null>(null)
 const [ids,select]=useState<string[]>([]),[entire,all]=useState(false),[category,cat]=useState(categories[0]),[body,write]=useState(''),[rows,setRows]=useState<Row[]>([]),[admin,priv]=useState(false),[busy,work]=useState(false),[msg,say]=useState(''),[err,fail]=useState('')
 const reload=async()=>setRows(await api(base+'conversation-feedback'))
 useEffect(()=>{let live=true;const timer=setTimeout(()=>api(base+'chats?q='+encodeURIComponent(query)).then(data=>{if(live)setThreads(data)}).catch(e=>live&&fail(e.message)),120);return()=>{live=false;clearTimeout(timer)}},[base,query])
 useEffect(()=>{let live=true;setChat(null);select([]);all(false);write('');if(tid)api(base+'chats/'+tid).then(data=>{if(live){setChat(data);select(focus?.thread===tid?[focus.message]:[])}}).catch(e=>live&&fail(e.message));return()=>{live=false}},[base,tid,focus])
 useEffect(()=>{reload().catch(e=>fail(e.message));api('session').then(x=>priv(x.admin)).catch(e=>fail(e.message))},[base])
 async function run(fn:()=>Promise<any>){work(true);fail('');say('');try{await fn();say('Saved.')}catch(e){fail((e as Error).message)}finally{try{await reload()}catch(e){fail((e as Error).message)}work(false)}}
 return <article><small>{project}</small><h2>Conversation feedback</h2><label>Find a conversation<input type="search" value={query} onChange={e=>search(e.target.value)} placeholder="Search titles or messages"/></label>
 <div className="feedback-choices">{threads.map(t=><button disabled={busy} key={t.id} aria-pressed={t.id===tid} onClick={()=>choose(t.id)}><strong>{t.title}</strong><small>Created {new Date(t.created||t.updated).toLocaleDateString()} · Updated {new Date(t.updated).toLocaleString()}</small>{t.preview}</button>)}</div>{!threads.length&&<p>No matching saved conversations.</p>}
 {chat&&<><h3>{chat.title}</h3><label><input type="checkbox" checked={entire} onChange={e=>all(e.target.checked)}/> Entire conversation</label><div className="feedback-thread">{chat.messages.map((m:Row)=><label key={m.id}><input type="checkbox" checked={entire||ids.includes(m.id)} disabled={entire} onChange={e=>select(e.target.checked?[...ids,m.id]:ids.filter(x=>x!==m.id))}/><strong>{m.role==='assistant'?'PM AI ES':'User'}</strong><p>{m.body}</p></label>)}</div>
 {canEdit&&<form onSubmit={e=>{e.preventDefault();run(async()=>{const result=await api(base+'conversation-feedback','POST',{thread_id:tid,message_ids:entire?[]:ids,entire,body,category});write('');try{await api(base+'conversation-feedback/'+result.id+'/analyse','POST')}catch(e){throw Error('Feedback saved. Analysis pending: '+(e as Error).message)}})}}><label>Category<select value={category} onChange={e=>cat(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></label><p>Project administrators can review the selected messages and correction.</p><label>What should PM AI ES correct or improve?<textarea required maxLength={3000} value={body} onChange={e=>write(e.target.value)}/></label><button className="primary" disabled={busy||!body.trim()||!(entire?chat.messages.length:ids.length)}>Submit for analysis</button></form>}</>}
 {busy&&<p role="status">Working…</p>}{err&&<p role="alert">{err}</p>}{msg&&<p role="status">{msg}</p>}
 <h3>Improvement proposals</h3>{rows.map(row=><Proposal key={row.id+'-'+row.edit_version} row={row} admin={admin} run={run} busy={busy}/>)}</article>
}
