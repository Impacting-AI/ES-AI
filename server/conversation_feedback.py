"""Conversation feedback is evidence for review. Only explicit admin decisions apply it."""
import json
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from .chat import thread
from .db import database
from .agent_store import settings,save
from .agent_policy import may_admin

Category=Literal["Response style","Project knowledge","Retrieval","Planning","Reasoning"]
class Correction(BaseModel):
    thread_id:str
    message_ids:list[str]=Field(default_factory=list,max_length=300)
    entire:bool=False
    category:Category
    body:str=Field(min_length=1,max_length=3000)
class Decision(BaseModel):
    action:Literal["save","approve","reject","rollback"]
    text:str=Field(min_length=1,max_length=3000)
    version:int
    global_style:bool=False
    preference:Literal["Concise","Balanced","Detailed"]="Concise"

JOIN="""SELECT i.*,f.body AS correction,f.thread_id,f.message_ids FROM improvement_proposals i
JOIN feedback f ON f.id=i.id AND f.pid=i.pid WHERE f.thread_id IS NOT NULL AND i.pid=%s"""

def snapshot(db,key):
    db.execute("""INSERT INTO feedback_versions(proposal_id,version,body,analysis,status,applied,actor) SELECT id,edit_version,policy_text,analysis,status,applied,coalesce(reviewer,uid) FROM improvement_proposals WHERE id=%s ON CONFLICT DO NOTHING""",(key,))

