from datetime import date,timedelta,datetime,timezone
from uuid import uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from .db import database
from .review_rules import ScheduleRule, reporting_window
from zoneinfo import ZoneInfo

class Period(BaseModel):
    start:date
    end:date
    audience:str=Field(pattern="^(CEO|Client)$")

class Edit(BaseModel):
    body:str=Field(min_length=1,max_length=16000)
    revision:int


from .report_text import render

def create_report(db,pid,user,data,zone=timezone.utc,heading=""):
    start=datetime.combine(data.start,datetime.min.time(),zone)
    end=datetime.combine(data.end,datetime.min.time(),zone)+timedelta(days=1)
    project=db.execute("SELECT name,client,profile FROM projects WHERE id=%s",(pid,)).fetchone()
    head=db.execute("SELECT name FROM project_staff WHERE pid=%s AND lower(role) IN ('project manager','project head') ORDER BY name LIMIT 1",(pid,)).fetchone()
    events=db.execute("SELECT service,record FROM mapped_delivery_events WHERE pid=%s AND happened>=%s AND happened<%s ORDER BY happened",(pid,start,end)).fetchall()
    approved=db.execute("SELECT s.title,s.version FROM audit a JOIN sources s ON s.id=a.subject AND s.pid=a.pid WHERE a.pid=%s AND a.action='source.approved' AND a.created>=%s AND a.created<%s ORDER BY a.created",(pid,start,end)).fetchall()
    text=(heading+"\n\n" if heading else "")+render(project,project['profile'].get('head') or (head['name'] if head else None),data,events,approved).replace("(UTC)",f"({zone})",1)
    if len(text)>16000:text=text[:15800]+"\n[Report truncated. Generate a shorter reporting period for the remaining records.]"
    key=str(uuid4())
    db.execute("INSERT INTO report_drafts(id,pid,uid,audience,period_start,period_end,body) VALUES (%s,%s,%s,%s,%s,%s,%s)",(key,pid,user,data.audience,data.start,data.end,text))
    return {"id":key}

def scheduled_reports():
    with database() as db:
        rows=db.execute("""SELECT r.* FROM report_rules r JOIN projects p ON p.id=r.pid JOIN members m ON m.pid=r.pid AND m.uid=r.uid JOIN users u ON u.id=r.uid WHERE NOT p.archived AND u.agent_access AND u.platform_role IN ('Super Admin','CEO','Project Manager') AND r.config->>'frequency' IN ('Daily','Weekly')""").fetchall()
    for row in rows:
        try:run_schedule(row["pid"])
        except Exception:
            import logging
            logging.error("Scheduled report generation failed for project %s",row["pid"])

def run_schedule(pid):
    with database() as db:
        rule_row=db.execute("SELECT r.* FROM report_rules r JOIN members m ON m.pid=r.pid AND m.uid=r.uid JOIN projects p ON p.id=r.pid JOIN users u ON u.id=r.uid WHERE r.pid=%s AND NOT p.archived AND u.agent_access AND u.platform_role IN ('Super Admin','CEO','Project Manager') FOR UPDATE OF r,m,p,u",(pid,)).fetchone()
        if not rule_row:return
        rule=ScheduleRule(**rule_row['config'])
        window=reporting_window(rule,datetime.now(timezone.utc))
        if not window:return
        day,start,end=window
        created=db.execute("INSERT INTO report_occurrences(pid,day) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING day",(pid,day)).fetchone()
        if created:
            result=create_report(db,pid,rule_row['uid'],Period(start=start,end=end,audience=rule.audience),ZoneInfo(rule.zone),rule.heading)
            db.execute("UPDATE report_occurrences SET report_id=%s WHERE pid=%s AND day=%s",(result['id'],pid,day))

def router(member):
    r=APIRouter()
    @r.get("/api/projects/{pid}/report-rule")
    def read_rule(pid:str,user=Depends(member)):
        with database() as db:
            row=db.execute("SELECT config FROM report_rules WHERE pid=%s",(pid,)).fetchone()
            return row["config"] if row else ScheduleRule()
    @r.put("/api/projects/{pid}/report-rule")
    def write_rule(pid:str,data:ScheduleRule,user=Depends(member)):
        with database() as db:
            db.execute("INSERT INTO report_rules(pid,uid,config) VALUES(%s,%s,%s::jsonb) ON CONFLICT(pid) DO UPDATE SET config=excluded.config,uid=excluded.uid,updated=now()",(pid,user,data.model_dump_json()))
            db.execute("INSERT INTO audit(uid,pid,action,subject) VALUES (%s,%s,'report.schedule',%s)",(user,pid,data.frequency))
        return data
    @r.get("/api/projects/{pid}/report-drafts")
    def listing(pid:str,user=Depends(member)):
        with database() as db:return db.execute("SELECT * FROM report_drafts WHERE pid=%s ORDER BY created DESC LIMIT 50",(pid,)).fetchall()

    @r.post("/api/projects/{pid}/report-drafts")
    def draft(pid:str,data:Period,user=Depends(member)):
        if data.end<data.start or (data.end-data.start).days>365:raise HTTPException(422,"Select a period up to one year.")
        with database() as db:return create_report(db,pid,user,data)
    @r.put("/api/projects/{pid}/report-drafts/{key}")
    def edit(pid:str,key:str,data:Edit,user=Depends(member)):
        with database() as db:
            if not db.execute("UPDATE report_drafts SET body=%s,revision=revision+1 WHERE pid=%s AND id=%s AND revision=%s",(data.body,pid,key,data.revision)).rowcount:raise HTTPException(409,"Draft changed. Reopen it before editing.")
        return {"saved":True}
    return r
