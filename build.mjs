import {build} from 'esbuild'
import {mkdir,readFile,writeFile} from 'node:fs/promises'
await mkdir('dist',{recursive:true})
const buildResult=await build({entryPoints:['web/main.tsx'],bundle:true,write:false,minify:true,outfile:'dist/app.js',target:'es2022',loader:{'.png':'dataurl'},define:{'process.env.NODE_ENV':'"production"'}})
const js=buildResult.outputFiles.find(f=>f.path.endsWith('.js')).text
const css=buildResult.outputFiles.find(f=>f.path.endsWith('.css')).text
const html=await readFile('index.html','utf8')
await writeFile('dist/app.js',js)
await writeFile('dist/app.css',css)
await writeFile('dist/index.html',html.replace('</head>','<link rel="stylesheet" href="/app.css"></head>').replace(/<script.*?<\/script>/,'<script src="/app.js"></script>'))
