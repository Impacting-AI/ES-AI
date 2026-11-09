"""Draft a daily internal snapshot once per project and local date."""
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from .agent_store import settings
from .agent_policy import health_snapshot
from .db import database
from .ingest import repair_uploads
from .activity import import_activity
from .reporting import scheduled_reports


def tick():
    with database() as db:
        _,policy=settings(db)
        now=datetime.now(ZoneInfo(policy.timezone))
        if not(policy.enabled and policy.allow_health and policy.daily_digest) or now.hour<policy.digest_hour:return
        if policy.digest_frequency=="Weekly" and now.weekday()!=policy.digest_weekday:return
        projects=db.execute("SELECT id FROM projects WHERE NOT archived AND NOT EXISTS (SELECT 1 FROM agent_digests d WHERE d.pid=projects.id AND d.local_day=%s)",(now.date(),)).fetchall()
        for project in projects:
            pid=project["id"]
            note=health_snapshot(db.execute("SELECT state FROM sources WHERE pid=%s",(pid,)).fetchall(),db.execute("SELECT state FROM plans WHERE pid=%s",(pid,)).fetchall(),db.execute("SELECT DISTINCT ON (record->>'issue') record FROM mapped_delivery_events WHERE pid=%s AND service='Jira' ORDER BY record->>'issue',happened DESC",(pid,)).fetchall())
            db.execute("INSERT INTO agent_digests(pid,local_day,body) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",(pid,now.date(),note))


def poll_workspaces():
    with database() as db:
        _,p=settings(db)
        if not p.enabled:return
        rows=db.execute("""SELECT l.pid,l.service FROM project_links l JOIN projects j ON j.id=l.pid
           WHERE NOT j.archived AND ((l.service='Jira' AND %s AND l.workspace=%s) OR (l.service='Slack' AND %s AND l.workspace=%s))
           AND (l.queued OR %s>0) AND (l.poll_after IS NULL OR l.poll_after<=now())
           ORDER BY l.poll_after NULLS FIRST LIMIT 5 FOR UPDATE OF l SKIP LOCKED""",(p.sync_jira,p.jira_site,p.sync_slack,p.slack_team,p.poll_minutes)).fetchall()
        for row in rows:
            db.execute("UPDATE project_links SET poll_after=now()+make_interval(mins=>%s) WHERE pid=%s AND service=%s",(max(1,p.poll_minutes),row["pid"],row["service"]))
    for row in rows:
        try:import_activity(row["pid"],row["service"])
        except Exception:logging.warning("Project sync deferred for %s",row["service"])

if __name__=="__main__":
    while True:
        for job in (repair_uploads,tick,poll_workspaces,scheduled_reports):
            try:job()
            except Exception:logging.error("Worker job %s failed during this cycle.",job.__name__)
        time.sleep(60)
