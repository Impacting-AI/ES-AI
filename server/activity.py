"""Explicit project bindings and bounded read-only delivery activity imports."""
from datetime import datetime,timezone
from uuid import uuid4
import json
from .transport import Client,ServiceFailure
from .discovery import verify_binding
from fastapi import APIRouter,Depends,HTTPException
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
    destination:str=Field(pattern="^[A-Z][A-Z0-9]{1,30}$")


def router(member):
    r=APIRouter()
    @r.get("/api/projects/{pid}/delivery")
    def delivery(pid:str,user=Depends(member)):
        with database() as db:return dict(team=db.execute("SELECT * FROM project_staff WHERE pid=%s ORDER BY name",(pid,)).fetchall(),links=db.execute("SELECT * FROM project_links WHERE pid=%s",(pid,)).fetchall(),events=db.execute("SELECT * FROM delivery_events WHERE pid=%s ORDER BY happened DESC LIMIT 100",(pid,)).fetchall())

    @r.post("/api/projects/{pid}/team")
    def staff(pid:str,data:Staff,user=Depends(member)):
        with database() as db:
            row=db.execute("""INSERT INTO project_staff(pid,id,name,role,skills,jira_id,slack_id,hours) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(pid,name) DO UPDATE SET role=excluded.role,skills=excluded.skills,jira_id=excluded.jira_id,slack_id=excluded.slack_id,hours=excluded.hours RETURNING id""",(pid,str(uuid4()),data.name,data.role,data.skills,data.jira_id,data.slack_id,data.hours)).fetchone()
            db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'team.confirmed',%s)",(pid,user,row["id"]))
            return row

    @r.put("/api/projects/{pid}/link")
    def link(pid:str,data:Link,user=Depends(member)):
        with database() as db:
            _,p=settings(db,True)
            workspace=p.jira_site if data.service=="Jira" else p.slack_team
            if not workspace:raise HTTPException(409,"Configure the workspace in Agent settings.")
            existing=db.execute("SELECT * FROM project_links WHERE (pid=%s AND service=%s) OR (service=%s AND workspace=%s AND destination=%s)",(pid,data.service,data.service,workspace,data.destination)).fetchall()
            if existing and any(x["pid"]!=pid or x["workspace"]!=workspace or x["destination"]!=data.destination for x in existing):
                raise HTTPException(409,"A different project binding already exists.")
            key=secret(db,data.service)
            if not key:raise HTTPException(409,"Configure and test the service credential first.")
            try:
                verify_binding(data.service,data.destination,p,key)
                if data.board_id:
                    if data.service!="Jira":raise HTTPException(422,"Board IDs apply to Jira only.")
                    with Client(timeout=15) as c:
                        board=checked(c.get(p.jira_site+"/rest/agile/1.0/board/"+data.board_id,auth=(p.jira_email,key)))
                        if board.get("location",{}).get("projectKey")!=data.destination:raise HTTPException(422,"Board location must match the selected project.")
            except ServiceFailure as exc:raise HTTPException(422,exc.category)
            except HTTPException:raise
            except Exception:raise HTTPException(422,"Workspace binding could not be verified.")
            db.execute("INSERT INTO project_links(pid,service,workspace,destination,board_id) VALUES (%s,%s,%s,%s,%s) ON CONFLICT(pid,service) DO UPDATE SET board_id=excluded.board_id",(pid,data.service,workspace,data.destination,data.board_id or None))
            db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'workspace.linked',%s)",(pid,user,workspace+'/'+data.destination))
        return {"saved":True}

    @r.post("/api/projects/{pid}/sync/{service}")
    def sync(pid:str,service:str,user=Depends(member)):
        return import_activity(pid,service,user)
    @r.get("/api/projects/{pid}/jira/{issue}/comments")
    def comments(pid:str,issue:str,user=Depends(member)):
        import re
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,19}-[1-9][0-9]*",issue):raise HTTPException(422,"Invalid issue key.")
        with database() as db:
            _,p=settings(db)
            row=db.execute("SELECT workspace,destination FROM project_links WHERE pid=%s AND service='Jira'",(pid,)).fetchone()
            if not row or row["workspace"]!=p.jira_site or row["destination"]!=issue.split("-")[0]:raise HTTPException(403)
            key=secret(db,"Jira")
        if not key or not p.sync_jira:raise HTTPException(409,"Enable Jira imports and configure the credential.")
        try:
            with Client(timeout=20) as c:
                data=checked(c.get(p.jira_site+"/rest/api/3/issue/"+issue+"/comment",params={"maxResults":50,"orderBy":"-created"},auth=(p.jira_email,key)))
            def plaintext(node):
                return node.get("text","")+" ".join(plaintext(child) for child in node.get("content",[]))
            return [{"id":x["id"],"author":x["author"].get("displayName"),"created":x["created"],"text":plaintext(x["body"])} for x in data.get("comments",[])]
        except Exception:raise HTTPException(502,"Could not retrieve permitted Jira comments.")
    return r


def import_activity(pid,service,user=None):
    if service not in {"Jira","Slack"}:raise HTTPException(422)
    with database() as db:
        _,p=settings(db)
        if not (p.sync_jira if service=="Jira" else p.sync_slack):raise HTTPException(409,"Activity imports disabled in integration settings.")
        link=db.execute("SELECT * FROM project_links WHERE pid=%s AND service=%s",(pid,service)).fetchone()
        if not link or link["workspace"]!=(p.jira_site if service=="Jira" else p.slack_team):raise HTTPException(409,"Confirm the workspace binding before importing activity.")
        key=secret(db,service)
    if not key:raise HTTPException(409,"Configure the service credential.")
    target=link["destination"]
    events=[]
    try:
        with Client(timeout=20) as c:
            if service=="Jira":
                data=checked(c.get(p.jira_site+"/rest/api/3/search/jql",params={"jql":"project = "+target+" ORDER BY updated DESC","fields":"summary,status,assignee,updated,duedate","maxResults":100},auth=(p.jira_email,key)))
                for issue in data.get("issues",[]):
                    f=issue["fields"];events.append((issue["key"]+"@"+f["updated"],f["updated"],{"title":f["summary"],"status":f["status"]["name"],"status_group":p.jira_status_map.get(f["status"]["name"],""),"issue":issue["key"],"url":p.jira_site+"/browse/"+issue["key"],"due":f.get("duedate"),"assignee":(f.get("assignee") or {}).get("displayName")}))
            else:
                slack_identity(c,p,key)
                data=checked(c.get("https://slack.com/api/conversations.history",headers={"Authorization":"Bearer "+key},params={"channel":target,"limit":100}))
                for m in data.get("messages",[]):
                    events.append((m["ts"],datetime.fromtimestamp(float(m["ts"]),timezone.utc),{"title":m.get("text","")[:4000],"sender":m.get("user"),"channel":target}))
        with database() as db:
            for rid,at,record in events:db.execute("""INSERT INTO delivery_events(pid,service,remote_id,happened,record) VALUES (%s,%s,%s,%s,%s::jsonb) ON CONFLICT(pid,service,remote_id) DO UPDATE SET synced=now(),record=excluded.record""",(pid,service,rid,at,json.dumps(record)))
            db.execute("UPDATE project_links SET sync_status=%s WHERE pid=%s AND service=%s",(f"Imported {len(events)} records",pid,service))
            db.execute("INSERT INTO audit(pid,uid,action,subject) VALUES (%s,%s,'activity.synced',%s)",(pid,user,service))
        return {"fetched":len(events)}
    except Exception:raise HTTPException(502,"Activity import failed. Check the configured workspace, project binding and read permissions.")
