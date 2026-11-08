import React,{useEffect,useState} from 'react'
import {api} from './api'
export default function ImprovementReview({pid,refreshKey}:{pid:string,refreshKey:unknown}){
 const path='projects/'+pid+'/improvements'
 const [rows,set]=useState<any[]>([]),[admin,privilege]=useState(false),[msg,say]=useState('')
 useEffect(()=>{Promise.all([api(path),api('session')]).then(([r,u])=>{set(r);privilege(u.admin)}).catch(e=>say(e.message))},[path,refreshKey])
 return <section><h2>Project instruction proposals</h2>{rows.map(r=><details key={r.id}><summary>{r.category} · {r.status} · {r.occurrences||1} in this category</summary><p>{r.correction}</p><p>Proposed project guidance: {r.policy_text}</p><small>Source output: {r.evidence[1]}</small>{r.status==='draft'&&admin&&<form onSubmit={async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await api(path+'/'+r.id,'POST',{approve:f.get('decision')==='Apply',evaluation:f.get('evaluation')});set(await api(path));say('Decision saved.')}catch(e){say((e as Error).message)}}}><label>Review findings<textarea required minLength={4} name="evaluation"/></label><select name="decision"><option>Reject</option><option>Apply</option></select><button>Confirm decision</button></form>}{admin&&r.status==='approved'&&<button onClick={async()=>{try{await api(path+'/'+r.id+'/rollback','POST');set(await api(path));say('Previous project guidance restored.')}catch(e){say((e as Error).message)}}}>Restore previous guidance</button>}{r.evaluation&&<p>{r.evaluation}</p>}</details>)}<p role="status">{msg}</p></section>
}
