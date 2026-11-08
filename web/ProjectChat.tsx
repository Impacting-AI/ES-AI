import React,{useEffect,useRef,useState} from 'react'
import {api,chatTurn} from './api'
import ChatMessage from './ChatMessage'
import './chat.css'
import {startDictation} from './voice'
type Row=Record<string,any>
type Props={pid:string,name:string,canEdit:boolean,openSource:(id:string,passage?:string)=>Promise<void>}
export default function ProjectChat({pid,name,canEdit,openSource}:Props){
 const base='projects/'+pid+'/chats', [list,setList]=useState<Row[]>([]),[thread,setThread]=useState<Row|null>(null),[query,search]=useState('')
 const [body,write]=useState(''),[file,pick]=useState<File|null>(null),[permanent,keep]=useState(false),[cached,cache]=useState<Row[]>([]),[on,toggle]=useState(true),[category,classify]=useState('Project note')
 const [busy,work]=useState(false),[partial,delta]=useState(''),[pending,setPending]=useState(''),[error,fail]=useState(''),[notice,say]=useState(''),[listOpen,showList]=useState(false),[mic,listen]=useState(false)
 const [renaming,rename]=useState(false),[title,setTitle]=useState(''),[feedback,setFeedback]=useState(''),[correction,correct]=useState(''),[citation,inspect]=useState<Row|null>(null)
 const [context,setContext]=useState<Row|null>(null)
 useEffect(()=>{let live=true;api(base+'/context').then(v=>live&&setContext(v)).catch(e=>live&&fail(e.message));return()=>{live=false}},[pid,busy])
 const linkedFile=useRef('')
 const stream=useRef<AbortController|null>(null),recognition=useRef<any>(null),scroll=useRef<HTMLDivElement>(null),follow=useRef(true),input=useRef<HTMLTextAreaElement>(null),upload=useRef<HTMLInputElement>(null),opened=useRef(0)
 const Speech=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition
 const rows=async(q='')=>api(base+'?q='+encodeURIComponent(q))
 const guard=async(fn:()=>Promise<void>)=>{try{fail('');await fn()}catch(e){fail((e as Error).message)}}
 async function open(id:string){const seq=++opened.current;const t=await api(base+'/'+id);if(seq!==opened.current)return;try{sessionStorage.setItem('pm-chat:'+pid,id)}catch{}linkedFile.current='';setThread(t);setTitle(t.title);rename(false);showList(false);inspect(null);delta('');setPending('');write('');pick(null);cache([]);setFeedback('');correct('');follow.current=true;recognition.current?.abort();window.speechSynthesis?.cancel()}
 async function create(){const t=await api(base,'POST',{title:'New chat'});setList(await rows(query));await open(t.id);return t}
 useEffect(()=>{let live=true;rows().then(async r=>{if(live){setList(r);let remembered='';try{remembered=sessionStorage.getItem('pm-chat:'+pid)||''}catch{}const first=r.find((x:Row)=>x.id===remembered)||r[0];if(first)await open(first.id)}}).catch(e=>live&&fail(e.message));return()=>{live=false;opened.current++;stream.current?.abort();recognition.current?.abort();window.speechSynthesis?.cancel()}},[pid])
 useEffect(()=>{let live=true;const id=setTimeout(()=>rows(query).then(r=>live&&setList(r)).catch(e=>live&&fail(e.message)),180);return()=>{live=false;clearTimeout(id)}},[query,pid])
 useEffect(()=>{if(follow.current&&scroll.current)scroll.current.scrollTop=scroll.current.scrollHeight},[thread,partial,pending])
 useEffect(()=>{if(input.current){input.current.style.height='auto';input.current.style.height=Math.min(input.current.scrollHeight,170)+'px'}},[body])
 async function copy(v:string){await guard(async()=>{await navigator.clipboard.writeText(v);say('Copied.')})}
 async function submit(text=body,current=thread,attached=cached,forceOn=on,selectedFile=file){
  if(busy||(!text.trim()&&!selectedFile))return
  const question=text.trim()||'Summarise this attachment and cite the source.'
  work(true);fail('');say('');delta('');setPending(question);follow.current=true
  const control=new AbortController();stream.current=control
  try{
   let t=current
   if(!t){t=await api(base,'POST',{title:'New chat'});setThread({...t,messages:[]});setTitle(t!.title);setList(await rows(query))}
   let ids=[...attached];let projectFile=linkedFile.current
   if(selectedFile){
    const form=new FormData();form.append('file',selectedFile)
    if(permanent){form.append('title',selectedFile.name);form.append('category','Chat attachment');form.append('origin','Chat upload');const doc=await api('projects/'+pid+'/files','POST',form);if(!doc.indexed)throw Error(doc.error||'File could not be indexed. Review it under Documents.');projectFile=doc.id;linkedFile.current=doc.id}
    else{ids=[...ids,await api(base+'/'+t!.id+'/files','POST',form)]}
    cache(ids);pick(null)
   }
   if(control.signal.aborted)throw new DOMException('Stopped','AbortError')
   await chatTurn(base+'/'+t!.id+'/turn',{body:question,revision:t!.revision,respond:forceOn,category,files:ids.map(f=>f.id),source_id:projectFile||undefined},control.signal,value=>delta(p=>p+value))
   if(!forceOn)say('Saved as draft project knowledge.')
   await open(t!.id);setList(await rows(query));write('');cache([])
  }catch(e){write(question);fail(control.signal.aborted?'Generation stopped. Edit or resend your message.':String((e as Error).message))}
  finally{stream.current=null;work(false);delta('');setPending('')}
 }
 async function branch(mid:string,regen:boolean){
  const b=await api(base+'/'+thread!.id+'/branch/'+mid,'POST');await open(b.id);setList(await rows(query));write(b.body);cache(b.files);if(regen)await submit(b.body,{id:b.id,revision:0},b.files,true,null);else input.current?.focus()
 }
 function dictate(){
  if(mic){recognition.current?.stop();return}
  try{
   recognition.current=startDictation(Speech,navigator.language,words=>{write(s=>(s+' '+words).trim());say('Review the transcription before sending.')},fail,()=>listen(false))
   listen(true)
  }catch(e){fail((e as Error).message)}

 }
 const messages:Row[]=thread?.messages||[]
 return <section className="pmchat"><aside className={'chatrail '+(listOpen?'expanded':'')}><b>Conversations</b><button disabled={!canEdit||busy} onClick={()=>guard(async()=>{await create()})}>＋ New chat</button><input aria-label="Search conversations" placeholder="Search chats…" value={query} onChange={e=>search(e.target.value)}/>{list.map(t=><button className={t.id===thread?.id?'current':''} disabled={busy} key={t.id} onClick={()=>guard(()=>open(t.id))}>{t.title}</button>)}</aside><div className="chatpanel"><header><div><small>PROJECT · {name}</small>{renaming?<form onSubmit={e=>{e.preventDefault();guard(async()=>{await api(base+'/'+thread!.id,'PATCH',{title});await open(thread!.id);setList(await rows(query))})}}><input value={title} maxLength={140} required onChange={e=>setTitle(e.target.value)}/><button>Save</button></form>:<h2>{thread?.title||'Project chat'}</h2>}</div><div className="chattools"><button className="railbutton" onClick={()=>showList(!listOpen)}>Chats</button>{thread&&canEdit&&<><button disabled={busy} onClick={()=>rename(!renaming)}>Rename</button><button disabled={busy} onClick={()=>guard(async()=>{await api(base+'/'+thread.id,'PATCH',{title:thread.title,archived:true});setThread(null);linkedFile.current='';write('');cache([]);pick(null);const r=await rows(query);setList(r);if(r[0])await open(r[0].id)})}>Archive</button></>}</div></header>
 {context&&<div className="contextline">{context.eligible} searchable project sources · {context.approved_only?'Approved sources only':'Approved and draft sources'}{context.unready>0&&' · '+context.unready+' awaiting indexing or attention in Documents'}</div>}
 <div className="transcript" ref={scroll} onScroll={()=>{const el=scroll.current!;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<90}}>
 {!messages.length&&!busy&&<div className="chatempty"><strong>Ask about {name}</strong><p>Use this project’s documents, decisions and delivery activity.</p><button onClick={()=>{write('Summarise the current approved scope and cite the documents.');input.current?.focus()}}>Summarise project scope</button></div>}
 {messages.map((m,i)=><div key={m.id} className={'turn '+m.role}><small>{m.role==='assistant'?'PM AI ES':'You'}</small><ChatMessage body={m.body} copy={copy}/>{m.files?.map((f:Row)=><span className="chip" key={f.id}>{f.name}</span>)}{m.citations?.map((c:Row)=><button className="chip" key={c.id} onClick={()=>inspect(c)}>{c.title} · {c.location||'Excerpt'}</button>)}<div className="chattools"><button onClick={()=>copy(m.body)}>Copy</button>{canEdit&&!busy&&(m.role==='user'?<button onClick={()=>guard(()=>branch(m.id,false))}>Edit in new chat</button>:<>{messages[i-1]?.role==='user'&&<button onClick={()=>guard(()=>branch(messages[i-1].id,true))}>Regenerate</button>}<button onClick={()=>setFeedback(m.id)}>Feedback</button></>)}{m.role==='assistant'&&'speechSynthesis' in window&&<><button onClick={()=>{window.speechSynthesis.cancel();window.speechSynthesis.speak(new SpeechSynthesisUtterance(m.body))}}>Play / replay</button><button onClick={()=>window.speechSynthesis.paused?window.speechSynthesis.resume():window.speechSynthesis.pause()}>Pause / resume</button><button onClick={()=>window.speechSynthesis.cancel()}>Stop audio</button></>}</div>
 {feedback===m.id&&<form onSubmit={e=>{e.preventDefault();guard(async()=>{await api('projects/'+pid+'/feedback','POST',{target:m.id,category:'Chat feedback',body:correction});setFeedback('');correct('');say('Feedback recorded.')})}}><input required value={correction} onChange={e=>correct(e.target.value)} placeholder="What should improve?"/><button>Submit feedback</button></form>}</div>)}
 {busy&&<><div className="turn user">{pending}</div><div className="turn assistant"><small>PM AI ES · Generating</small><ChatMessage body={partial} copy={copy}/></div></>}
 </div>{citation&&<section className="citation"><button onClick={()=>inspect(null)}>Close</button><strong>{citation.title} · {citation.location||'Excerpt'}</strong><p>{citation.body}</p>{citation.sid&&!citation.kind&&<button onClick={()=>guard(()=>openSource(citation.sid,citation.id))}>Open project document</button>}</section>}
 {error&&<p role="alert">{error}</p>}{notice&&<small role="status">{notice}</small>}
 {canEdit&&<div className="composer"><textarea ref={input} rows={1} value={body} disabled={busy} onChange={e=>write(e.target.value)} maxLength={6000} placeholder={on?'Ask about this project…':'Write a project note…'} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();submit()}}}/>{file&&<label>{file.name} <button onClick={()=>pick(null)}>Remove</button><input type="checkbox" checked={permanent} onChange={e=>keep(e.target.checked)}/> Add to project knowledge</label>}{cached.map(f=><small key={f.id}>{f.name} </small>)}<div className="composeactions"><input ref={upload} hidden type="file" accept=".pdf,.docx,.txt,.csv,.xlsx,.md,.json" onChange={e=>{linkedFile.current='';pick(e.target.files?.[0]||null);e.target.value='';keep(false)}}/><button disabled={busy} onClick={()=>upload.current?.click()}>Attach</button><button disabled={busy} onClick={dictate}>{mic?'Finish recording':'Microphone'}</button><label><input type="checkbox" checked={on} disabled={busy} onChange={e=>toggle(e.target.checked)}/> Response {on?'ON':'OFF'}</label>{!on&&<select value={category} onChange={e=>classify(e.target.value)}>{['Project note','Client discussion','Proposed change','Internal instruction'].map(v=><option key={v}>{v}</option>)}</select>}{busy?<button onClick={()=>stream.current?.abort()}>Stop generating</button>:<button className="primary" disabled={!body.trim()&&!file} onClick={()=>submit()}>{on?(error?'Retry':'Send'):'Save note'}</button>}</div></div>}
 </div></section>
}
