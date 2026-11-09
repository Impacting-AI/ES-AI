import React from 'react'
function inline(s:string){
 return s.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g).map((p,i)=>{
  if(p.startsWith('**'))return <strong key={i}>{p.slice(2,-2)}</strong>
  if(p.startsWith('`'))return <code key={i}>{p.slice(1,-1)}</code>
  const link=p.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/)
  return link?<a key={i} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]}</a>:p
 })
}
function highlight(s:string){return s.split(/(\b(?:function|return|const|let|def|from|import|class|if|else|async|await|SELECT|FROM|WHERE|true|false|null)\b)/g).map((p,i)=>i%2?<b key={i}>{p}</b>:p)}
export default function ChatMessage({body,copy}:{body:string,copy:(v:string)=>void}){
 const lines=body.split('\n'),out:React.ReactNode[]=[]
 for(let i=0;i<lines.length;){
  const k=i,line=lines[i++]
  if(!line.trim())continue
  if(line.startsWith('```')){
   const code=[];while(i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i++]);i++
   const value=code.join('\n');out.push(<section className="codeblock" key={k}><small>{line.slice(3)||'Code'}</small><button onClick={()=>copy(value)}>Copy code</button><pre><code>{highlight(value)}</code></pre></section>);continue
  }
  if(line.includes('|')&&i<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i])){
   const cells=(v:string)=>v.trim().replace(/^\||\|$/g,'').split('|')
   i++;const rows=[];while(i<lines.length&&lines[i].includes('|'))rows.push(cells(lines[i++]))
   out.push(<div className="scroll" key={k}><table><thead><tr>{cells(line).map((v,j)=><th key={j}>{inline(v)}</th>)}</tr></thead><tbody>{rows.map((r,j)=><tr key={j}>{r.map((v,n)=><td key={n}>{inline(v)}</td>)}</tr>)}</tbody></table></div>);continue
  }
  if(/^#{1,6} /.test(line)){out.push(<h3 key={k}>{inline(line.replace(/^#+ /,''))}</h3>);continue}
  const list=line.match(/^\s*(?:[-*•]|(\d+)\.)\s+(.*)/)
  if(list){const listItems=[list[2]],pattern=list[1]?/^\s*\d+\.\s+(.*)/:/^\s*[-*•]\s+(.*)/;while(i<lines.length&&pattern.test(lines[i]))listItems.push(lines[i++].match(pattern)![1]);const Tag=list[1]?'ol':'ul';out.push(<Tag key={k}>{listItems.map((v,j)=><li key={j}>{inline(v)}</li>)}</Tag>);continue}
  out.push(<p key={k}>{inline(line)}</p>)
 }
 return <div className="chat-prose">{out}</div>
}
