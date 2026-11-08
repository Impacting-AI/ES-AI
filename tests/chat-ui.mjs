import assert from 'node:assert/strict'
import {build} from 'esbuild'
import {createRequire} from 'node:module'
import React from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
const req=createRequire(import.meta.url)
const code=await build({entryPoints:['web/ChatMessage.tsx'],bundle:true,external:['react','react/jsx-runtime'],format:'cjs',platform:'node',write:false})
const module={exports:{}}
new Function('require','module','exports',code.outputFiles[0].text)(req,module,module.exports)
const body='# Delivery\n|Item|Owner|\n|---|---|\n|Review|QA|\n- Verify scope\n```js\nconst value = 1\n```\n<img src=x onerror=alert(1)>'
const html=renderToStaticMarkup(React.createElement(module.exports.default,{body,copy(){}}))
for(const tag of ['<h3>Delivery','<table>','<li>','<b>const</b>','Copy code','&lt;img'])assert(html.includes(tag),tag)
assert(!html.includes('<img'))
const transport=await build({entryPoints:['web/api.ts'],bundle:true,format:'esm',write:false,platform:'node'})
const {chatTurn}=await import('data:text/javascript;base64,'+Buffer.from(transport.outputFiles[0].text).toString('base64'))
const original=globalThis.fetch
try{
 const bytes=new TextEncoder().encode('{"type":"delta","value":"é"}\n{"type":"done","value":"fixture"}\n')
 globalThis.fetch=async()=>new Response(new ReadableStream({start(c){for(const b of bytes)c.enqueue(Uint8Array.of(b));c.close()}}))
 const seen=[];await chatTurn('sample',{respond:true},new AbortController().signal,v=>seen.push(v));assert.deepEqual(seen,['é'])
 globalThis.fetch=async()=>new Response('{"type":"delta","value":"partial"}\n')
 await assert.rejects(chatTurn('sample',{respond:true},new AbortController().signal,()=>{}),/interrupted/)
 globalThis.fetch=async()=>new Response('{"detail":"Invalid credentials"}',{status:403})
 await assert.rejects(chatTurn('sample',{respond:true},new AbortController().signal,()=>{}),/Invalid credentials/)
 console.log('PASS: rich rendering and escaped HTML; fragmented UTF-8 streaming; truncated response and credential errors.')
}finally{globalThis.fetch=original}
const voice=await build({entryPoints:['web/voice.ts'],bundle:true,format:'esm',write:false,platform:'node'})
const {startDictation}=await import('data:text/javascript;base64,'+Buffer.from(voice.outputFiles[0].text).toString('base64'))
let output='',failure=''
class FakeRecognition{start(){this.active=true}}
const mic=startDictation(FakeRecognition,'en-PK',s=>output=s,s=>failure=s,()=>{})
assert.equal(mic.active,true);mic.onresult({results:[[{transcript:'Review scope'}]]});assert.equal(output,'Review scope')
mic.onerror({error:'not-allowed'});assert.match(failure,/denied/)
assert.throws(()=>startDictation(null,'en',()=>{},()=>{},()=>{}),/does not support/)
console.log('PASS: speech adapter transcript, permission-denied and unsupported-browser fixtures.')
const controls=await build({entryPoints:['web/ComposerControls.tsx'],bundle:true,external:['react','react/jsx-runtime'],format:'cjs',platform:'node',write:false})
const controlsModule={exports:{}}
new Function('require','module','exports',controls.outputFiles[0].text)(req,controlsModule,controlsModule.exports)
for(const active of [true,false]){
 const actions=[]
 const node=controlsModule.exports.default({busy:false,mic:active,on:active,attach:()=>actions.push('attach'),dictate:()=>actions.push('mic'),toggle:()=>actions.push('mode')})
 for(const button of node.props.children){assert.equal(button.props.title,button.props['aria-label']);button.props.onClick()}
 const markup=renderToStaticMarkup(node)
 assert.equal(markup.split('<svg').length-1,3)
 assert(markup.includes('aria-checked="'+active+'"'));assert(markup.includes('aria-pressed="'+active+'"'))
 assert.deepEqual(actions,['attach','mic','mode'])
}
console.log('PASS: composer icons, accessible names, switch state and action handlers.')
