import React,{useEffect,useState} from 'react'
import {api} from './api'
export default function ReportRule({pid,onRecipient}:{pid:string,onRecipient:(v:string)=>void}){
 const [rule,set]=useState<any>(),[msg,say]=useState('')
 const path='projects/'+pid+'/report-rule'
 useEffect(()=>{api(path).then(r=>{set(r);onRecipient(r.recipient)}).catch(e=>say(e.message))},[path])
 return <article><h2>Scheduled report drafts</h2>{rule&&<form onSubmit={async e=>{
  e.preventDefault();const f=Object.fromEntries(new FormData(e.currentTarget))
  try{const r=await api(path,'PUT',{...f,hour:Number(f.hour),weekday:Number(f.weekday)});set(r);onRecipient(r.recipient);say('Schedule saved. Email delivery requires review.')}catch(e){say((e as Error).message)}
 }}><label>Frequency<select name="frequency" defaultValue={rule.frequency}>{['Off','Daily','Weekly'].map(v=><option key={v}>{v}</option>)}</select></label><label>Time zone<input name="zone" defaultValue={rule.zone} required/></label><div className="pair"><label>Local hour (0–23)<input name="hour" type="number" min="0" max="23" required defaultValue={rule.hour}/></label><label>Weekly draft day<select name="weekday" defaultValue={rule.weekday}>{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((v,i)=><option key={v} value={i}>{v}</option>)}</select></label></div><label>Audience<select name="audience" defaultValue={rule.audience}><option>CEO</option><option>Client</option></select></label><label>Report heading<input name="heading" required defaultValue={rule.heading}/></label><label>Suggested email recipient<input type="email" name="recipient" defaultValue={rule.recipient}/></label><button>Save schedule</button></form>}<p role="status">{msg}</p></article>
}
