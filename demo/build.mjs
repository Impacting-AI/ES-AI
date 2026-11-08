import {build} from 'esbuild'
import {readFile,writeFile} from 'node:fs/promises'
import path from 'node:path'
const result=await build({entryPoints:['web/main.tsx'],bundle:true,minify:true,write:false,outfile:'preview.js',target:'es2022',loader:{'.png':'dataurl'},define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'offline-api',setup(b){b.onResolve({filter:/^\.\/api$/},()=>({path:path.resolve('demo/api.ts')}))}}]})
const js=result.outputFiles.find(f=>f.path.endsWith('.js')).text
const css=result.outputFiles.find(f=>f.path.endsWith('.css')).text
const html=(await readFile('index.html','utf8')).replace('</head>',`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'"><style>${css}.demo-banner{padding:12px 22px;background:#22251f;color:white;font:14px/1.5 system-ui}.demo-banner a{color:#eeeeac}</style></head>`).replace('<div id="root">','<div class="demo-banner"><b>Offline demonstration</b> · Enter any sample username and password to explore. Use sample data only. Changes last until refresh. AI and external services are disconnected. <a href="http://localhost:8080">Open installed app</a></div><div id="root">').replace(/<script type="module"[^>]+><\/script>/,()=>'<script>'+js.replace(/<\/script/gi,'<\\/script')+'</script>')
await writeFile(process.argv[2]||'demo/test-preview.html',html)
