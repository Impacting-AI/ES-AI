import React,{useEffect,useState} from 'react'
import {api} from './api'
export default function Health(){
 const [label,set]=useState('Checking backend…')
 useEffect(()=>{
  let live=true
  async function poll(){try{const h=await api('health');if(live)set(h.database==='ready'?'Backend online · PostgreSQL ready':h.database==='offline'?'Offline demo · Sample records':'Database unavailable')}catch{if(live)set('Disconnected · check the app and database')}}
  poll();const timer=setInterval(poll,30000);return ()=>{live=false;clearInterval(timer)}
 },[])
 return <span className="connection-health" aria-live="polite">{label}</span>
}
