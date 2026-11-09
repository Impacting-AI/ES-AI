"""Read-only service identity, capabilities and paginated discovery."""
from urllib.parse import quote
import hashlib
import hmac
import json
from .model_options import model_config
from .models import PROVIDERS,generate
from .transport import Client,ServiceFailure,failure
from .connectors import checked,connection


def fingerprint(signing_key,service,policy,key):
    attributes=[service,key]
    if service in PROVIDERS:
        attributes += [model_config(policy,flag) for flag in (False,True)
                       if (policy.fallback_provider if flag else policy.provider)==service]
    if service=="Jira":attributes += [policy.jira_site,policy.jira_email]
    if service=="Slack":attributes += [policy.slack_team]
    if service=="Email":attributes += [policy.email_sender]
    return hmac.new(signing_key.encode(),json.dumps(attributes,sort_keys=True).encode(),hashlib.sha256).hexdigest()


def selected_model(p,service):
    if service==p.provider:return p.model
    if service==p.fallback_provider:return p.fallback_model
    return ""


def limit_warnings(config,limit,key):
    """Discovery is advisory: some valid aliases/accounts allow generation only."""
    provider=config["provider"]
    if provider=="OpenAI":return []
    if provider=="Gemini":
        name=quote(config["model"].removeprefix("models/"),safe="")
        url="https://generativelanguage.googleapis.com/v1beta/models/"+name
        headers={"x-goog-api-key":key}
        input_key,output_key="inputTokenLimit","outputTokenLimit"
    else:
        url="https://api.anthropic.com/v1/models/"+quote(config["model"],safe="")
        headers={"x-api-key":key,"anthropic-version":"2023-06-01"}
        input_key,output_key="max_input_tokens","max_tokens"
    try:
        with Client(timeout=8) as client:
            result=client.get(url,headers=headers)
        if result.status_code!=200:return []
        info=result.json()
    except (ServiceFailure,ValueError):return []
    warnings=[]
    for label,value,maximum in (("maximum output tokens",limit,info.get(output_key)),
                                ("input budget",config["context_window"]-(limit or 0),info.get(input_key))):
        if value and isinstance(maximum,int) and value>maximum:
            warnings.append(f"{config['model']}: configured {label} {value} exceeds the provider limit {maximum}.")
    return warnings

def probe(service,p,key):
    if not key:raise ServiceFailure("Enter or save a credential first",422)
    if service in PROVIDERS:
        model=selected_model(p,service)
        if not model:raise ServiceFailure("Select this provider and enter a model ID first",422)
        models=[]
        for fallback in (False,True):
            config,limit,temperature=model_config(p,fallback)
            if service!=config["provider"]:continue
            name=config["model"]
            models.append(name)
            warnings=limit_warnings(config,limit,key)
            if warnings:raise ServiceFailure(" ".join(warnings),422)
            answer,_,_=generate(config,"Reply with the word OK.",[],secret=key,max_tokens=limit,temperature=temperature)
            if not isinstance(answer,str) or not answer.strip():raise ServiceFailure("Model returned no usable text",422)
        return "Verified text generation with "+", ".join(models)
    if service=="Slack":
        with Client(timeout=15) as c:
            response=c.post("https://slack.com/api/auth.test",headers={"Authorization":"Bearer "+key})
            info=checked(response)
            if not p.slack_team or p.slack_team!=info.get("team_id"):raise ServiceFailure("Slack workspace ID does not match",422)
            scopes=response.headers.get("x-oauth-scopes","")
            return "Verified "+str(info.get("team","Slack"))+" ("+info["team_id"]+"). Granted scopes: "+(scopes or "not returned")
    return connection(service,p,key)


