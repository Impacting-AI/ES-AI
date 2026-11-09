from .model_options import model_config
from .chat_sources import chat_evidence,cited_sources,clean_text,public_messages,VisibleStream
from .conversation import plan_turn, ROUTER
import hashlib
import math
import io
import json
import os
import secrets
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from contextlib import asynccontextmanager
from .migrate import migrate, VERSION
from .chat_errors import chat_error

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .connections_api import router as connections_router
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from pypdf import PdfReader

from .body_limit import BodyLimit
from .db import database
from .ingest import index_source
from .knowledge import select_context,project_passages,historical_request,historical_context
from .imports import parse_export
from .review_rules import suggested_instruction
from .transport import ServiceFailure,retry_delay
from .domain import chunks, password_matches, retrieve, working_schedule
from .models import PROVIDERS, generate, POLICY
from .agent_store import settings as agent_settings, save as save_policy, secret
from .agent_policy import permitted,reserve_estimate,may_admin,may_edit
from .agent_api import router as agent_router
from .activity import router as activity_router
from .reporting import router as reporting_router

@asynccontextmanager
async def lifespan(app):
    migrate()
    yield


app = FastAPI(lifespan=lifespan,title="PM AI ES", docs_url=None, redoc_url=None)
app.add_middleware(BodyLimit)
PUBLIC = os.environ["PUBLIC_ORIGIN"].rstrip("/")
META = "id,title,category,origin,description,state,original,family,version,created,processing,processing_error"


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    # Validation errors must never reflect a submitted password, token or request body.
    return JSONResponse(status_code=422,content={"detail":[{"loc":list(x["loc"]),"msg":x["msg"]} for x in exc.errors()]})

@app.get("/api/health")
def health():
    try:
        with database() as db:
            row=db.execute("SELECT version FROM pm_schema_version WHERE id=1").fetchone()
            if not row or row["version"] != VERSION:raise ValueError()
        return {"backend":"online","database":"ready"}
    except Exception:raise HTTPException(503,"Database unavailable or schema migration required.")


def ident(): return str(uuid4())


def audit(db, uid, pid, action, subject):
    db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES (%s,%s,%s,%s)",(uid,pid,action,subject))


@app.middleware("http")
async def boundary(request: Request, call_next):
    if request.method not in {"GET","HEAD","OPTIONS"} and request.headers.get("origin") != PUBLIC and request.url.path not in {"/api/hooks/Jira","/api/hooks/Slack"}:
        return Response("Origin rejected",status_code=403)
    try:
        response = await call_next(request)
    except Exception as exc:
        route = getattr(request.scope.get("route"), "path", "")
        if not route.startswith("/api/projects/{pid}/chats"):
            raise
        response = JSONResponse(status_code=500, content={"detail": chat_error(route, exc)})
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; object-src 'none'"
    return response


def uid(request: Request):
    token = hashlib.sha256(request.cookies.get("pm_session","").encode()).hexdigest()
    with database() as db:
        row = db.execute("SELECT uid FROM sessions WHERE token=%s AND expires>%s",(token,int(time.time()))).fetchone()
    if not row: raise HTTPException(401,"Please sign in.")
    return row["uid"]


def access(user):
    with database() as db:
        account=db.execute("SELECT platform_role,agent_access FROM users WHERE id=%s",(user,)).fetchone()
    if not account or not account["agent_access"]:raise HTTPException(403,"PM AI ES access is disabled for this account.")
    return account["platform_role"]


def admin_user(user=Depends(uid)):
    if not may_admin(access(user)):raise HTTPException(403,"Administrator access is required.")
    return user


def editor_user(user=Depends(uid)):
    if not may_edit(access(user)):raise HTTPException(403,"Project manager access is required.")
    return user


@app.get("/api/session")
def current_session(user=Depends(uid)):
    role=access(user)
    return {"role":role,"can_edit":may_edit(role),"admin":may_admin(role)}


def member(pid: str, request: Request, user=Depends(uid)):
    role=access(user)
    if request.method not in {"GET","HEAD"} and not may_edit(role):raise HTTPException(403,"This account has view access.")
    with database() as db:
        row = db.execute("SELECT 1 FROM members m JOIN projects p ON m.pid=p.id WHERE m.uid=%s AND m.pid=%s AND NOT p.archived",(user,pid)).fetchone()
    if not row: raise HTTPException(404,"Project unavailable.")
    return user


def throttle(key, limit, seconds):
    now = int(time.time())
    with database() as db:
        row = db.execute("""INSERT INTO attempts VALUES (%s,%s,1) ON CONFLICT(bucket) DO UPDATE SET
        count=CASE WHEN attempts.began<= %s THEN 1 ELSE attempts.count+1 END,
        began=CASE WHEN attempts.began<= %s THEN excluded.began ELSE attempts.began END RETURNING count""",
        (key,now,now-seconds,now-seconds)).fetchone()
    if row["count"] > limit: raise HTTPException(429,"Try again later.")


