from datetime import datetime,timezone

def render(project,head,period,events,approved):
    lines=[f"Project: {project['name']}",f"Client: {project['client']}",f"Project head: {head or 'Unassigned'}",
           f"Report date: {datetime.now(timezone.utc).date()} UTC",f"Reporting period: {period.start} to {period.end} (UTC)"]
    latest={}
    for row in events:
        if row['service']=='Jira':latest[row['record']['issue']]=row['record']
    lines+=["","Executive summary",f"{len(latest)} Jira issues have an imported update in the reporting period. {len(approved)} scope approvals were recorded."]
    groups={'Recorded as done':[],'Review and testing':[],'Work in progress':[],'Remaining and upcoming work':[],'Blockers and other statuses':[]}
    for key,issue in latest.items():
        status=issue['status'].casefold()
        group='Recorded as done' if status in {'done','closed','resolved'} else 'Review and testing' if any(x in status for x in ('review','test','qa')) else 'Work in progress' if status in {'in progress','implementing'} else 'Remaining and upcoming work' if status in {'open','to do','backlog'} else 'Blockers and other statuses'
        # Internal issue titles and links require deliberate disclosure in client drafts.
        label=(issue['issue']+' · '+issue['title']+' · '+issue['url']) if period.audience=='CEO' else issue['issue']
        group={'Remaining':'Remaining and upcoming work','In progress':'Work in progress','Review':'Review and testing','Done':'Recorded as done','Blocked':'Blockers and other statuses'}.get(issue.get('status_group'),group)
        groups[group].append(label+' · '+issue['status'])
    for name,items in groups.items():lines+=['',name,*(items or ['No matching issue updates in the imported records.'])]
    delayed=[x['issue'] for x in latest.values() if x.get('due') and x['due']<period.end.isoformat() and (x.get('status_group') or x['status']).casefold() not in {'done','closed','resolved'}]
    lines+=['','Overdue in the imported snapshots',', '.join(delayed) if delayed else 'No overdue issues identified in the available dates.']
    lines+=['','Important decisions' ,*([f"Scope approval · {a['title']} · v{a['version']}" for a in approved] if period.audience=='CEO' else [f"{len(approved)} scope approvals during this period."])]
    lines+=['','Verification','Recorded issue statuses do not establish acceptance-test results. Coverage depends on the latest successful project imports.']
    if period.audience=='CEO':
        slack=[e for e in events if e['service']=='Slack']
        lines+=['','Team activity',f'{len(slack)} imported Slack updates during the period.']
    return '\n'.join(lines)


