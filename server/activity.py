"""Explicit project bindings and bounded read-only delivery activity imports."""
from datetime import datetime,timezone,timedelta
from typing import Literal
from uuid import uuid4
import json
import os
from .provider_hooks import authenticated,destination
from .transport import Client,ServiceFailure
from .activity_feed import read_page
from .discovery import options
from .project_links import workspace,validate,store_mapping,guard_dispatch
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from .agent_store import settings,secret
from .connectors import checked,slack_identity
from .db import database

class Staff(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    role:str=Field(min_length=1,max_length=100)
    skills:str=Field(default="",max_length=1000)
    hours:float=Field(gt=0,le=24)
    jira_id:str=Field(default="",max_length=200)
    slack_id:str=Field(default="",pattern=r"^$|^U[A-Z0-9]+$")

class Link(BaseModel):
    service:str=Field(pattern="^(Jira|Slack)$")
    board_id:str=Field(default="",pattern="^[0-9]{0,20}$")
    destination:str=Field(min_length=1,max_length=100)
    expected:str|None=None

class Search(BaseModel):
    service:Literal["Jira","Slack"]
    query:str=Field(default="",max_length=80)
    cursor:str=Field(default="",max_length=2000)


def router(member):
    r=APIRouter()
    @r.post("/api/hooks/{provider}")
    async def hook(provider:Literal["Jira","Slack"],request:Request):
        body=await request.body()
        env="JIRA_WEBHOOK_SECRET" if provider=="Jira" else "SLACK_SIGNING_SECRET"
        if not authenticated(provider,os.getenv(env,""),request.headers,body):
            raise HTTPException(403,"Invalid webhook signature.")
        try:
            event=json.loads(body)
            if provider=="Slack" and event.get("type")=="url_verification":
                return {"challenge":event["challenge"]}
            site,target,refresh=destination(provider,event)
        except (ValueError,AttributeError,KeyError):
            raise HTTPException(400,"Invalid webhook payload.")
        if site and target:
            with database() as db:
                _,policy=settings(db)
                if site==workspace(provider,policy):
                    db.execute("""UPDATE project_links SET queued=true,
                        poll_after=CASE WHEN verified_at IS NULL THEN poll_after ELSE now() END,
                        last_full=CASE WHEN %s THEN NULL ELSE last_full END,
                        scan_started=CASE WHEN %s THEN NULL ELSE scan_started END,
                        scan_cursor=CASE WHEN %s THEN '' ELSE scan_cursor END
                        WHERE service=%s AND workspace=%s AND destination=%s""",
                        (refresh,refresh,refresh,provider,site,target))
        return {"accepted":True}

    @r.get("/api/projects/{pid}/delivery")
    def delivery(pid:str,user=Depends(member)):
        with database() as db:return dict(team=db.execute("SELECT * FROM project_staff WHERE pid=%s ORDER BY name",(pid,)).fetchall(),links=db.execute("SELECT * FROM project_links WHERE pid=%s",(pid,)).fetchall(),events=db.execute("SELECT * FROM mapped_delivery_events WHERE pid=%s ORDER BY happened DESC LIMIT 100",(pid,)).fetchall())

    @r.post("/api/projects/{pid}/team")
    def staff(pid:str,data:Staff,user=Depends(member)):
        with database() as db:
            row=db.execute("""INSERT INTO project_staff(pid,id,name,role,skills,jira_id,slack_id,hours) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(pid,name) DO UPDATE SET role=excluded.role,skills=excluded.skills,jira_id=excluded.jira_id,slack_id=excluded.slack_id,hours=excluded.hours RETURNING id""",(pid,str(uuid4()),data.name,data.role,data.skills,data.jira_id,data.slack_id,data.hours)).fetchone()
            db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'team.confirmed',%s)",(pid,user,row["id"]))
            return row

    @r.get("/api/projects/{pid}/connections")
    def connections(pid:str,user=Depends(member)):
        with database() as db:
            _,policy=settings(db)
            rows=db.execute("SELECT * FROM project_links WHERE pid=%s",(pid,)).fetchall()
            for row in rows:
                service=row["service"]
                row["connected"]=bool(row["verified_at"] and row["workspace"]==workspace(service,policy) and secret(db,service))
            return rows

    @r.post("/api/projects/{pid}/connections/search")
    def search_connections(pid:str,data:Search,user=Depends(member)):
        with database() as db:
            _,p=settings(db)
            key=secret(db,data.service)
        try:
            result=options(data.service,"projects" if data.service=="Jira" else "channels",p,key,cursor=data.cursor,query=data.query)
            if data.service=="Slack" and data.query:
                result["items"]=[r for r in result["items"] if data.query.casefold() in r["name"].casefold() or data.query==r["id"]]
            return result
        except ServiceFailure as exc:raise HTTPException(exc.code,exc.category)
        except ValueError as exc:raise HTTPException(422,str(exc))

    @r.put("/api/projects/{pid}/link")
    @r.post("/api/projects/{pid}/link/test")
    def link(pid:str,data:Link,request:Request,user=Depends(member)):
        saving=request.method=="PUT"
        with database() as db:
            revision,p=settings(db)
            key=secret(db,data.service)
        try:
            resource=validate(data.service,data.destination,data.board_id,p,key)
            with database() as db:
                current,_=settings(db,True)
                if current!=revision:raise ServiceFailure("Global settings changed. Test again.",409)
                if saving:
                    guard_dispatch(db,pid,data.service)
                    store_mapping(db,pid,data.service,workspace(data.service,p),resource,data.board_id,data.expected)
                    db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'workspace.linked',%s)",(pid,user,resource["destination"]))
                else:
                    db.execute("UPDATE project_links SET verified_at=now() WHERE pid=%s AND service=%s AND workspace=%s AND destination=%s",(pid,data.service,workspace(data.service,p),resource["destination"]))
            return dict(resource,saved=saving)
        except (ServiceFailure,ValueError) as exc:
            if not saving:
                with database() as db:
                    db.execute("UPDATE project_links SET verified_at=NULL,sync_status=%s WHERE pid=%s AND service=%s AND workspace=%s AND (destination=%s OR external_id=%s)",(str(exc),pid,data.service,workspace(data.service,p),data.destination,data.destination))
            raise HTTPException(getattr(exc,"code",422),str(exc))

    @r.delete("/api/projects/{pid}/link/{service}")
    def disconnect(pid:str,service:Literal["Jira","Slack"],expected:str,user=Depends(member)):
        with database() as db:
            settings(db,True)
            try:guard_dispatch(db,pid,service)
            except ServiceFailure as exc:raise HTTPException(exc.code,exc.category)
            if not db.execute("DELETE FROM project_links WHERE pid=%s AND service=%s AND mapping_id::text=%s",(pid,service,expected)).rowcount:
                raise HTTPException(409,"Mapping changed. Refresh project settings.")
            db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'workspace.disconnected',%s)",(pid,user,service))
        return {"disconnected":True}

    @r.post("/api/projects/{pid}/sync/{service}")
    def sync(pid:str,service:str,user=Depends(member)):
        return import_activity(pid,service,user)
    @r.get("/api/projects/{pid}/jira/{issue}/comments")
    def comments(pid:str,issue:str,user=Depends(member)):
        import re
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,19}-[1-9][0-9]*",issue):raise HTTPException(422,"Invalid issue key.")
        with database() as db:
            _,p=settings(db)
            row=db.execute("SELECT workspace,destination FROM project_links WHERE pid=%s AND verified_at IS NOT NULL AND service='Jira'",(pid,)).fetchone()
            if not row or row["workspace"]!=p.jira_site or row["destination"]!=issue.split("-")[0]:raise HTTPException(403)
            key=secret(db,"Jira")
        if not key or not p.sync_jira:raise HTTPException(409,"Enable Jira imports and configure the credential.")
        try:
            with Client(timeout=20) as c:
                issue_url=p.jira_site+"/rest/api/3/issue/"
                resolved=checked(c.get(issue_url+issue,params={"fields":"project"},auth=(p.jira_email,key)))
                if resolved.get("fields",{}).get("project",{}).get("key")!=row["destination"]:raise HTTPException(403,"Issue moved outside this project.")
                data=checked(c.get(issue_url+str(resolved["id"])+"/comment",params={"maxResults":50,"orderBy":"-created"},auth=(p.jira_email,key)))
            def plaintext(node):
                return node.get("text","")+" ".join(plaintext(child) for child in node.get("content",[]))
            return [{"id":x["id"],"author":x["author"].get("displayName"),"created":x["created"],"text":plaintext(x["body"])} for x in data.get("comments",[])]
        except HTTPException:raise
        except Exception:raise HTTPException(502,"Could not retrieve permitted Jira comments.")
    return r


