import os
from .agent_policy import Policy
from .db import cipher
from .model_options import model_config,generation_options
from .transport import ServiceFailure
from .models import PROVIDERS

AGENT="pm-ai-es"
SERVICES={**PROVIDERS,"Jira":"JIRA_API_TOKEN","Slack":"SLACK_BOT_TOKEN","Email":"RESEND_API_KEY"}

def settings(db,lock=False):
    # Bootstrap from the original model choice when upgrading an existing installation.
    original=db.execute("SELECT provider,model FROM config WHERE id=1").fetchone() or {}
    default=Policy(**original)
    db.execute("INSERT INTO agent_settings VALUES (%s,1,%s::jsonb) ON CONFLICT DO NOTHING",(AGENT,default.model_dump_json()))
    row=db.execute("SELECT revision,policy FROM agent_settings WHERE agent_id=%s"+(" FOR UPDATE" if lock else ""),(AGENT,)).fetchone()
    return row['revision'],Policy(**row['policy'])

def secret(db,service):
    row=db.execute("SELECT encrypted FROM agent_credentials WHERE agent_id=%s AND service=%s",(AGENT,service)).fetchone()
    if row is None:return os.getenv(SERVICES[service],"")
    return cipher().decrypt(row["encrypted"].encode()).decode() if row["encrypted"] else ""

def save(db,user,policy,revision):
    current,old=settings(db,True)
    if revision!=current:raise ValueError("Settings changed in another session. Reload and retry.")
    if policy.monthly_budget and not (policy.input_rate and policy.output_rate):raise ValueError("Set both token prices before enabling a monthly budget.")
    if bool(policy.fallback_provider)!=bool(policy.fallback_model):raise ValueError("Fallback needs both provider and model.")
    for fallback in (False,True):
        config,limit,temperature=model_config(policy,fallback)
        if not config["provider"] or not config["model"]:continue
        if policy.monthly_budget and limit is None:
            raise ValueError("Set maximum output tokens to reserve usage against the monthly budget.")
        if config["context_window"] and limit and limit>=config["context_window"]:
            raise ValueError("The context window must leave room for both the input and the response.")
        try:generation_options(config,limit,temperature)
        except ServiceFailure as exc:raise ValueError(exc.category) from exc
    if policy.jira_site!=old.jira_site and secret(db,"Jira"):
        db.execute("INSERT INTO agent_credentials(agent_id,service,encrypted) VALUES (%s,'Jira',NULL) ON CONFLICT(agent_id,service) DO UPDATE SET encrypted=NULL,updated=now()",(AGENT,))
    db.execute("INSERT INTO agent_versions(agent_id,revision,policy,actor) VALUES (%s,%s,%s::jsonb,%s) ON CONFLICT DO NOTHING",(AGENT,current,old.model_dump_json(),user))
    db.execute("UPDATE agent_settings SET revision=revision+1,policy=%s::jsonb WHERE agent_id=%s",(policy.model_dump_json(),AGENT))
    db.execute("INSERT INTO audit(uid,action,subject) VALUES (%s,'agent.settings.saved',%s)",(user,str(current+1)))
    return current+1
