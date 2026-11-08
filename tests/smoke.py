"""Run inside the built app container against a DISPOSABLE compose database."""
import json
import secrets
import time
import uuid
from pathlib import Path
import httpx
from server.db import database
from server.domain import password_hash
import os


def run():
    login=str(uuid.uuid4())
    password=secrets.token_urlsafe(24)
    with database() as db:
        db.execute(Path('server/schema.sql').read_text())
        db.execute('INSERT INTO users(id,login,password,platform_role) VALUES (%s,%s,%s,%s)',(login,login,password_hash(password),"Super Admin"))
    headers={'Origin':os.environ['PUBLIC_ORIGIN']}
    with httpx.Client(base_url='http://localhost:8080/api/',headers=headers) as c:
        assert c.get('projects').status_code==401
        credentials=dict(login=login,password=password)
        assert c.post('login',json=dict(login=login,password='incorrect')).status_code==401
        assert c.get('session').status_code==401
        c.post('login',json=credentials).raise_for_status()
        for _ in range(2):
            assert c.get('session').raise_for_status().json()['role']=='Super Admin'
            c.get('projects').raise_for_status()
        with database() as db:db.execute('UPDATE sessions SET expires=0 WHERE uid=%s',(login,))
        assert c.get('projects').status_code==401
        c.post('login',json=credentials).raise_for_status()
        pid=c.post('projects',json=dict(name='Smoke test',client='Fixture')).raise_for_status().json()['id']
        base=f'projects/{pid}/'
        def upload(name,body,family=''):
            return c.post(base+'files',data=dict(title=name,category='Scope',origin='Fixture',family=family),files={'file':('scope.txt',body)}).raise_for_status().json()['id']
        registry=c.get('agents').raise_for_status().json()
        assert registry[0]['id']=='pm-ai-es'
        cfg=c.get('agents/pm-ai-es').raise_for_status().json()
        policy=dict(cfg['policy'],enabled=False)
        c.put('agents/pm-ai-es/settings',json=dict(revision=cfg['revision'],policy=policy)).raise_for_status()
        assert c.post(base+'agent',json={'action':'health'}).status_code==403
        cfg=c.get('agents/pm-ai-es').raise_for_status().json()
        c.put('agents/pm-ai-es/settings',json=dict(revision=cfg['revision'],policy=dict(policy,enabled=True))).raise_for_status()
        assert 'answer' in c.post(base+'agent',json={'action':'auto','question':'Check project health'}).raise_for_status().json()
        first=upload('Scope v1','Panel thickness 2 mm')
        c.post(base+'sources/'+first+'/approve').raise_for_status()
        second=upload('Scope v2','Panel thickness 3 mm',first)
        assert c.get(base+'search',params={'q':'thickness'}).json()[0]['state']=='approved'
        c.post(base+'sources/'+second+'/approve').raise_for_status()
        assert all('2 mm' not in s['body'] for s in c.get(base+'search',params={'q':'thickness'}).json())
        c.post(base+'messages',json=dict(body='Proposed blue finish',respond=False)).raise_for_status()
        assert c.get(base+'workspace').json()['messages']==[]
        assert c.get('projects/'+str(uuid.uuid4())+'/sources/'+second).status_code==404
        assert c.post(base+'messages',headers={'Origin':'https://other.invalid'},json=dict(body='x',respond=False)).status_code==403
        rule={"frequency":"Weekly","zone":"Asia/Karachi","weekday":0,"hour":8,"audience":"CEO","heading":"Weekly delivery review","recipient":"review@example.invalid"}
        c.put(base+"report-rule",json=rule).raise_for_status()
        assert c.get(base+"report-rule").json()==rule
        today=time.strftime("%Y-%m-%d")
        rid=c.post(base+"report-drafts",json={"start":today,"end":today,"audience":"CEO"}).raise_for_status().json()["id"]
        c.put(base+"report-drafts/"+rid,json={"body":"Reviewed snapshot","revision":1}).raise_for_status()
        assert c.put(base+"report-drafts/"+rid,json={"body":"Stale","revision":1}).status_code==409
        c.patch("projects/"+pid,json={"name":"Audit","client":"Fixture","expertise":"React","target":today}).raise_for_status()
        assert any(p["profile"].get("expertise")=="React" for p in c.get("projects").json())
        with database() as db:
            plan=str(uuid.uuid4())
            db.execute("INSERT INTO plans(id,pid,content) VALUES(%s,%s,%s)",(plan,pid,"Fixture output"))
        fid=c.post(base+"feedback",json={"target":plan,"category":"Scope","body":"Missing source reference"}).raise_for_status().json()["id"]
        assert c.get(base+"improvements").json()[0]["status"]=="draft"
        c.post(base+"improvements/"+fid,json={"approve":True,"evaluation":"Compared proposed rule with approved scope."}).raise_for_status()
        assert c.get(base+"improvements").json()[0]["status"]=="approved"
        from tests.test_knowledge_chat import docx
        marker="ATLAS-"+uuid.uuid4().hex[:12]
        sample=c.post(base+"files",data={"title":"Acceptance annex","category":"Agreement","origin":"QA"},files={"file":("annex.docx",docx("Handover requires "+marker))}).raise_for_status().json()
        assert sample["processing"]=="Ready"
        assert c.get(base+"search",params={"q":marker}).raise_for_status().json()[0]["sid"]==sample["id"]
        thread=c.post(base+"chats",json={"title":"Delivery discussion"}).raise_for_status().json()
        path=base+"chats/"+thread["id"]
        c.post(path+"/turn",json={"revision":0,"body":"Record the handover meeting","respond":False}).raise_for_status()
        messages=c.get(path).raise_for_status().json()["messages"]
        assert len(messages)==1 and messages[0]["role"]=="user"
        branch=c.post(path+"/branch/"+messages[0]["id"]).raise_for_status().json()
        assert c.get(base+"chats/"+branch["id"]).raise_for_status().json()["messages"]==[]
        c.patch(path,json={"title":"Renamed handover"}).raise_for_status()
        assert any(t["id"]==thread["id"] for t in c.get(base+"chats?q=Renamed").json())
        p2=c.post("projects",json={"name":"Other project","client":"QA"}).raise_for_status().json()["id"]
        assert c.get("projects/"+p2+"/chats/"+thread["id"]).status_code==404
        assert c.get("projects/"+p2+"/search",params={"q":marker}).raise_for_status().json()==[]
        review=base+"conversation-feedback"
        correction=dict(thread_id=thread["id"],message_ids=[messages[0]["id"]],category="Response style",body="Lead with the deadline.")
        assert c.post("projects/"+p2+"/conversation-feedback",json=correction).status_code==404
        assert c.post(review,json={**correction,"message_ids":["unrelated"]}).status_code==422
        key=c.post(review,json=correction).raise_for_status().json()["id"]
        item=next(r for r in c.get(review).raise_for_status().json() if r["id"]==key)
        assert item["thread_id"]==thread["id"] and item["message_ids"]==correction["message_ids"]
        assert c.get(review+"/"+key+"/evidence").raise_for_status().json()["messages"][0]["body"]==messages[0]["body"]
        decision=dict(text="Lead with the deadline when known.",version=item["edit_version"],action="save")
        route=review+"/"+key+"/decision"
        c.post(route,json=decision).raise_for_status()
        assert c.post(route,json=decision).status_code==409
        decision.update(version=decision["version"]+1,action="approve")
        assert c.post(route,json=decision).raise_for_status().json()["applied"]["scope"]=="project"
        decision.update(version=decision["version"]+1,action="rollback")
        assert c.post(route,json=decision).raise_for_status().json()["status"]=="rolled back"
        assert len(c.get(review+"/"+key+"/evidence").raise_for_status().json()["versions"])==4
        failed=c.post(base+"files",data={"title":"Unreadable","category":"Scope","origin":"QA"},files={"file":("bad.docx",b"damaged")}).raise_for_status().json()
        assert failed["processing"]=="Failed"
        assert c.post(base+"sources/"+failed["id"]+"/retry").raise_for_status().json()["error"]
        c.post('logout').raise_for_status()
        assert c.get('projects').status_code==401
    print("HTTP smoke checks passed.")


if __name__=='__main__': run()