class Login(BaseModel):
    login: str = Field(max_length=254)
    password: str = Field(max_length=512)


@app.post("/api/login")
def login(data: Login, request: Request, response: Response):
    name = data.login.strip().lower()
    throttle("ip:"+request.client.host,30,900)
    throttle("login:"+hashlib.sha256(name.encode()).hexdigest(),10,900)
    with database() as db:
        user = db.execute("SELECT id,password,agent_access FROM users WHERE login=%s FOR UPDATE",(name,)).fetchone()
        if not user or not password_matches(data.password,user["password"]): raise HTTPException(401,"Sign-in failed.")
        if not user["agent_access"]:raise HTTPException(403,"PM AI ES access is disabled for this account.")
        token = secrets.token_urlsafe(40)
        db.execute("INSERT INTO sessions VALUES (%s,%s,%s)",(hashlib.sha256(token.encode()).hexdigest(),user["id"],int(time.time())+28800))
        audit(db,user["id"],None,"login",name)
    response.set_cookie("pm_session",token,httponly=True,secure=PUBLIC.startswith("https://"),samesite="strict",max_age=28800)
    return {"signed_in":True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    with database() as db:
        db.execute("DELETE FROM sessions WHERE token=%s",(hashlib.sha256(request.cookies.get("pm_session","").encode()).hexdigest(),))
    response.delete_cookie("pm_session")
    return {"signed_in":False}


class Project(BaseModel):
    head:str | None=Field(default=None,max_length=150)
    industry:str | None=Field(default=None,max_length=150)
    stack:str | None=Field(default=None,max_length=300)
    start:date | None=None
    target:date | None=None
    status:Literal["Active","On hold","Completed"] | None=None
    @model_validator(mode="after")
    def dates(self):
        if self.start and self.target and self.target<self.start:raise ValueError("Target precedes project start.")
        return self
    def metadata(self):
        return self.model_dump(mode="json",exclude={"name","client"},exclude_unset=True)
    expertise:str | None=Field(default=None,max_length=1500)
    name: str = Field(min_length=1,max_length=180)
    client: str = Field(min_length=1,max_length=180)


@app.get("/api/projects")
def projects(user=Depends(uid)):
    access(user)
    with database() as db:
        return db.execute("""SELECT p.*, (SELECT count(*) FROM sources s WHERE s.pid=p.id) AS sources,
        (SELECT count(*) FROM plans t WHERE t.pid=p.id AND t.state='draft') AS drafts
        ,(SELECT count(*) FROM agent_actions a WHERE a.pid=p.id AND a.status='draft') AS approvals
        ,(SELECT count(*) FROM (SELECT DISTINCT ON (record->>'issue') record FROM mapped_delivery_events WHERE pid=p.id AND service='Jira' ORDER BY record->>'issue',happened DESC) latest WHERE record->>'due'<to_char(current_date,'YYYY-MM-DD') AND lower(coalesce(nullif(record->>'status_group',''),record->>'status')) NOT IN ('done','closed','resolved')) AS overdue
        ,(SELECT max(happened) FROM mapped_delivery_events WHERE pid=p.id) AS latest_activity
        ,(SELECT config->>'frequency' FROM report_rules WHERE pid=p.id) AS report_frequency
        FROM projects p JOIN members m ON p.id=m.pid WHERE m.uid=%s AND NOT p.archived ORDER BY p.created DESC""",(user,)).fetchall()


@app.post("/api/projects")
def new_project(data: Project,user=Depends(editor_user)):
    if not data.name.strip() or not data.client.strip(): raise HTTPException(422,"Enter a project and client name.")
    pid = ident()
    with database() as db:
        db.execute("INSERT INTO projects(id,name,client,profile) VALUES (%s,%s,%s,%s::jsonb)",(pid,data.name.strip(),data.client.strip(),json.dumps(data.metadata())))
        db.execute("INSERT INTO members VALUES (%s,%s)",(pid,user))
        audit(db,user,pid,"project.created",pid)
    return {"id":pid}


@app.patch("/api/projects/{pid}")
def edit_project(pid:str,data:Project,user=Depends(member)):
    if not data.name.strip() or not data.client.strip():raise HTTPException(422,"Project and client names are required.")
    with database() as db:
        db.execute("UPDATE projects SET name=%s,client=%s,profile=profile || %s::jsonb WHERE id=%s",(data.name.strip(),data.client.strip(),json.dumps(data.metadata()),pid))
        audit(db,user,pid,"project.updated",pid)
    return {"id":pid}

@app.delete("/api/projects/{pid}")
def archive_project(pid:str,confirm:str,user=Depends(member)):
    with database() as db:
        if not db.execute("UPDATE projects SET archived=true WHERE id=%s AND name=%s",(pid,confirm)).rowcount:raise HTTPException(409,"Enter the current project name to archive it.")
        audit(db,user,pid,"project.archived",pid)
    return {"archived":True}


@app.get("/api/projects/{pid}/workspace")
def workspace(pid:str,user=Depends(member)):
    with database() as db:
        return dict(sources=db.execute(f"SELECT {META} FROM sources WHERE pid=%s ORDER BY created DESC",(pid,)).fetchall(),
                    messages=public_messages(db.execute("SELECT m.* FROM messages m LEFT JOIN chat_threads t ON t.id=m.thread_id AND t.pid=m.pid WHERE m.pid=%s AND (t.owner_id IS NULL OR t.owner_id=%s) ORDER BY m.created,m.id",(pid,user)).fetchall()),
                    plans=db.execute("SELECT * FROM plans WHERE pid=%s ORDER BY created DESC",(pid,)).fetchall(),
                    audit=db.execute("SELECT action,subject,uid,created FROM audit WHERE pid=%s ORDER BY id DESC LIMIT 150",(pid,)).fetchall())


def add_source(db,pid,title,category,origin,description,original,content,body,family=None):
    sid = ident()
    version = 1
    if family:
        db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE",(pid,))
        last = db.execute("SELECT max(version) AS v FROM sources WHERE pid=%s AND family=%s",(pid,family)).fetchone()["v"]
        if not last: raise HTTPException(404,"Version family unavailable.")
        version = last+1
    db.execute("""INSERT INTO sources(id,pid,title,category,origin,description,original,content,family,version)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(sid,pid,title,category,origin,description,original,content,family or sid,version))
    for i,part in enumerate(chunks(body)):
        db.execute("INSERT INTO passages(id,pid,sid,position,body) VALUES (%s,%s,%s,%s,%s)",(f"{sid}.{i+1}",pid,sid,i+1,part))
    return sid


@app.post("/api/projects/{pid}/files")
def upload(pid:str,file:UploadFile=File(), title:str=Form(max_length=240),category:str=Form(max_length=100),origin:str=Form(max_length=200),description:str=Form(default="",max_length=2000),family:str=Form(default=""),user=Depends(member)):
    raw = file.file.read(5*1024**2+1)
    if len(raw)>5*1024**2: raise HTTPException(413,"Maximum file size is 5 MiB.")
    name = file.filename or "upload"
    with database() as db:
        sid=add_source(db,pid,title.strip() or name,category,origin,description,name,raw,"",family or None)
        db.execute("UPDATE sources SET processing='Uploaded' WHERE id=%s",(sid,))
        audit(db,user,pid,"document.uploaded",sid)
    return run_index(pid,sid)

def run_index(pid,sid):
    with database() as db:
        if not db.execute("UPDATE sources SET processing='Processing' WHERE pid=%s AND id=%s AND content IS NOT NULL",(pid,sid)).rowcount:raise HTTPException(404,"Original unavailable.")
    status,error=index_source(pid,sid)
    return {"id":sid,"indexed":status=="Ready","processing":status,"error":error}

@app.post("/api/projects/{pid}/sources/{sid}/retry")
def retry_source(pid:str,sid:str,user=Depends(member)):
    return run_index(pid,sid)

@app.post("/api/projects/{pid}/chat-import")
def import_chat(pid:str,file:UploadFile=File(),user=Depends(member)):
    raw=file.file.read(1024**2+1)
    if len(raw)>1024**2:raise HTTPException(413,"Maximum conversation export size is 1 MiB.")
    try:platform,body,digest=parse_export(raw)
    except (ValueError,UnicodeError):raise HTTPException(422,"Invalid conversation export. Check the documented JSON format.")
    with database() as db:
        db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE",(pid,))
        previous=db.execute("SELECT sid FROM chat_imports WHERE pid=%s AND digest=%s",(pid,digest)).fetchone()
        if previous:return {"id":previous["sid"],"duplicate":True}
        sid=add_source(db,pid,file.filename or "Conversation","Conversation export",platform,"Imported in original order",file.filename,raw,body)
        db.execute("INSERT INTO chat_imports VALUES (%s,%s,%s)",(pid,digest,sid))
        audit(db,user,pid,"conversation.imported",sid)
    return {"id":sid,"duplicate":False}


class Metadata(BaseModel):
    title:str=Field(min_length=1,max_length=240)
    description:str=Field(max_length=2000)


@app.patch("/api/projects/{pid}/sources/{sid}")
def rename(pid:str,sid:str,data:Metadata,user=Depends(member)):
    with database() as db:
        if not db.execute("UPDATE sources SET title=%s,description=%s WHERE pid=%s AND id=%s",(data.title,data.description,pid,sid)).rowcount: raise HTTPException(404)
        audit(db,user,pid,"metadata.edited",sid)
    return {"id":sid}


@app.get("/api/projects/{pid}/sources/{sid}")
def inspect(pid:str,sid:str,user=Depends(member)):
    with database() as db:
        row=db.execute(f"SELECT {META} FROM sources WHERE pid=%s AND id=%s",(pid,sid)).fetchone()
        if not row: raise HTTPException(404)
        return dict(row,passages=db.execute("SELECT id,body,location FROM passages WHERE pid=%s AND sid=%s ORDER BY position",(pid,sid)).fetchall())


@app.post("/api/projects/{pid}/sources/{sid}/approve")
def approve(pid:str,sid:str,user=Depends(member)):
    with database() as db:
        db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE",(pid,))
        src=db.execute("SELECT family,state,version FROM sources WHERE pid=%s AND id=%s",(pid,sid)).fetchone()
        if not src or src["state"]!="draft": raise HTTPException(409,"Only drafts can be approved.")
        current=db.execute("SELECT id,version FROM sources WHERE pid=%s AND family=%s AND state='approved'",(pid,src["family"])).fetchone()
        if current and current["version"] >= src["version"]: raise HTTPException(409,"A later version is already approved.")
        if current:
            db.execute("UPDATE sources SET state='superseded' WHERE pid=%s AND id=%s",(pid,current["id"]))
            audit(db,user,pid,"superseded.by."+sid,current["id"])
        db.execute("UPDATE sources SET state='approved' WHERE pid=%s AND id=%s",(pid,sid))
        audit(db,user,pid,"source.approved",sid)
    return {"state":"approved"}


class Message(BaseModel):
    body:str=Field(min_length=1,max_length=6000)
    respond:bool=True
    category:str=Field(default="Project note",max_length=100)


def evidence(db,pid,question,chat=False,history=(),breadth=None,original=None):
    _,p=agent_settings(db)
    rows=project_passages(db,pid,p.approved_only)
    if not chat:return retrieve(rows,question,p.context_passages)
    refs=select_context(rows,question,history,p.context_passages,breadth=breadth)
    if not p.approved_only and historical_request(original or question):
        past=historical_context(db,pid,original or question)
        if past:
            count=min(len(past),max(1,p.context_passages//3))
            refs=refs[:p.context_passages-count]+past[:count]
    return refs


def ask(user,pid,action,prompt,refs,history=(),emit=None,intent=None,tid=None,cancelled=None,question=None):
    run=ident()
    question=question if question is not None else prompt
    with database() as db:
        rev,p=agent_settings(db)
        try: permitted(p,"answer" if action in {"feedback","route"} else action)
        except ValueError as e: raise HTTPException(403,str(e))
        if not p.model: raise HTTPException(409,"Open Agents → AI model and select a model.")
        if p.approved_only:
            refs=[r for r in refs if r["state"]=="approved"]
            # Conversation history is labelled non-authoritative in the model policy.
        if action in {"answer","feedback"}:
            refs=refs[:p.context_passages]
            history=history[-p.history_messages:] if p.history_messages else []
        if action not in {"answer","route"} or (intent and "profile" in intent.sources):
            project=db.execute("SELECT name,profile FROM projects WHERE id=%s",(pid,)).fetchone()
            profile={"project_name":project["name"],"profile":project["profile"]}
            prompt += "\nProject profile and reviewed guidance (context only): "+json.dumps(profile)
        from .response_style import chat_style
        instructions=p.instructions
        if action=="answer":instructions+="\n"+chat_style(p.response_preference)
        categories=["Planning"] if action=="plan" else ["Reasoning","Response style"] if action=="answer" else []
        if action=="route":instructions=ROUTER
        if intent and not intent.sources:categories=[]
        rules=db.execute("""SELECT i.policy_text FROM improvement_proposals i JOIN feedback f ON f.id=i.id AND f.pid=i.pid WHERE i.pid=%s AND i.status='approved' AND i.applied->>'scope'='project' AND i.category=ANY(%s) ORDER BY i.updated DESC LIMIT 8""",(pid,categories)).fetchall() if categories else []
        if rules:prompt+="\nAdministrator-reviewed project recommendations (context only): "+json.dumps([r["policy_text"][:600] for r in rules])
        if intent and intent.kind in {"general","social"}:history=[]
        if intent and intent.kind in {"project","overview"}:
            instructions+=" Ground project facts in the supplied evidence. Briefly mention a missing fact only if the answer depends on it."
        if intent and intent.kind=="overview":
            instructions+=" Introduce the active project by name and purpose. Explain the main workflow and the milestones or latest decisions supported by the sources. Distinguish planned work from confirmed delivery. Combine overlapping passages. Skip evidence inventories, audit headings and unrelated unknowns."
        options=[(p.provider,p.model,secret(db,p.provider))]
        if p.fallback_provider:
            options.append((p.fallback_provider,p.fallback_model,secret(db,p.fallback_provider)))
        db.execute("INSERT INTO agent_runs(id,pid,uid,action,status,revision) VALUES (%s,%s,%s,%s,'running',%s)",(run,pid,user,action,rev))
    raise_error = ""
    attempts = []
    result = None
    status = 409
    started = False
    def on_text(value):
        nonlocal started
        started = True
        emit(value)
    if action in {"answer","route"}:
        history=public_messages([dict(m) for m in history])
    model_refs=chat_evidence(refs) if action=="answer" else refs
    visible=VisibleStream(on_text) if emit and action=="answer" else None
    for option_index,(provider, model, key) in enumerate(options):
        if raise_error or result:
            break
        if not key:
            raise_error = "Configure the selected provider credential in AI settings."
            break
        config,output_limit,temperature=model_config(p,bool(option_index))
        config["question"]=question
        for index in range(2):
            if visible:visible.pending=""
            record = dict(provider=provider, model=model, attempt=index+1, status="failed")
            attempts.append(record)
            start = time.monotonic()
            stage = "usage reservation"
            try:
                if cancelled and cancelled():
                    raise ServiceFailure("Generation stopped.",499)
                throttle("ai:"+user,p.hourly_calls,3600)
                usage_id=ident()
                prompt_bytes=len(json.dumps([prompt,refs,history,instructions,POLICY,p.language],default=str).encode())+256
                if p.monthly_budget and output_limit is None:
                    raise ServiceFailure("Set maximum output tokens to reserve usage against the monthly budget.",422)
                estimate=reserve_estimate(p.model_copy(update={"max_tokens":output_limit}),prompt_bytes)
                with database() as db:
                    db.execute("SELECT pg_advisory_xact_lock(507715)")
                    spent=db.execute("SELECT coalesce(sum(estimated_usd),0) AS total FROM agent_usage WHERE created>=date_trunc('month',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'").fetchone()["total"]
                    if p.monthly_budget and float(spent)+estimate>p.monthly_budget:
                        raise ServiceFailure("Monthly agent budget reached. Review the budget in AI settings.",429)
                    db.execute("INSERT INTO agent_usage(id,pid,provider,model,estimated_usd) VALUES (%s,%s,%s,%s,%s)",(usage_id,pid,provider,model,estimate))
                record["estimated_usd"]=estimate
                stage = "model response"
                text,input_tokens,output_tokens=generate(config,prompt,model_refs,history,secret=key,instructions=instructions,language=p.language,max_tokens=output_limit,temperature=temperature,emit=visible.write if visible else on_text if emit else None,diagnostics=record)
                if not text or not text.strip():
                    raise ServiceFailure("Model returned no answer. Check its output limit and configuration.",422)
                stage = "usage settlement"
                if input_tokens is not None and output_tokens is not None:
                    cost=(input_tokens*p.input_rate+output_tokens*p.output_rate)/1000000
                    record.update(input_tokens=input_tokens,output_tokens=output_tokens,estimated_usd=cost)
                    with database() as db:
                        db.execute("UPDATE agent_usage SET settled=true,input_tokens=%s,output_tokens=%s,estimated_usd=%s WHERE id=%s",(input_tokens,output_tokens,cost,usage_id))
                used_ids=record.pop("used_ids",None)
                if action=="answer":
                    used=cited_sources(text,refs,used_ids or [])
                    text=clean_text(text).strip()
                    if not text:raise ServiceFailure("The model returned only source references. Retry the question.",422)
                    if visible:visible.finish()
                else:
                    used=[r for r in refs if used_ids is None or r.get("id") in used_ids]
                record["status"]="success"
                result=(text,(provider+" / "+model) if option_index else model,used)
                break
            except ServiceFailure as exc:
                status=exc.code
                record["error"]=exc.category
                if not started and stage=="model response" and (exc.rejected or exc.category.startswith("Request exceeds the model input budget")):
                    with database() as db:
                        db.execute("UPDATE agent_usage SET settled=true,input_tokens=0,output_tokens=0,estimated_usd=0 WHERE id=%s",(usage_id,))
                    record.update(input_tokens=0,output_tokens=0,estimated_usd=0)
                if exc.request_id:record["request_id"]=exc.request_id
                if status==413 and index==0 and not started and exc.category.startswith("Model context") and (refs or history):
                    model_refs=model_refs[:max(1,len(model_refs)//2)]
                    history=history[-2:]
                    continue
                retry=exc.transient and not started and not (cancelled and cancelled())
                delay=retry_delay(exc,index,started,cancelled and cancelled())
                if delay is not None:
                    time.sleep(delay)
                    continue
                raise_error=exc.category
                if exc.retry_after:raise_error+=f". Retry after {math.ceil(min(exc.retry_after,86400))} seconds."
                if retry and option_index+1<len(options) and not exc.retry_after:
                    raise_error=""
                break
            except HTTPException as exc:
                status=exc.status_code
                raise_error="Hourly model-call limit reached. Retry after the hourly window resets." if status==429 else str(exc.detail)
                record["error"]=raise_error
                break
            except Exception as exc:
                status=502 if stage=="model response" else 503
                record["error"]=stage+" / "+type(exc).__name__
                raise_error=("The model returned an unreadable response." if stage=="model response" else "The request could not finish recording its usage.")+" Reference "+run+"."
                break
            finally:
                record.pop("used_ids",None)
                record["latency_ms"]=round((time.monotonic()-start)*1000)
    detail=(attempts[-1]["provider"]+" / "+attempts[-1]["model"]) if result else raise_error
    with database() as db:
        db.execute("UPDATE agent_runs SET status=%s,detail=%s,finished=now(),diagnostics=%s::jsonb WHERE id=%s",("success" if result else "failed",detail,json.dumps({"conversation":tid,"attempts":attempts}),run))
    if not result:raise HTTPException(status,raise_error)
    return result


@app.post("/api/projects/{pid}/messages")
def message(pid:str,data:Message,user=Depends(member)):
    with database() as db:
        if not data.respond:
            sid=add_source(db,pid,data.body[:70],data.category,"Manual entry","",None,None,data.body)
            audit(db,user,pid,"knowledge.saved",sid)
            return {"saved":sid}
        _,policy=agent_settings(db)
        history=db.execute("""SELECT role,left(body,1000) AS body FROM messages WHERE pid=%s AND (thread_id IS NULL OR thread_id='legacy-'||pid) AND created>coalesce((SELECT connections_changed FROM projects WHERE id=messages.pid),'-infinity') AND created>coalesce((SELECT max(created) FROM audit WHERE pid=%s AND action='source.approved'),'-infinity'::timestamptz) ORDER BY created DESC LIMIT %s""",(pid,pid,policy.history_messages)).fetchall()[::-1]
        history=history[-policy.history_messages:] if policy.history_messages else []
    intent=plan_turn(ask,user,pid,data.body,history)
    with database() as db:
        refs=evidence(db,pid,intent.query,True,history,breadth=intent.kind=="overview",original=data.body) if "documents" in intent.sources or (policy.approved_only and "activity" in intent.sources) else []
        if "activity" in intent.sources and not policy.approved_only:
            from .chat import activity_context
            matches = activity_context(db, pid, policy, intent.query)
            refs = refs[:policy.context_passages-len(matches)] + matches
    answer,model,refs=ask(user,pid,"answer",data.body,refs,history,intent=intent)
    with database() as db:
        legacy="legacy-"+pid
        db.execute("INSERT INTO chat_threads(id,pid,title) VALUES(%s,%s,'Earlier project chat') ON CONFLICT DO NOTHING",(legacy,pid))
        for role,body,links in [("user",data.body,[]),("assistant",answer,refs)]:
            db.execute("INSERT INTO messages(id,pid,thread_id,role,body,refs,citations,created) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,clock_timestamp())",(ident(),pid,legacy,role,body,json.dumps([r["id"] for r in links]),json.dumps(links)))
        audit(db,user,pid,"chat.answered",model)
    return {"answer":answer,"citations":refs}


@app.get("/api/projects/{pid}/search")
def search(pid:str,q:str,user=Depends(member)):
    with database() as db: return evidence(db,pid,q)


class Config(BaseModel):
    provider:str
    model:str=Field(min_length=1)


@app.get("/api/settings")
def settings(user=Depends(admin_user)):
    with database() as db:
        _,policy=agent_settings(db)
        return dict(selected={"provider":policy.provider,"model":policy.model},available={k:bool(secret(db,k)) for k in PROVIDERS})


@app.put("/api/settings")
def configure(data:Config,user=Depends(admin_user)):
    if data.provider not in PROVIDERS: raise HTTPException(422,"Unknown provider.")
    with database() as db:
        rev,p=agent_settings(db,True)
        try:save_policy(db,user,p.model_copy(update=data.model_dump()),rev)
        except ValueError as exc:raise HTTPException(422,str(exc))
    return {"saved":True}


@app.post("/api/projects/{pid}/plans")
def plan(pid:str,user=Depends(member)):
    with database() as db:
        refs=db.execute("""SELECT p.id,p.body,s.title,s.state FROM passages p JOIN sources s ON s.id=p.sid AND s.pid=p.pid WHERE p.pid=%s AND s.state='approved' ORDER BY s.created,p.position LIMIT 22""",(pid,)).fetchall()
        if not refs: raise HTTPException(409,"Approve an indexed scope before generating a plan.")
        if len(refs)>21: raise HTTPException(422,"Approved scope exceeds the single-pass planning limit. Multi-pass planning is required.")
    with database() as db:
        team=db.execute("SELECT name,role,skills,hours FROM project_staff WHERE pid=%s ORDER BY name LIMIT 80",(pid,)).fetchall()
    result,_,refs=ask(user,pid,"plan","Draft milestones, deliverables, epics, stories, tasks and subtasks in simple English. For each give instructions, acceptance criteria, effort in hours including review, proposed role and dependencies. Cite scope. Identify missing capacity and deadlines; leave unconfirmed dates and assignments open. Confirmed team and available hours per working day: "+json.dumps(team,default=str),refs)
    with database() as db:
        key=ident()
        db.execute("INSERT INTO plans(id,pid,content,scope_ids) VALUES (%s,%s,%s,%s)",(key,pid,result,json.dumps(sorted({r["id"].split(".")[0] for r in refs}))))
        audit(db,user,pid,"plan.drafted",key)
    return {"id":key}


class Review(BaseModel):
    content:str=Field(min_length=1,max_length=48000)
    decision:str=Field(pattern="^(draft|approved|rejected)$")
    previous:str=Field(max_length=48000)


@app.put("/api/projects/{pid}/plans/{key}")
def review(pid:str,key:str,data:Review,user=Depends(member)):
    with database() as db:
        if data.decision=="approved":
            db.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE",(pid,))
            plan=db.execute("SELECT scope_ids FROM plans WHERE id=%s AND pid=%s",(key,pid)).fetchone()
            current=db.execute("SELECT DISTINCT s.id FROM sources s JOIN passages p ON s.id=p.sid AND s.pid=p.pid WHERE s.pid=%s AND s.state='approved' ORDER BY s.id",(pid,)).fetchall()
            if not plan or json.loads(plan["scope_ids"]) != [s["id"] for s in current]:
                raise HTTPException(409,"Approved scope has changed. Generate a fresh plan.")
        changed=db.execute("UPDATE plans SET content=%s,state=%s WHERE pid=%s AND id=%s AND state='draft' AND content=%s",(data.content,data.decision,pid,key,data.previous)).rowcount
        if not changed: raise HTTPException(409,"Draft changed. Reload before reviewing.")
        audit(db,user,pid,"plan."+data.decision,key)
    return {"state":data.decision}


@app.get("/api/projects/{pid}/sources/{sid}/original")
def original(pid:str,sid:str,user=Depends(member)):
    with database() as db:
        row=db.execute("SELECT original,content FROM sources WHERE pid=%s AND id=%s",(pid,sid)).fetchone()
    if not row or row["content"] is None: raise HTTPException(404)
    return Response(bytes(row["content"]),media_type="application/octet-stream",headers={"Content-Disposition":"attachment; filename*=UTF-8''"+quote(row["original"],safe="")})


class Task(BaseModel):
    key:str=Field(min_length=1,max_length=100)
    owner:str=Field(min_length=1,max_length=100)
    hours:float=Field(gt=0,le=10000)
    depends_on:list[str]=Field(default_factory=list,max_length=100)


class Schedule(BaseModel):
    tasks:list[Task]=Field(min_length=1,max_length=100)
    capacities:dict[str,float]
    start:date
    target:date|None=None


@app.post("/api/projects/{pid}/schedule")
def schedule(pid:str,data:Schedule,user=Depends(member)):
    try: return working_schedule([t.model_dump() for t in data.tasks],data.capacities,data.start,data.target)
    except (ValueError,OverflowError) as e: raise HTTPException(422,str(e))


@app.get("/api/projects/{pid}/reports")
def report(pid:str,start:date,end:date,user=Depends(member)):
    if end<start or end-start>timedelta(days=366): raise HTTPException(422,"Select a period of up to one year.")
    first=datetime.combine(start,datetime.min.time(),timezone.utc)
    after=datetime.combine(end,datetime.min.time(),timezone.utc)+timedelta(days=1)
    with database() as db:
        events=db.execute("SELECT id,created,action,subject FROM audit WHERE pid=%s AND created>=%s AND created<%s ORDER BY created,id",(pid,first,after)).fetchall()
        delivery=db.execute("SELECT * FROM mapped_delivery_events WHERE pid=%s AND happened>=%s AND happened<%s ORDER BY happened",(pid,first,after)).fetchall()
    return {"period":[start,end],"events":events,"delivery":delivery,"verified_delivery":None}


class Feedback(BaseModel):
    target:str=Field(min_length=1,max_length=160)
    category:str=Field(min_length=1,max_length=80)
    body:str=Field(min_length=1,max_length=3000)


@app.post("/api/projects/{pid}/feedback")
def feedback(pid:str,data:Feedback,user=Depends(member)):
    with database() as db:
        target=db.execute("SELECT id FROM plans WHERE pid=%s AND id=%s UNION SELECT m.id FROM messages m LEFT JOIN chat_threads t ON t.id=m.thread_id AND t.pid=m.pid WHERE m.pid=%s AND m.id=%s AND m.role='assistant' AND (t.owner_id IS NULL OR t.owner_id=%s)",(pid,data.target,pid,data.target,user)).fetchone()
        if not target: raise HTTPException(404,"Output unavailable.")
        key=ident()
        db.execute("INSERT INTO feedback(id,pid,uid,target,category,body) VALUES (%s,%s,%s,%s,%s,%s)",(key,pid,user,data.target,data.category,data.body))
        revision=db.execute("SELECT coalesce((profile->>'revision')::int,0) AS revision FROM projects WHERE id=%s",(pid,)).fetchone()["revision"]
        db.execute("INSERT INTO improvement_proposals(id,pid,uid,revision,policy_text,category,evidence) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",(key,pid,user,revision,suggested_instruction(data.category),data.category,json.dumps([key,data.target])))
        audit(db,user,pid,"feedback.recorded",key)
    return {"id":key}


@app.get("/api/projects/{pid}/improvements")
def improvements(pid:str,user=Depends(member)):
    with database() as db:return db.execute("SELECT i.*,f.body AS correction,count(*) OVER(PARTITION BY lower(i.category)) AS occurrences FROM improvement_proposals i JOIN feedback f ON i.id=f.id AND i.pid=f.pid WHERE i.pid=%s AND f.thread_id IS NULL ORDER BY i.created DESC LIMIT 100",(pid,)).fetchall()

class Review(BaseModel):
    approve:bool
    evaluation:str=Field(min_length=4,max_length=1200)

@app.post("/api/projects/{pid}/improvements/{key}")
def review(pid:str,key:str,data:Review,user=Depends(member),admin=Depends(admin_user)):
    with database() as db:
        profile=db.execute("SELECT profile FROM projects WHERE id=%s FOR UPDATE",(pid,)).fetchone()["profile"]
        row=db.execute("SELECT * FROM improvement_proposals WHERE pid=%s AND id=%s AND status='draft' AND NOT EXISTS(SELECT 1 FROM feedback f WHERE f.id=improvement_proposals.id AND f.thread_id IS NOT NULL) FOR UPDATE",(pid,key)).fetchone()
        if not row:raise HTTPException(409,"Proposal already reviewed.")
        if data.approve:
            revision=profile.get("revision",0)
            if revision!=row["revision"]:raise HTTPException(409,"Project guidance changed. Submit fresh feedback for the current revision.")
            db.execute("UPDATE improvement_proposals SET prior_guidance=%s WHERE id=%s",(profile.get("guidance",""),key))
            profile.update(guidance=row["policy_text"],revision=revision+1,active_proposal=key)
            db.execute("UPDATE projects SET profile=%s::jsonb WHERE id=%s",(json.dumps(profile),pid))
        status="approved" if data.approve else "rejected"
        db.execute("UPDATE improvement_proposals SET status=%s,evaluation=%s,reviewer=%s WHERE id=%s",(status,data.evaluation,user,key))
        audit(db,user,pid,"feedback."+status,key)
    return {"status":status}

@app.post("/api/projects/{pid}/improvements/{key}/rollback")
def rollback_improvement(pid:str,key:str,user=Depends(member),admin=Depends(admin_user)):
    with database() as db:
        profile=db.execute("SELECT profile FROM projects WHERE id=%s FOR UPDATE",(pid,)).fetchone()["profile"]
        if profile.get("active_proposal")!=key:raise HTTPException(409,"Only the active proposal can be rolled back.")
        row=db.execute("SELECT prior_guidance FROM improvement_proposals WHERE id=%s AND pid=%s AND status='approved'",(key,pid)).fetchone()
        if not row:raise HTTPException(409,"Proposal unavailable.")
        profile.update(guidance=row["prior_guidance"] or "",revision=profile["revision"]+1,active_proposal=None)
        db.execute("UPDATE projects SET profile=%s::jsonb WHERE id=%s",(json.dumps(profile),pid))
        db.execute("UPDATE improvement_proposals SET status='rolled back' WHERE id=%s",(key,))
        audit(db,user,pid,"feedback.rollback",key)
    return {"saved":True}

from .conversation_feedback import router as feedback_router
app.include_router(feedback_router(member,admin_user,access,ask,evidence,add_source))
from .chat import router as chat_router
app.include_router(chat_router(member,ask,evidence,add_source))
app.include_router(connections_router(admin_user,throttle))
app.include_router(reporting_router(member))
app.include_router(activity_router(member))
app.include_router(agent_router(uid,admin_user,access,member,message,plan,ask))

static=Path(__file__).parent.parent/"dist"
if static.exists(): app.mount("/",StaticFiles(directory=static,html=True),name="frontend")
