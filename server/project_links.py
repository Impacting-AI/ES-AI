"""Project mappings hold verified destinations, never credentials."""
from .discovery import verify_binding
from .transport import Client,ServiceFailure
from .connectors import checked

def workspace(service,p):
    return p.jira_site if service=="Jira" else p.slack_team

def validate(service,destination,board,p,key):
    if not key or not workspace(service,p):raise ServiceFailure("Configure the global connection in Integrations first.",409)
    row=verify_binding(service,destination,p,key)
    if board:
        if service!="Jira":raise ServiceFailure("A board ID applies only to Jira.",422)
        with Client(timeout=15) as c:
            data=checked(c.get(p.jira_site+"/rest/agile/1.0/board/"+board,auth=(p.jira_email,key)))
        if (data.get("location") or {}).get("projectKey")!=row["destination"]:
            raise ServiceFailure("Choose a board belonging to the selected Jira project.",422)
    return row

def store_mapping(db,pid,service,site,resource,board=None,expected=None):
    # All callers serialize mapping changes with the agent settings lock.
    existing=db.execute("SELECT * FROM project_links WHERE pid=%s AND service=%s FOR UPDATE",(pid,service)).fetchone()
    if expected is not None and expected!=str(existing["mapping_id"] if existing else ""):
        raise ServiceFailure("Mapping changed. Refresh project settings.",409)
    conflict=db.execute("SELECT pid FROM project_links WHERE service=%s AND workspace=%s AND destination=%s AND pid<>%s",(service,site,resource["destination"],pid)).fetchone()
    if conflict:raise ServiceFailure("That resource is already linked to another project.",409)
    if existing and (site,resource["destination"])!=(existing["workspace"],existing["destination"]):
        db.execute("DELETE FROM project_links WHERE pid=%s AND service=%s",(pid,service))
    db.execute("""INSERT INTO project_links(pid,service,workspace,destination,external_id,resource_name,resource_url,board_id,verified_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(pid,service) DO UPDATE SET
        external_id=excluded.external_id,resource_name=excluded.resource_name,resource_url=excluded.resource_url,board_id=excluded.board_id,
        verified_at=now(),updated_at=now(),queued=true,poll_after=now()""",
        (pid,service,site,resource["destination"],resource["external_id"],resource["resource_name"],resource["resource_url"],board or None))

def guard_dispatch(db,pid,service):
    if db.execute("SELECT 1 FROM agent_actions WHERE pid=%s AND service=%s AND status='dispatching'",(pid,service)).fetchone():
        raise ServiceFailure("An approved action is being published. Retry when it finishes.",409)