def import_activity(pid,service,user=None):
    if service not in {"Jira","Slack"}:raise HTTPException(422)
    mapping=None
    try:
        with database() as db:
            _,p=settings(db)
            if not (p.sync_jira if service=="Jira" else p.sync_slack):raise HTTPException(409,"Enable imports in Integrations.")
            link=db.execute("SELECT * FROM project_links WHERE pid=%s AND service=%s FOR UPDATE",(pid,service)).fetchone()
            if not link or workspace(service,p)!=link["workspace"]:raise HTTPException(409,"Verify this project's workspace mapping.")
            mapping=link["mapping_id"]
            key=secret(db,service)
            if not key:raise ServiceFailure("Set the global credential in Integrations.",409)
            start=link["scan_started"] or datetime.now(timezone.utc)
            full=link["scan_full"] if link["scan_started"] else not link["last_full"] or start-link["last_full"]>timedelta(days=1)
            if not link["verified_at"] or full and not link["scan_started"]:
                resource=validate(service,link["destination"],link["board_id"],p,key)
                db.execute("UPDATE project_links SET external_id=%s,resource_name=%s,resource_url=%s WHERE mapping_id=%s",(resource["external_id"],resource["resource_name"],resource["resource_url"],mapping))
            with Client(timeout=20) as c:events,cursor=read_page(c,service,link,p,key,start,full)
            for rid,at,record in events:
                db.execute("""INSERT INTO delivery_events(pid,service,mapping_id,remote_id,happened,record,synced) VALUES (%s,%s,%s,%s,%s,%s::jsonb,clock_timestamp())
                  ON CONFLICT(pid,service,mapping_id,remote_id) DO UPDATE SET synced=clock_timestamp(),record=excluded.record""",(pid,service,mapping,rid,at,json.dumps(record)))
            if not cursor and full:
                # Retire history for issues/messages that are no longer visible to this credential.
                db.execute("""DELETE FROM delivery_events old WHERE old.mapping_id=%s AND old.synced<%s AND NOT EXISTS
                    (SELECT 1 FROM delivery_events fresh WHERE fresh.mapping_id=old.mapping_id AND fresh.synced>=%s
                     AND fresh.record->>'issue'=old.record->>'issue')""",(mapping,start,start))
            db.execute("""UPDATE project_links SET verified_at=now(),scan_cursor=%s,scan_started=%s,scan_full=%s,queued=%s,
                last_sync=CASE WHEN %s THEN last_sync ELSE %s END,last_full=CASE WHEN %s THEN %s ELSE last_full END,
                poll_after=CASE WHEN %s THEN now() ELSE now()+make_interval(mins=>%s) END,sync_status=%s WHERE mapping_id=%s""",
                (cursor or "",start if cursor else None,full,bool(cursor),bool(cursor),start,not cursor and full,start,bool(cursor),p.poll_minutes,
                 "Sync in progress" if cursor else ("Channel synced; thread replies require additional Slack access." if link.get("thread_warning") else "Up to date"),mapping))
        return {"fetched":len(events),"more":bool(cursor)}
    except HTTPException:raise
    except Exception as exc:
        detail=exc.category if isinstance(exc,ServiceFailure) else "Sync failed. Verify workspace access and retry."
        if mapping:
            with database() as db:
                db.execute("""UPDATE project_links SET verified_at=NULL,queued=true,sync_status=%s,poll_after=now()+make_interval(secs=>%s),
                    scan_cursor=CASE WHEN %s THEN scan_cursor ELSE '' END,
                    scan_started=CASE WHEN %s THEN scan_started ELSE NULL END
                    WHERE mapping_id=%s AND last_sync IS NOT DISTINCT FROM %s AND scan_cursor=%s""",
                    (detail,max(60,getattr(exc,"retry_after",0)),getattr(exc,"transient",False),getattr(exc,"transient",False),
                     mapping,link["last_sync"],link["scan_cursor"]))
        raise HTTPException(getattr(exc,"code",502),detail)
