export function startDictation(Recognition:any,language:string,onText:(s:string)=>void,onError:(s:string)=>void,onEnd:()=>void){
 if(!Recognition)throw Error('This browser does not support speech input. You can type your message.')
 const recognition=new Recognition()
 recognition.lang=language
 recognition.interimResults=false
 recognition.continuous=false
 recognition.onresult=(event:any)=>{
  const text=Array.from(event.results).map((result:any)=>result[0].transcript).join(' ').trim()
  if(text)onText(text)
 }
 recognition.onerror=(event:any)=>{onError(event.error==='not-allowed'?'Microphone access was denied. Allow the microphone in browser settings or type your message.':'Microphone: '+event.error);onEnd()}
 recognition.onend=onEnd
 recognition.start()
 return recognition
}
