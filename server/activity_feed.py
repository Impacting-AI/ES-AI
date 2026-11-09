import json
from .transport import ServiceFailure
from datetime import datetime,timezone
from .connectors import checked,slack_identity

def adf_text(value):
    if isinstance(value,str):return value
    if not isinstance(value,dict):return ""
    return (value.get("text","")+" "+" ".join(adf_text(child) for child in value.get("content",[]))).strip()

def read_page(c,service,link,p,key,start,full):
    target=link["destination"]
    cursor=link["scan_cursor"]
    since=link["last_sync"]
    if service=="Jira":
        jql="project = "+target
        if since and not full:
            # Use relative minutes so Jira account timezone settings cannot shift the window.
            minutes=max(2,int((start-since).total_seconds()/60)+2)
            jql+=f' AND updated >= "-{minutes}m"'
        params={"jql":jql+" ORDER BY updated ASC","maxResults":100,"fields":"summary,project,issuetype,status,assignee,updated,duedate,description,comment,worklog,attachment,fixVersions,parent,progress"}
        if cursor:params["nextPageToken"]=cursor
        data=checked(c.get(p.jira_site+"/rest/api/3/search/jql",params=params,auth=(p.jira_email,key)))
        events=[]
        for issue in data["issues"]:
            f=issue["fields"]
            if (f.get("project") or {}).get("key")!=target or not issue["key"].startswith(target+"-"):continue
            record=dict(title=f["summary"],issue=issue["key"],url=p.jira_site+"/browse/"+issue["key"],status=f["status"]["name"],
                status_group=p.jira_status_map.get(f["status"]["name"],""),due=f.get("duedate"),assignee=(f.get("assignee") or {}).get("displayName"),
                issue_type=f["issuetype"]["name"],description=adf_text(f.get("description"))[:4000],parent=(f.get("parent") or {}).get("key"),
                milestones=[v["name"] for v in f.get("fixVersions",[])],progress=f.get("progress"),
                comments=[dict(text=adf_text(x.get("body"))[:2000],created=x.get("created")) for x in (f.get("comment") or {}).get("comments",[])],
                worklogs=[dict(seconds=x.get("timeSpentSeconds"),started=x.get("started"),author=(x.get("author") or {}).get("displayName")) for x in (f.get("worklog") or {}).get("worklogs",[])],
                attachments=[dict(name=x.get("filename"),url=x.get("content")) for x in f.get("attachment",[])])
            events.append((issue["key"]+"@"+f["updated"],f["updated"],record))
        return events,data.get("nextPageToken","")
    slack_identity(c,p,key)
    state=json.loads(cursor) if cursor.startswith("{") else {"page":cursor,"threads":[]}
    threads=state["threads"]
    headers={"Authorization":"Bearer "+key}
    if threads:
        parent=threads[0]
        params={"channel":target,"ts":parent,"limit":100,"latest":str(start.timestamp())}
        if state.get("replies"):params["cursor"]=state["replies"]
        try:
            data=checked(c.get("https://slack.com/api/conversations.replies",headers=headers,params=params))
        except ServiceFailure as exc:
            if exc.code!=403:raise
            # Some bot tokens can read channel history but cannot read its threads.
            data={"messages":[]}
            state["thread_warning"]=True
        state["replies"]=(data.get("response_metadata") or {}).get("next_cursor","")
        if not state["replies"]:threads.pop(0)
    else:
        params={"channel":target,"limit":100,"latest":str(start.timestamp())}
        if since and not full:params["oldest"]=str(max(0,since.timestamp()-60))
        if state["page"]:params["cursor"]=state["page"]
        data=checked(c.get("https://slack.com/api/conversations.history",headers=headers,params=params))
        state["page"]=(data.get("response_metadata") or {}).get("next_cursor","")
        threads.extend(m["ts"] for m in data["messages"] if m.get("reply_count"))
    events=[(m["ts"],datetime.fromtimestamp(float(m["ts"]),timezone.utc),dict(title=m.get("text","")[:4000],sender=m.get("user"),channel=target,
            thread=m.get("thread_ts"),references=[f.get("permalink") for f in m.get("files",[]) if f.get("permalink")])) for m in data["messages"]]
    link["thread_warning"]=state.get("thread_warning",False)
    return events,json.dumps(state) if threads or state["page"] else ""
