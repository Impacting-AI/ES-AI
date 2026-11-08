import os
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,SecretStr
from .agent_store import AGENT,SERVICES,settings,secret,save
from .agent_policy import Policy
from .db import database,cipher
from .discovery import fingerprint,probe,options,model_list
from .transport import ServiceFailure

class Configuration(BaseModel):
    revision:int
    policy:Policy
    credential:SecretStr|None=Field(default=None,max_length=3000)

def signature(service,policy,key):
    return fingerprint(os.environ["ENCRYPTION_KEY"],service,policy,key)

def latest(db,p):
    states={}
    for service in SERVICES:
        key=secret(db,service)
        row=db.execute("SELECT ok,detail,checked_at FROM connection_checks WHERE agent_id=%s AND service=%s AND fingerprint=%s",(AGENT,service,signature(service,p,key))).fetchone() if key else None
        states[service]=row or {"ok":False,"detail":"Saved · untested" if key else "No credential","checked_at":None}
    return states

def router(admin,throttle):
    r=APIRouter()
    @r.post("/api/connections/{service}/{operation}")
    def configure(service:str,operation:str,data:Configuration,user=Depends(admin)):
        if service not in SERVICES or operation not in {"test","save","models"}:raise HTTPException(404)
        entered=data.credential.get_secret_value().strip() if data.credential else ""
        with database() as db:
            revision,current=settings(db,operation=="save")
            if revision!=data.revision:raise HTTPException(409,"Configuration changed. Reload settings before continuing.")
            if service=="Jira" and current.jira_site!=data.policy.jira_site and not entered:
                raise HTTPException(422,"Enter the token for the new Jira site.")
            key=entered or secret(db,service)
            if operation=="save":
                try:new_revision=save(db,user,data.policy,revision)
                except ValueError as exc:raise HTTPException(422,str(exc))
                if entered:
                    encrypted=cipher().encrypt(entered.encode()).decode()
                    db.execute("INSERT INTO agent_credentials(agent_id,service,encrypted) VALUES (%s,%s,%s) ON CONFLICT(agent_id,service) DO UPDATE SET encrypted=excluded.encrypted, updated=now()",(AGENT,service,encrypted))
                    db.execute("INSERT INTO audit(uid,action,subject) VALUES (%s,'credential.rotated',%s)",(user,service))
                return {"revision":new_revision,"status":latest(db,data.policy)[service]}
        throttle("probe:"+user,12,3600)
        if operation=="models":
            try:return {"models":model_list(service,key)}
            except (ValueError,ServiceFailure) as e:raise HTTPException(422,str(e))
        try:
            detail=probe(service,data.policy,key)
            ok=True
        except ServiceFailure as e:ok,detail=False,e.category
        except ValueError as e:ok,detail=False,"Configuration or workspace mismatch"
        except Exception:ok,detail=False,"Network error or unsupported service response"
        stamp=signature(service,data.policy,key)
        with database() as db:
            row=db.execute("""INSERT INTO connection_checks(agent_id,service,fingerprint,ok,detail) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(agent_id,service,fingerprint) DO UPDATE SET ok=excluded.ok, detail=excluded.detail, checked_at=now()
            RETURNING ok,detail,checked_at""",(AGENT,service,stamp,ok,detail)).fetchone()
            db.execute("INSERT INTO audit(uid,action,subject) VALUES (%s,%s,%s)",(user,"connection.verified" if ok else "connection.failed",service))
        return row

    @r.get("/api/connections/{service}/options/{resource}")
    def discover(service:str,resource:str,project:str=Query(default="",pattern=r"^$|^[A-Z][A-Z0-9]{1,19}$"),cursor:str=Query(default="",max_length=2000),query:str=Query(default="",max_length=80),user=Depends(admin)):
        if service not in {"Jira","Slack"}:raise HTTPException(404)
        with database() as db:
            _,p=settings(db); key=secret(db,service)
            if not latest(db,p)[service]["ok"]:raise HTTPException(409,"Test and save the current connection before discovering resources.")
        try:return options(service,resource,p,key,project,cursor,query)
        except ValueError as exc:raise HTTPException(422,str(exc))
        except ServiceFailure as exc:raise HTTPException(502,exc.category)
    return r