def options(service,resource,p,key,project="",cursor="",query=""):
    if not key:raise ServiceFailure("Credential unavailable",422)
    with Client(timeout=18) as c:
        if service=="Jira":
            if not p.jira_site or not p.jira_email:raise ServiceFailure("Configure Jira site and email first",422)
            auth=(p.jira_email,key)
            def get(path,params={}):return checked(c.get(p.jira_site+path,auth=auth,params=params))
            start=int(cursor or "0")
            if not 0<=start<=1000000:raise ValueError("Invalid page")
            page={"startAt":start,"maxResults":50}
            if resource=="projects":result=get("/rest/api/3/project/search",{**page,"query":query} if query else page)
            elif resource=="relationships":
                data=get("/rest/api/3/issueLinkType")
                return {"items":[{"id":x["id"],"name":x["name"]} for x in data.get("issueLinkTypes",[])],"next":""}
            elif resource=="permissions":
                requested="ADMINISTER,BROWSE_PROJECTS,CREATE_ISSUES,ASSIGN_ISSUES,LINK_ISSUES,SCHEDULE_ISSUES"
                data=get("/rest/api/3/mypermissions",{"permissions":requested,**({"projectKey":project} if project else {})})
                return {"items":[{"id":k,"name":v.get("name",k),"allowed":v["havePermission"]} for k,v in data["permissions"].items()],"next":""}
            elif not project:raise ValueError("Select a Jira project first.")
            elif resource=="types":result=get("/rest/api/3/issue/createmeta/"+project+"/issuetypes",page)
            elif resource=="statuses":
                data=get("/rest/api/3/project/"+project+"/statuses")
                unique={s["id"]:s["name"] for t in data for s in t.get("statuses",[])}
                return {"items":[{"id":k,"name":v} for k,v in unique.items()],"next":""}
            elif resource=="users":
                data=get("/rest/api/3/user/assignable/search",{"project":project,"query":query,**page})
                return {"items":[{"id":u["accountId"],"name":u["displayName"]} for u in data if u.get("active",True)],"next":str(start+len(data)) if len(data)==50 else ""}
            elif resource=="boards":result=get("/rest/agile/1.0/board",{**page,"projectKeyOrId":project})
            else:raise ValueError("Unsupported Jira discovery operation.")
            values=result.get("values",result.get("issueTypes",[]))
            items=[{"id":str(x.get("key") if resource=="projects" else x.get("id")),"name":x["name"],"subtask":bool(x.get("subtask",False))} for x in values]
            more=not result.get("isLast",False) and start+len(values)<result.get("total",start+len(values)+(1 if len(values)==50 else 0))
            return {"items":items,"next":str(start+len(values)) if values and more else ""}
        if service!="Slack" or resource not in {"channels","users"}:raise ValueError("Unsupported discovery operation.")
        headers={"Authorization":"Bearer "+key}
        identity=checked(c.post("https://slack.com/api/auth.test",headers=headers))
        if identity.get("team_id")!=p.slack_team:raise ServiceFailure("Workspace mismatch",403)
        is_channel=resource=="channels"
        params={"limit":100,**({"cursor":cursor} if cursor else {})}
        if is_channel:params.update(types="public_channel,private_channel",exclude_archived="true")
        data=checked(c.get("https://slack.com/api/"+("users.conversations" if is_channel else "users.list"),headers=headers,params=params))
        return {"items":[{"id":x["id"],"name":x.get("real_name") or x.get("name") or x["id"]} for x in data.get("channels" if is_channel else "members",[]) if not x.get("deleted")],"next":data.get("response_metadata",{}).get("next_cursor","")}

