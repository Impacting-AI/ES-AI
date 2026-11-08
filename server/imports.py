import hashlib
import json
from datetime import datetime

def parse_export(raw):
    """Supported interchange format; preserve external order and provenance."""
    root=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(root,dict):raise ValueError('Expected an object with platform and messages.')
    platform=root.get('platform')
    messages=root.get('messages')
    if not isinstance(platform,str) or not platform.strip() or len(platform)>100 or not isinstance(messages,list) or not 1<=len(messages)<=2000:raise ValueError('Provide a platform and 1–2000 messages.')
    records=[]
    for i,item in enumerate(messages):
        if not isinstance(item,dict) or not isinstance(item.get('text'),str):raise ValueError(f'Message {i+1} requires text.')
        ts=item.get('timestamp','');sender=item.get('sender','')
        if not isinstance(sender,str) or not isinstance(ts,str):raise ValueError('Use text values for sender and timestamp.')
        if ts:datetime.fromisoformat(ts.replace('Z','+00:00'))
        attachments=item.get('attachments',[])
        if not isinstance(attachments,list) or not all(isinstance(a,str) for a in attachments):raise ValueError('Attachment references must be a list of strings.')
        records.append(f"[{i+1}] {platform} | {ts or 'Time unknown'} | {sender or 'Sender unknown'}\n{item['text']}"+('\nAttachments: '+', '.join(attachments) if attachments else ''))
    return platform,'\n\n'.join(records),hashlib.sha256(raw).hexdigest()
