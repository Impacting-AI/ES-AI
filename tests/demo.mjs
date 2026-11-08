import assert from 'node:assert/strict'
import {webcrypto} from 'node:crypto'
import {build} from 'esbuild'
if(!globalThis.crypto)globalThis.crypto=webcrypto
const mod=await build({entryPoints:['demo/api.ts'],platform:'node',format:'esm',bundle:true,write:false})
const {api}=await import('data:text/javascript;base64,'+Buffer.from(mod.outputFiles[0].text).toString('base64'))
await assert.rejects(api('session'),/sign in/);await api('login','POST',{})
const p=await api('projects','POST',{name:'Test',client:'Example'}),base='projects/'+p.id+'/'
await api(base+'messages','POST',{respond:false,body:'Use cobalt'})
assert.equal((await api(base+'search?q=cobalt')).length,1)
assert.equal((await api('projects/sample/search?q=cobalt')).length,0)
await assert.rejects(api('connections/OpenAI/test','POST',{}),/Offline/)
await api(base+'report-drafts','POST',{start:'2026-11-01',end:'2026-11-07',audience:'CEO'})
assert.equal((await api(base+'report-drafts')).length,1)
await api('logout','POST');await assert.rejects(api(base+'workspace'),/sign in/)
console.log('PASS: offline demo login, project isolation, note retrieval, report draft, disconnected integration and logout.')
await api('login','POST',{})
const chat=await api(base+'chats','POST',{title:'Test chat'})
await api(base+'chats/'+chat.id+'/turn','POST',{body:'Reminder for Thursday',respond:false})
assert.equal((await api(base+'chats/'+chat.id)).messages.length,1)
await api(base+'chats/'+chat.id,'PATCH',{title:'Handover'})
assert.equal((await api(base+'chats?q=handover')).length,1)
await api(base+'chats/'+chat.id,'PATCH',{archived:true})
assert.equal((await api(base+'chats?q=handover')).length,0)
console.log('PASS: offline chat creation, note, rename, search and archive.')