def verify_binding(service,destination,p,key):
    """Prove that the target belongs to this workspace before saving a binding."""
    import re
    destination=destination.strip().upper()
    if service not in {"Jira","Slack"}:raise ServiceFailure("Unknown service.",422)
    pattern=r"(?:[A-Z][A-Z0-9_]+|[0-9]+)" if service=="Jira" else r"[CG][A-Z0-9]+"
    if not re.fullmatch(pattern,destination):raise ServiceFailure("Enter a Jira project ID or key." if service=="Jira" else "Enter a Slack channel ID beginning with C or G.",422)
    with Client(timeout=15) as c:
        if service=="Jira":
            auth=(p.jira_email,key)
            row=checked(c.get(p.jira_site+"/rest/api/3/project/"+destination,auth=auth))
            canonical=row.get("key","")
            if destination not in (str(row.get("id")),canonical) or not re.fullmatch(r"[A-Z][A-Z0-9_]+",canonical):
                raise ServiceFailure("Jira returned a different project.",422)
            perms=checked(c.get(p.jira_site+"/rest/api/3/mypermissions",auth=auth,params={"projectKey":canonical,"permissions":"BROWSE_PROJECTS"}))
            if not perms.get("permissions",{}).get("BROWSE_PROJECTS",{}).get("havePermission"):
                raise ServiceFailure("Grant Browse Projects for this Jira project.",403)
            return dict(destination=canonical,external_id=str(row["id"]),resource_name=row["name"],resource_url=p.jira_site+"/browse/"+canonical)
        from .connectors import slack_identity
        slack_identity(c,p,key)
        headers={"Authorization":"Bearer "+key}
        row=checked(c.get("https://slack.com/api/conversations.info",headers=headers,params={"channel":destination}))["channel"]
        if row.get("id")!=destination or row.get("is_archived") or not row.get("is_member"):
            raise ServiceFailure("Invite the bot to an active channel in the configured Slack workspace.",403)
        checked(c.get("https://slack.com/api/conversations.history",headers=headers,params={"channel":destination,"limit":1}))
        return dict(destination=destination,external_id=destination,resource_name=row["name"],resource_url="https://app.slack.com/client/"+p.slack_team+"/"+destination)


def jira_preflight(action,p,key):
    if action.kind not in {"Jira project","Jira issue"}:return
    project=action.destination if action.kind=="Jira issue" else ""
    allowed=options("Jira","permissions",p,key,project)["items"]
    permissions={i["id"] for i in allowed if i["allowed"]}
    required={"ADMINISTER"} if action.kind=="Jira project" else {"CREATE_ISSUES"}
    if action.assignee:required.add("ASSIGN_ISSUES")
    if action.due:required.add("SCHEDULE_ISSUES")
    if not required<=permissions:raise ServiceFailure("Required Jira permission unavailable: "+", ".join(sorted(required-permissions)),403)
    if not project:return
    cursor=""
    while True:
        page=options("Jira","types",p,key,project,cursor)
        match=next((x for x in page["items"] if x["name"].replace("-","").casefold()==(action.reference or "Task").replace("-","").casefold()),None)
        if match:break
        cursor=page["next"]
        if not cursor:raise ServiceFailure("Issue type is unavailable in the linked project",422)
    if action.parent and not action.parent.startswith(project+"-"):raise ServiceFailure("Parent issue belongs to a different project",422)
    if match.get("subtask") and not action.parent:raise ServiceFailure("The selected subtask type requires a parent issue",422)
    return match["name"]

def model_list(service,key):
    if not key:raise ServiceFailure("Enter or save a provider credential first",422)
    providers={
        "OpenAI":("https://api.openai.com/v1/models",{"Authorization":"Bearer "+key}),
        "Anthropic":("https://api.anthropic.com/v1/models",{"x-api-key":key,"anthropic-version":"2023-06-01"}),
        "Gemini":("https://generativelanguage.googleapis.com/v1beta/models",{"x-goog-api-key":key})
    }
    if service not in providers:raise ValueError("Unknown model provider.")
    url,headers=providers[service]
    with Client(timeout=15) as client:data=checked(client.get(url,headers=headers))
    if service=="Gemini":return sorted(x["name"].removeprefix("models/") for x in data.get("models",[]) if "generateContent" in x.get("supportedGenerationMethods",[]))
    return sorted(x["id"] for x in data.get("data",[]))
