"""Thread-scoped persistence and delivery of provider tokens to authorised clients."""
import asyncio,json,threading
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field
from .chat_memory import digest
from .knowledge import process,select_context,valid_citations
from .db import database
from .agent_store import settings,secret

class Title(BaseModel):
    title:str=Field(default="New chat",min_length=1,max_length=140)
class Edit(Title):
    archived:bool=False
class Turn(BaseModel):
    body:str=Field(min_length=1,max_length=6000)
    respond:bool=True
    category:str=Field(default="Project note",max_length=100)
    source_id:str | None=Field(default=None,max_length=100)
    files:list[str]=Field(default_factory=list,max_length=4)
    revision:int=Field(ge=0)

def thread(db,pid,tid,uid,lock=False):
    t=db.execute("SELECT * FROM chat_threads WHERE pid=%s AND id=%s AND (owner_id=%s OR owner_id IS NULL)"+(" FOR UPDATE" if lock else ""),(pid,tid,uid)).fetchone()
    if not t:raise HTTPException(404,"Conversation unavailable.")
    return t

def router(member,ask,evidence,add_source):
    r=APIRouter(prefix="/api/projects/{pid}/chats")
    @r.get("")
    def listing(pid:str,q:str="",user=Depends(member)):
        with database() as db:return db.execute("""SELECT t.id,t.title,t.updated,t.revision FROM chat_threads t WHERE t.pid=%s AND NOT archived AND (owner_id=%s OR owner_id IS NULL) AND (title ILIKE %s OR EXISTS(SELECT 1 FROM messages m WHERE m.pid=t.pid AND m.thread_id=t.id AND m.body ILIKE %s)) ORDER BY updated DESC LIMIT 150""",(pid,user,"%"+q[:180]+"%","%"+q[:180]+"%")).fetchall()

    @r.post("")
    def create(pid:str,data:Title,user=Depends(member)):
        with database() as db:return db.execute("INSERT INTO chat_threads(id,pid,owner_id,title) VALUES(%s,%s,%s,%s) RETURNING id,title,revision",(str(uuid4()),pid,user,data.title)).fetchone()

    @r.get("/context")
    def context(pid:str,user=Depends(member)):
        with database() as db:
            _,p=settings(db)
            row=db.execute("SELECT count(*) FILTER(WHERE processing='Ready' AND (NOT %s OR state='approved')) AS eligible,count(*) FILTER(WHERE processing<>'Ready') AS unready FROM sources WHERE pid=%s AND state<>'superseded'",(p.approved_only,pid)).fetchone()
            return dict(row,approved_only=p.approved_only)
    @r.get("/{tid}")
    def read(pid:str,tid:str,user=Depends(member)):
        with database() as db:
            t=thread(db,pid,tid,user)
            return dict(t,messages=db.execute("SELECT * FROM messages WHERE pid=%s AND thread_id=%s ORDER BY created,id",(pid,tid)).fetchall())

    @r.patch("/{tid}")
    def update(pid:str,tid:str,data:Edit,user=Depends(member)):
        with database() as db:
            thread(db,pid,tid,user,True)
            db.execute("UPDATE chat_threads SET title=%s,archived=%s,revision=revision+1 WHERE id=%s",(data.title,data.archived,tid))
        return {"saved":True}

    @r.post("/{tid}/branch/{mid}")
    def branch(pid:str,tid:str,mid:str,user=Depends(member)):
        with database() as db:
            old=thread(db,pid,tid,user,True)
            target=db.execute("SELECT created,role,body,files FROM messages WHERE pid=%s AND thread_id=%s AND id=%s",(pid,tid,mid)).fetchone()
            if not target or target['role']!='user':raise HTTPException(404,"Choose a user turn.")
            new=str(uuid4())
            db.execute("INSERT INTO chat_threads(id,pid,owner_id,title) VALUES(%s,%s,%s,%s)",(new,pid,user,(old['title'][:110]+' · branch')))
            history=db.execute("SELECT * FROM messages WHERE pid=%s AND thread_id=%s AND (created,id)<(%s,%s) ORDER BY created,id",(pid,tid,target['created'],mid)).fetchall()
            ids={v['id'] for m in history+[target] for v in m['files']}
            mapping={}
            for fid in ids:
                newfile=str(uuid4())
                if db.execute("INSERT INTO chat_files(id,pid,thread_id,name,parts,created,original) SELECT %s,pid,%s,name,parts,created,original FROM chat_files WHERE pid=%s AND thread_id=%s AND id=%s",(newfile,new,pid,tid,fid)).rowcount:mapping[fid]=newfile
            def remap(files):return [dict(f,id=mapping.get(f['id'],f['id'])) for f in files]
            for m in history:
                db.execute("INSERT INTO messages(id,pid,thread_id,role,body,refs,citations,files,created) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)",(str(uuid4()),pid,new,m['role'],m['body'],m['refs'],json.dumps(m['citations']),json.dumps(remap(m['files'])),m['created']))
            return {"id":new,"body":target['body'],"files":remap(target['files'])}

    @r.post("/{tid}/files")
    def attach(pid:str,tid:str,file:UploadFile=File(),user=Depends(member)):
        with database() as db:thread(db,pid,tid,user)
        raw=file.file.read(5*1024**2+1)
        if len(raw)>5*1024**2:raise HTTPException(413,"Maximum attachment size is 5 MiB.")
        name=Path(file.filename or "file").name[:250]
        status,error,parts=process(name,raw)
        if status!='Ready':raise HTTPException(422,error)
        fid=str(uuid4())
        with database() as db:db.execute("INSERT INTO chat_files(id,pid,thread_id,name,parts,original) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",(fid,pid,tid,name,json.dumps(parts),raw))
        return {"id":fid,"name":name}

    @r.post("/{tid}/turn")
    def turn(pid:str,tid:str,data:Turn,user=Depends(member)):
        with database() as db:
            t=thread(db,pid,tid,user,True)
            if t['archived'] or t['revision']!=data.revision:raise HTTPException(409,"Conversation changed. Reopen it before sending.")
            if not data.body.strip():raise HTTPException(422,"Write a message.")
            files=db.execute("SELECT * FROM chat_files WHERE pid=%s AND thread_id=%s AND id=ANY(%s::text[])",(pid,tid,data.files)).fetchall()
            if len(files)!=len(set(data.files)):raise HTTPException(404,"Attachment unavailable.")
            attachments=[dict(id=f['id'],name=f['name']) for f in files]
            _,p=settings(db)
            def save(db,role,body,cites,attached):
                db.execute("INSERT INTO messages(id,pid,thread_id,role,body,refs,citations,files,created) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,clock_timestamp())",(str(uuid4()),pid,tid,role,body,json.dumps([x['id'] for x in cites]),json.dumps(cites),json.dumps(attached)))
            if not data.respond:
                sid=add_source(db,pid,data.body[:70],data.category,"Chat note","",None,None,data.body)
                save(db,'user',data.body,[],attachments)
                db.execute("UPDATE chat_threads SET title=CASE WHEN title='New chat' THEN %s ELSE title END,revision=revision+1,updated=now() WHERE id=%s",(data.body[:70],tid))
                db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES(%s,%s,'knowledge.saved',%s)",(user,pid,sid))
                return {"saved":sid}
            recent=db.execute("SELECT role,body,refs FROM messages WHERE pid=%s AND thread_id=%s ORDER BY created DESC,id DESC LIMIT %s",(pid,tid,p.history_messages)).fetchall()[::-1]
            history=[dict(role=m['role'],body=m['body'][:1300]) for m in recent]
            refs=evidence(db,pid,data.body,True,history)
            pinned=[]
            if data.source_id:
                pinned=db.execute("""SELECT p.id,p.sid,p.position,p.body,p.location,s.title,s.state FROM passages p JOIN sources s ON s.id=p.sid AND s.pid=p.pid WHERE p.pid=%s AND s.id=%s AND s.processing='Ready' AND s.state<>'superseded' AND (NOT %s OR s.state='approved') ORDER BY p.position""",(pid,data.source_id,p.approved_only)).fetchall()
                if not pinned:raise HTTPException(409,"The selected project file is unavailable under the current approval policy.")
            recent_files=db.execute("""SELECT f.* FROM chat_files f WHERE f.pid=%s AND f.thread_id=%s AND EXISTS(SELECT 1 FROM messages m, jsonb_array_elements(m.files) a WHERE m.thread_id=f.thread_id AND m.pid=f.pid AND a->>'id'=f.id) ORDER BY f.created DESC LIMIT 4""",(pid,tid)).fetchall()
            if not p.approved_only:
                available={f['id']:f for f in recent_files}
                available.update({f['id']:f for f in files})
                extracts=[dict(id=f["id"]+'.'+str(i),sid=f['id'],title=f['name'],location=loc,body=text,state='draft',kind='attachment',position=i) for f in available.values() for i,(loc,text) in enumerate(f['parts'],1)]
                if extracts:
                    selected=select_context(extracts,data.body,history,min(4,p.context_passages))
                    refs=(selected+refs if files else refs[:max(1,p.context_passages-2)]+selected)[:p.context_passages]
                activity=db.execute("""SELECT e.service,e.remote_id,e.record,e.happened FROM delivery_events e JOIN project_links l ON l.pid=e.pid AND l.service=e.service WHERE e.pid=%s AND ((e.service='Jira' AND %s AND l.workspace=%s) OR (e.service='Slack' AND %s AND l.workspace=%s)) ORDER BY happened DESC LIMIT 80""",(pid,bool(p.sync_jira and secret(db,'Jira')),p.jira_site,bool(p.sync_slack and secret(db,'Slack')),p.slack_team)).fetchall()
                from .domain import retrieve
                records=[dict(id=a['service']+'-'+a['remote_id'],title=a['service']+' activity',state='recorded',kind='activity',body=json.dumps(a['record'])) for a in activity]
                hits=retrieve(records,data.body,min(2,max(0,p.context_passages-1)))
                if hits:refs=refs[:p.context_passages-len(hits)]+hits
            elif files:raise HTTPException(409,"Approved-only mode excludes conversation attachments. Add the file to project knowledge and approve it first.")
            if pinned:
                chosen=select_context(pinned,data.body,history,max(1,p.context_passages//2))
                used={r['id'] for r in chosen}
                refs=(chosen+[r for r in refs if r['id'] not in used])[:p.context_passages]
            past=db.execute("SELECT id,title,summary FROM chat_threads WHERE pid=%s AND owner_id=%s AND id<>%s AND NOT archived AND summary<>'' ORDER BY updated DESC LIMIT 40",(pid,user,tid)).fetchall()
            from .domain import retrieve
            memory=retrieve([dict(id=x['id'],state='draft',title=x['title'],body=x['summary']) for x in past],data.body,2)
            status=db.execute("SELECT processing,state,count(*) AS count FROM sources WHERE pid=%s GROUP BY processing,state",(pid,)).fetchall()
            prompt=data.body+"\nDocument processing counts (metadata): "+json.dumps(status,default=str)
            if not p.approved_only and p.history_messages:prompt+="\nConversation memory (unverified): "+(t['summary']+ '\n'+'\n'.join(m['body'][:650] for m in memory))[:4800]
            if not p.approved_only and p.history_messages:
                old=db.execute("""SELECT id,role,body FROM messages WHERE pid=%s AND thread_id=%s AND id NOT IN (SELECT id FROM messages WHERE pid=%s AND thread_id=%s ORDER BY created DESC,id DESC LIMIT %s) AND to_tsvector('simple',body) @@ plainto_tsquery('simple',%s) ORDER BY created DESC LIMIT 40""",(pid,tid,pid,tid,p.history_messages,data.body)).fetchall()
                related=retrieve([dict(id=m['id'],title=m['role'],body=m['body'][:900],state='recorded') for m in old],data.body,2)
                prompt+="\nEarlier matching conversation excerpts (unverified): "+json.dumps([r['body'] for r in related])
            if not refs:prompt+="\nNo eligible project passage was retrieved. Explain the processing or approval status when relevant."
        async def events():
            loop=asyncio.get_running_loop();queue=asyncio.Queue();stopped=threading.Event()
            def send(kind,value):loop.call_soon_threadsafe(queue.put_nowait,dict(type=kind,value=value))
            def emit(value):
                if stopped.is_set():raise RuntimeError("Stopped")
                send("delta",value)
            def run():
                try:
                    answer,model,used=ask(user,pid,"answer",prompt,refs,history,emit=emit)
                    if stopped.is_set():return
                    cites=valid_citations(answer,used)
                    with database() as db:
                        current=thread(db,pid,tid,user,True)
                        if current['revision']!=data.revision or current['archived']:raise HTTPException(409,"Another turn changed this chat. Refresh and retry.")
                        save(db,'user',data.body,[],attachments);save(db,'assistant',answer,cites,[])
                        older=db.execute("SELECT role,body,refs FROM messages WHERE pid=%s AND thread_id=%s ORDER BY created DESC,id DESC LIMIT 30",(pid,tid)).fetchall()[::-1]
                        db.execute("UPDATE chat_threads SET title=CASE WHEN title='New chat' THEN %s ELSE title END,summary=%s,updated=now(),revision=revision+1 WHERE id=%s",(data.body[:70],(digest(older[:-6] or older,current["summary"])),tid))
                        db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES(%s,%s,'chat.answered',%s)",(user,pid,model))
                    send("done",model)
                except Exception as e:send("error",e.detail if isinstance(e,HTTPException) else "Chat generation failed. Check the connection and retry.")
                finally:send("end","")
            task=asyncio.create_task(asyncio.to_thread(run))
            try:
                yield '{"type":"start"}\n'
                while True:
                    event=await queue.get()
                    if event['type']=='end':break
                    yield json.dumps(event)+'\n'
            finally:stopped.set()
        return StreamingResponse(events(),media_type="application/x-ndjson",headers={"X-Accel-Buffering":"no"})
    return r
