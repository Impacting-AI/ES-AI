import React,{useEffect,useState} from 'react'
import {api} from './api'
type Mapping={service:string,destination:string,mapping_id:string,resource_name:string,resource_url:string,board_id:string,connected:boolean,sync_status:string,last_sync:string}
type Option={id:string,name:string}
function Panel({pid,service,link,canEdit,reload}:{pid:string,service:string,link?:Mapping,canEdit:boolean,reload:()=>Promise<void>}){
 const jira=service==='Jira',base='projects/'+pid+'/'
 const [dest,setDest]=useState(link?.destination||''),[board,setBoard]=useState(link?.board_id||'')
 const [query,search]=useState(''),[items,setItems]=useState<Option[]>([]),[cursor,page]=useState('')
 const [busy,working]=useState(false),[message,say]=useState(''),[error,fail]=useState('')
 async function run(fn:()=>Promise<string>){
  working(true);fail('');say('')
  try{say(await fn())}catch(e){fail((e as Error).message);await reload().catch(()=>{})}finally{working(false)}
 }
 async function discover(next=''){
  const result=await api(base+'connections/search','POST',{service,query,cursor:next})
  setItems(next?[...items,...result.items]:result.items);page(result.next||'')
  return result.items.length?'Select a result below.':'No matches on this page.'
 }
 async function connect(test:boolean){
  const r=await api(base+'link'+(test?'/test':''),test?'POST':'PUT',{service,destination:dest.trim(),board_id:jira?board:'',expected:link?.mapping_id||''})
  await reload()
  return test?'Access verified for '+r.resource_name:'Mapping saved. Initial sync queued.'
 }
 return <article><h3>{jira?'Jira project':'Slack channel'}</h3>
 <p><b>{link?(link.connected?'Connected':'Needs verification'):'Disconnected'}</b>{link&&<> · <a href={link.resource_url||undefined} target="_blank" rel="noreferrer">{link.resource_name||link.destination}</a> ({link.destination})</>}</p>
 {link&&<p>{link.sync_status||'Initial sync queued'} · Last successful sync {link.last_sync?new Date(link.last_sync).toLocaleString():'pending'}</p>}
 {canEdit&&<fieldset disabled={busy} className="control-group">
 <label>{jira?'Search Jira projects':'Search Slack channels'}<input value={query} onChange={e=>{search(e.target.value);page('');setItems([])}}/></label>
 <button onClick={()=>run(()=>discover())}>Search</button>{cursor&&<button onClick={()=>run(()=>discover(cursor))}>More results</button>}
 {items.length>0&&<label>Select existing {jira?'project':'channel'}<select value="" onChange={e=>{setDest(e.target.value);say('')}}><option value="">Choose…</option>{items.map(i=><option key={i.id} value={i.id}>{i.name} ({i.id})</option>)}</select></label>}
 <label>{jira?'Jira project ID or key':'Slack channel ID'}<input value={dest} onChange={e=>{setDest(e.target.value);say('')}}/></label>
 {jira&&<label>Jira board ID (optional)<input value={board} inputMode="numeric" onChange={e=>setBoard(e.target.value)}/></label>}
 <div className="actions"><button disabled={!dest.trim()} onClick={()=>run(()=>connect(true))}>Test connection</button>
 <button disabled={!dest.trim()} className="primary" onClick={()=>run(()=>connect(false))}>{link?'Save connection':'Connect '+(jira?'project':'channel')}</button>
 {link&&<><button onClick={()=>run(async()=>{const r=await api(base+'sync/'+service,'POST');await reload();return r.fetched+' records synced.'+(r.more?' More pages queued.':'')})}>Sync now</button>
 <button onClick={()=>run(async()=>{await api(base+'link/'+service+'?expected='+encodeURIComponent(link.mapping_id),'DELETE');await reload();return 'Disconnected.'})}>Disconnect</button></>}</div></fieldset>}
 {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}</article>
}
export default function ProjectConnections({pid,canEdit}:{pid:string,canEdit:boolean}){
 const [links,set]=useState<Mapping[]>(),[error,fail]=useState('')
 const reload=async()=>set(await api('projects/'+pid+'/connections'))
 useEffect(()=>{let active=true;const refresh=async()=>{try{const rows=await api('projects/'+pid+'/connections');if(active){set(rows);fail('')}}catch(e){if(active)fail((e as Error).message)}};refresh();const timer=window.setInterval(refresh,30000);return ()=>{active=false;window.clearInterval(timer)}},[pid])
 return <section><h2>Jira &amp; Slack Connections</h2>{error&&<p role="alert">{error}</p>}
 <div className="agent-grid">{links&&['Jira','Slack'].map(service=>{const link=links.find(l=>l.service===service);return <Panel key={service+(link?.mapping_id||'')} {...{service,pid,canEdit,link,reload}}/>})}</div></section>
}
