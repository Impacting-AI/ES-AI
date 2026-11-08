"""Allowlisted provider endpoints. Only a reviewed action may call publish()."""
from .transport import Client, failure
from pydantic import BaseModel,Field,model_validator
from typing import Literal
from datetime import date

class ExternalAction(BaseModel):
    kind: Literal["Jira issue","Jira project","Jira board","Jira relationship","Slack channel","Slack invitation","Slack Jira update","Email report"]
    destination: str = Field(min_length=1,max_length=254)
    title: str = Field(min_length=1,max_length=180)
    body: str = Field(default="",max_length=16000)
    reference: str = Field(default="",max_length=240)
    assignee: str = Field(default="",max_length=200)
    due: date | None = None
    parent: str = Field(default="",pattern=r"^$|^[A-Z][A-Z0-9]+-[1-9][0-9]*$")
    @model_validator(mode="after")
    def validate_destination(self):
        import re
        if self.kind.startswith("Jira") and not re.fullmatch(r"[A-Z][A-Z0-9]{1,19}",self.destination):raise ValueError("Enter a Jira project key.")
        if self.kind=="Jira relationship":
            if not self.reference or not all(re.fullmatch(re.escape(self.destination)+r"-[1-9][0-9]*",x) for x in (self.title,self.parent)) or self.title==self.parent:raise ValueError("Supply two different issues in the linked project and a Jira link type.")
        if self.kind=="Jira board" and not self.reference.isdecimal():raise ValueError("Enter an existing Jira filter ID.")
        if self.kind=="Jira project" and not self.reference:raise ValueError("Enter the Jira lead account ID.")
        if self.kind=="Slack channel" and not re.fullmatch(r"[a-z0-9_-]{1,80}",self.destination):raise ValueError("Invalid Slack channel name.")
        if self.kind=="Slack invitation" and (not re.fullmatch(r"[CG][A-Z0-9]+",self.destination) or not re.fullmatch(r"U[A-Z0-9]+(,U[A-Z0-9]+)*",self.reference)):raise ValueError("Enter a channel ID and comma-separated Slack member IDs.")
        if self.kind=="Slack Jira update" and (not re.fullmatch(r"[CG][A-Z0-9]+",self.destination) or not re.fullmatch(r"[A-Z][A-Z0-9]+-[1-9][0-9]*",self.reference)):raise ValueError("Provide a channel ID and Jira issue key.")
        if self.kind=="Email report" and not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+",self.destination):raise ValueError("Enter one recipient email address.")
        return self

def checked(response):
    response.raise_for_status()
    data=response.json()
    if data.get("ok") is False: raise failure(400,response.body)
    return data

def slack_identity(c,policy,key):
    info=checked(c.post("https://slack.com/api/auth.test",headers={"Authorization":"Bearer "+key}))
    if not policy.slack_team or info.get("team_id")!=policy.slack_team: raise ValueError("Slack workspace ID does not match the configured workspace.")
    return info

def connection(service,policy,key):
    if not key:raise ValueError("Configure a credential first.")
    with Client(timeout=15) as c:
        if service=="Jira":
            if not policy.jira_site or not policy.jira_email:raise ValueError("Set the existing Jira Cloud site and account email.")
            info=checked(c.get(policy.jira_site+"/rest/api/3/myself",auth=(policy.jira_email,key)))
            return "Connected account "+info["accountId"]
        if service=="Slack":return "Connected workspace "+slack_identity(c,policy,key)["team_id"]
        if service=="Email":
            checked(c.get("https://api.resend.com/domains",headers={"Authorization":"Bearer "+key}));return "Connected to Resend"
        if service=="OpenAI": url,headers="https://api.openai.com/v1/models",{"Authorization":"Bearer "+key}
        elif service=="Anthropic":url,headers="https://api.anthropic.com/v1/models",{"x-api-key":key,"anthropic-version":"2023-06-01"}
        else:url,headers="https://generativelanguage.googleapis.com/v1beta/models",{"x-goog-api-key":key}
        checked(c.get(url,headers=headers));return "Provider connection verified"

def publish(action,policy,key,action_id):
    if not key:raise ValueError("Credential unavailable.")
    a=action
    with Client(timeout=30) as c:
        if a.kind.startswith("Jira"):
            if not policy.jira_site or not policy.jira_email:raise ValueError("Configure Jira first.")
            auth=(policy.jira_email,key); site=policy.jira_site
            if a.kind=="Jira relationship":
                result=c.post(site+"/rest/api/3/issueLink",auth=auth,json={"type":{"name":a.reference},"inwardIssue":{"key":a.title},"outwardIssue":{"key":a.parent}})
                result.raise_for_status()
                return a.title+" / "+a.reference+" / "+a.parent
            if a.kind=="Jira issue":
                fields=dict(project={"key":a.destination},issuetype={"name":a.reference or "Task"},summary=a.title,description={"type":"doc","version":1,"content":[{"type":"paragraph","content":[{"type":"text","text":a.body or a.title}]}]})
                if a.assignee:fields["assignee"]={"accountId":a.assignee}
                if a.due:fields["duedate"]=a.due.isoformat()
                if a.parent:fields["parent"]={"key":a.parent}
                return checked(c.post(site+"/rest/api/3/issue",auth=auth,json={"fields":fields}))["key"]
            if a.kind=="Jira project":
                existing=c.get(site+"/rest/api/3/project/"+a.destination,auth=auth)
                if existing.status_code==200:raise ValueError("Project key already exists. Review the existing project before linking.")
                if existing.status_code!=404:existing.raise_for_status()
                return checked(c.post(site+"/rest/api/3/project",auth=auth,json=dict(key=a.destination,name=a.title,description=a.body,projectTypeKey="software",leadAccountId=a.reference)))["key"]
            return str(checked(c.post(site+"/rest/agile/1.0/board",auth=auth,json=dict(name=a.title,type="kanban",filterId=int(a.reference),location={"type":"project","projectKeyOrId":a.destination})))["id"])
        headers={"Authorization":"Bearer "+key}
        if a.kind.startswith("Slack"):
            slack_identity(c,policy,key)
            if a.kind=="Slack Jira update":
                if not policy.slack_notifications:raise ValueError("Notifications disabled.")
                return checked(c.post("https://slack.com/api/chat.postMessage",headers=headers,json={"channel":a.destination,"text":a.reference+" · "+a.title+"\n"+a.body,"mrkdwn":False,"unfurl_links":False}))["ts"]
            if a.kind=="Slack channel":return checked(c.post("https://slack.com/api/conversations.create",headers=headers,json={"name":a.destination,"is_private":True}))["channel"]["id"]
            return checked(c.post("https://slack.com/api/conversations.invite",headers=headers,json={"channel":a.destination,"users":a.reference}))["channel"]["id"]
        if not policy.email_sender:raise ValueError("Set a verified sender address first.")
        return checked(c.post("https://api.resend.com/emails",headers={**headers,"Idempotency-Key":action_id},json={"from":policy.email_sender,"to":[a.destination],"subject":a.title,"text":a.body}))["id"]
