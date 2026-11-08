import React from 'react'

type Props={busy:boolean,mic:boolean,on:boolean,attach:()=>void,dictate:()=>void,toggle:()=>void}
export default function ComposerControls({busy,mic,on,attach,dictate,toggle}:Props){
 const micLabel=mic?'Finish dictation':'Dictate a message'
 const modeLabel=on?'AI responses on · Switch to project notes':'AI responses off · Switch to AI replies'
 return <div className="composer-icons">
  <button type="button" disabled={busy} title="Attach a file" aria-label="Attach a file" onClick={attach}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 11-9 9a6 6 0 0 1-8.5-8.5l10-10a4 4 0 0 1 5.7 5.7l-10 10a2 2 0 0 1-2.8-2.8l9-9"/></svg></button>
  <button type="button" disabled={busy} aria-pressed={mic} title={micLabel} aria-label={micLabel} onClick={dictate}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8"/></svg></button>
  <button type="button" role="switch" disabled={busy} aria-checked={on} title={modeLabel} aria-label={modeLabel} onClick={toggle}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1" y="5" width="22" height="14" rx="7"/><circle cx={on?16:8} cy="12" r="3.4" fill="currentColor" stroke="none"/></svg></button>
 </div>
}
