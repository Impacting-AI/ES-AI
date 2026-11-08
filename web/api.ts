export type Method='GET'|'POST'|'PUT'|'PATCH'|'DELETE'
export async function api(path:string,method:Method='GET',body?:unknown) {
  const file=body instanceof FormData
  const response=await fetch('/api/'+path,{method,signal:AbortSignal.timeout(150000),headers:file?{}:{'Content-Type':'application/json'},body:file?body:JSON.stringify(body)}).catch(()=>{throw Error('Backend connection lost. Start PM AI ES and reopen http://localhost:8080.')})
  if(!response.ok){
    const e=await response.json().catch(()=>({}))
    if(Array.isArray(e.detail))throw Error(e.detail.map((x:any)=>x.loc.slice(1).join('.')+' · '+x.msg).join('\n'))
    throw Error(typeof e.detail==='string'?e.detail:'Request failed ('+response.status+').')
  }
  return response.json()
}

export async function chatTurn(path:string,data:Record<string,unknown>,signal:AbortSignal,onDelta:(s:string)=>void){
 const res=await fetch('/api/'+path,{method:'POST',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
 if(!res.ok){const error=await res.json().catch(()=>({}));throw Error(typeof error.detail==='string'?error.detail:'Request failed ('+res.status+')')}
 if(!data.respond)return res.json()
 if(!res.body)throw Error('Streaming unavailable in this browser.')
 const reader=res.body.getReader(),decoder=new TextDecoder()
 let buffer='',done=false
 try{
  for(;;){
   const next=await reader.read()
   buffer+=decoder.decode(next.value,{stream:!next.done})
   const lines=buffer.split('\n');buffer=lines.pop()||''
   for(const line of lines){
    if(!line.trim())continue
    const event=JSON.parse(line)
    if(event.type==='delta')onDelta(event.value)
    if(event.type==='error')throw Error(event.value)
    if(event.type==='done')done=true
   }
   if(next.done)break
  }
 }finally{reader.releaseLock()}
 if(!done)throw Error('Stream interrupted. Your draft is available to retry.')
}
