import assert from 'node:assert/strict'
import http from 'node:http'
import {build} from 'esbuild'
const b=await build({entryPoints:['web/api.ts'],bundle:true,format:'esm',write:false,platform:'node'})
const {api}=await import('data:text/javascript;base64,'+Buffer.from(b.outputFiles[0].text).toString('base64'))
const requests=[]
const mock=http.createServer(async(req,res)=>{
 const chunks=[];for await(const c of req)chunks.push(c)
 requests.push({url:req.url,method:req.method,body:Buffer.concat(chunks).toString()})
 res.setHeader('content-type','application/json')
 if(req.url.endsWith('denied')){res.statusCode=403;res.end(JSON.stringify({detail:'Insufficient permissions'}))}
 else res.end(JSON.stringify({received:true}))
})
await new Promise(r=>mock.listen(0,'127.0.0.1',r))
const fetchImpl=globalThis.fetch
globalThis.fetch=(path,options)=>fetchImpl(new URL(path,'http://127.0.0.1:'+mock.address().port),options)
try{
 assert.equal((await api('projects','POST',{name:'Fixture',client:'Test'})).received,true)
 await api('projects/one/messages','POST',{body:'question',respond:true})
 await api('connections/OpenAI/test','POST',{credential:'fixture-placeholder',policy:{model:'test'}})
 await assert.rejects(api('denied'),/Insufficient permissions/)
 assert.deepEqual(requests.slice(0,3).map(x=>x.url),['/api/projects','/api/projects/one/messages','/api/connections/OpenAI/test'])
 assert(requests.every(r=>!r.url.includes('fixture-placeholder')))
 console.log('PASS: frontend HTTP transport, submissions, server-only credential path and displayed API errors (local fixture).')
} finally{globalThis.fetch=fetchImpl;mock.closeAllConnections();await new Promise(r=>mock.close(r))}