def router(member,admin_user,access,ask,evidence,add_source):
    r=APIRouter(prefix="/api/projects/{pid}/conversation-feedback")
    @r.get("")
    def listing(pid:str,user=Depends(member)):
        with database() as db:
            return db.execute(JOIN+" AND (i.uid=%s OR %s) ORDER BY i.created DESC LIMIT 100",(pid,user,may_admin(access(user)))).fetchall()

    @r.get("/{key}/evidence")
    def details(pid:str,key:str,user=Depends(member)):
        with database() as db:
            row=db.execute(JOIN+" AND i.id=%s AND (i.uid=%s OR %s)",(pid,key,user,may_admin(access(user)))).fetchone()
            if not row:raise HTTPException(404,"Feedback unavailable.")
            turns=db.execute("SELECT id,role,body FROM messages WHERE pid=%s AND thread_id=%s AND id=ANY(%s) ORDER BY created,id",(pid,row['thread_id'],row['message_ids'])).fetchall()
            history=db.execute("SELECT * FROM feedback_versions WHERE proposal_id=%s ORDER BY version DESC",(key,)).fetchall()
            return {"messages":turns,"versions":history}
    @r.post("")
    def submit(pid:str,data:Correction,user=Depends(member)):
        if not data.body.strip():raise HTTPException(422,"Enter a correction.")
        with database() as db:
            thread(db,pid,data.thread_id,user)
            rows=db.execute("SELECT id,role FROM messages WHERE pid=%s AND thread_id=%s ORDER BY created,id",(pid,data.thread_id)).fetchall()
            chosen=set(data.message_ids)
            if chosen-{m['id'] for m in rows}:raise HTTPException(422,"Message is outside the selected conversation.")
            selected=[m for m in rows if data.entire or m["id"] in chosen]
            if not selected:raise HTTPException(422,"Select messages or the entire conversation.")
            key=str(uuid4());ids=[m["id"] for m in selected]
            db.execute("INSERT INTO feedback(id,pid,uid,target,category,body,thread_id,message_ids) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",(key,pid,user,ids[0],data.category,data.body.strip(),data.thread_id,json.dumps(ids)))
            db.execute("INSERT INTO improvement_proposals(id,pid,uid,revision,policy_text,category,evidence) VALUES(%s,%s,%s,0,%s,%s,%s::jsonb)",(key,pid,user,data.body.strip(),data.category,json.dumps(ids)))
            snapshot(db,key)
            db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES(%s,%s,'feedback.submitted',%s)",(user,pid,key))
        return {"id":key}

    @r.post("/{key}/analyse")
    def analyse(pid:str,key:str,user=Depends(member)):
        with database() as db:
            row=db.execute(JOIN+" AND i.id=%s AND (i.uid=%s OR %s)",(pid,key,user,may_admin(access(user)))).fetchone()
            if not row or row['status']!='draft':raise HTTPException(409,"Draft unavailable.")
            # Only selected turns and their preceding question are disclosed to the reviewer/model.
            messages=db.execute("""WITH turns AS (SELECT id,role,body,citations,created,lag(id) OVER(ORDER BY created,id) AS prev FROM messages WHERE pid=%s AND thread_id=%s)
            SELECT id,role,left(body,1400) AS body,citations FROM turns WHERE id=ANY(%s) OR id IN (SELECT prev FROM turns WHERE role='assistant' AND id=ANY(%s)) ORDER BY created,id""",(pid,row['thread_id'],row['message_ids'],row['message_ids'])).fetchall()
            _,p=settings(db)
            refs=evidence(db,pid,row['correction'],chat=True)
            states=db.execute("SELECT processing,state,count(*) AS n FROM sources WHERE pid=%s GROUP BY processing,state",(pid,)).fetchall()
        sample=messages if len(messages)<=12 else messages[:6]+messages[-6:]
        turns=[dict(role=m['role'],text=m['body'][:900],citations=[{'id':c.get('id'),'excerpt':c.get('body','')[:220]} for c in m['citations'][:3]]) for m in sample]
        prompt=("Review feedback as a hypothesis. Examine quoted messages, citations, project evidence and current agent instructions. "
                "Distinguish demonstrated errors from possible causes. For retrieval, assess readiness, approval filters and cited passages. "
                "Return JSON with analysis (what went wrong and evidence) and proposal (specific corrected behaviour or investigative action). "
                "For Project knowledge, propose the precise factual statement for a draft record and identify any missing approval evidence. For Planning or Reasoning, propose a reusable project-specific recommendation. For Response style, write a presentation rule. For Retrieval, propose a diagnostic check rather than a prompt change. Never execute changes or broaden a project correction. Data: "+json.dumps(dict(category=row['category'],correction=row['correction'],turns=turns,total_turns=len(messages),processing=states,instructions=p.instructions),default=str,ensure_ascii=False))
        result,_,_=ask(user,pid,'feedback',prompt,refs)
        try:
            obj=json.loads(result.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip())
            analysis=obj['analysis'];proposal=obj['proposal']
            if not all(isinstance(x,str) and x.strip() for x in (analysis,proposal)):raise ValueError()
        except (ValueError,KeyError,TypeError):raise HTTPException(422,"Model returned an unreadable proposal. Feedback remains saved.")
        with database() as db:
            if not db.execute("UPDATE improvement_proposals SET analysis=%s,policy_text=%s,edit_version=edit_version+1,reviewer=%s,updated=now() WHERE id=%s AND pid=%s AND status='draft' AND edit_version=%s",(analysis[:4000],proposal[:3000],user,key,pid,row['edit_version'])).rowcount:raise HTTPException(409,"Proposal changed during analysis.")
            snapshot(db,key)
            db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES(%s,%s,'feedback.analysed',%s)",(user,pid,key))
        return {"saved":True}

    @r.post("/{key}/decision")
    def decide(pid:str,key:str,data:Decision,user=Depends(member),admin=Depends(admin_user)):
        with database() as db:
            row=db.execute(JOIN+" AND i.id=%s FOR UPDATE OF i",(pid,key)).fetchone()
            if not row or row['edit_version']!=data.version:raise HTTPException(409,"Proposal changed. Reload before reviewing.")
            text=data.text.strip()
            if not text:raise HTTPException(422,"Enter the proposed correction.")
            applied=row['applied'];category=row['category']
            if data.action=="rollback":
                if row['status']!='approved':raise HTTPException(409,"Only approved changes can be rolled back.")
                if applied.get('scope')=='agent':
                    rev,p=settings(db,True)
                    if rev!=applied['revision']:raise HTTPException(409,"Agent settings changed. Review the saved configuration history.")
                    save(db,user,p.model_copy(update={'response_preference':applied['previous']}),rev)
                if applied.get('source'):
                    db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE",(pid,))
                    if not db.execute("UPDATE sources SET state='superseded' WHERE id=%s AND pid=%s AND state IN ('draft','approved')",(applied['source'],pid)).rowcount:raise HTTPException(409,"The knowledge version has already changed.")
                status='rolled back';text=row['policy_text']
            else:
                if row['status']!='draft':raise HTTPException(409,"Proposal has already been reviewed.")
                status={'approve':'approved','save':'draft','reject':'rejected'}[data.action]
                if data.action=='save' and category=='Response style':
                    applied={'proposed_global':data.global_style,'preference':data.preference}
                if status=='approved':
                    if data.global_style and category!='Response style':raise HTTPException(422,"Only a response preference may be applied globally.")
                    applied={'scope':'project','type':category}
                    if data.global_style:
                        rev,p=settings(db,True)
                        applied={'scope':'agent','previous':p.response_preference,'preference':data.preference,'revision':save(db,user,p.model_copy(update={'response_preference':data.preference}),rev)}
                    elif category=='Project knowledge':
                        applied['source']=add_source(db,pid,"Reviewed correction · "+text[:65],"Proposed scope change","Conversation feedback",key,None,None,text)
                    elif category=='Retrieval':
                        applied['task']='Retrieval investigation approved; verify indexing and source selection.'
            db.execute("UPDATE improvement_proposals SET status=%s,policy_text=%s,reviewer=%s,applied=%s::jsonb,edit_version=edit_version+1,updated=now() WHERE id=%s",(status,text,user,json.dumps(applied),key))
            snapshot(db,key)
            db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES(%s,%s,%s,%s)",(user,pid,'feedback.'+data.action,key))
        return {"status":status,"applied":applied}
    return r
