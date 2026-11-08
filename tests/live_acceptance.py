"""Operator-run test on a disposable local installation. Never prints credentials."""
import getpass
from datetime import datetime,timezone
import os
import time
from uuid import uuid4
import httpx
from server.db import database

def run():
    user=input("Administrator username: ").strip()
    password=getpass.getpass("Password: ")
    headers={"Origin":os.environ["PUBLIC_ORIGIN"]}
    suffix=uuid4().hex[:10]
    with httpx.Client(base_url="http://localhost:8080/api/",headers=headers,timeout=150) as client:
        def request(method,path,**kwargs):
            r=client.request(method,path,**kwargs)
            if not r.is_success:
                detail=r.json().get("detail",r.status_code) if r.headers.get("content-type","").startswith("application/json") else r.status_code
                raise RuntimeError(f"{method} {path.split('?')[0]}: {detail}")
            return r.json()
        def login():
            code=getpass.getpass("Current six-digit authenticator code (use a new code after logout): ")
            request("POST","login",json={"login":user,"password":password,"code":code})
        request("GET","health");login()
        pid=request("POST","projects",json={"name":"Acceptance "+suffix,"client":"Internal fixture"})["id"]
        base="projects/"+pid+"/"
        marker="COBALT-"+suffix.upper()
        saved=request("POST",base+"files",data={"title":"Approved fixture scope","origin":"Acceptance","category":"Scope","description":"Custom fixture description"},files={"file":("scope.txt",("The acceptance colour is cobalt. The handover identifier is "+marker).encode())})
        request("POST",base+"sources/"+saved["id"]+"/approve")
        before=len(request("GET",base+"workspace")["messages"])
        request("POST",base+"messages",json={"body":"Fixture discussion about cobalt","respond":False})
        ws=request("GET",base+"workspace")
        assert len(ws["messages"])==before and any(s["description"]=="Custom fixture description" for s in ws["sources"])
        assert request("GET",base+"search",params={"q":"cobalt"})
        print("PASS: project, upload, custom metadata, draft note and retrieval.")
        d=request("GET","agents/pm-ai-es")
        passed=[]
        for service in [d["policy"]["provider"],"Jira","Slack"]:
            if not d["credentials"].get(service):
                print("SKIPPED:",service,"has no stored credential.")
                continue
            parameters={"revision":d["revision"],"policy":d["policy"]}
            result=request("POST","connections/"+service+"/test",json=parameters)
            if not result["ok"]:print("FAILED:",service,result["detail"]);continue
            if service in {"Jira","Slack"}:
                resource="projects" if service=="Jira" else "channels"
                found=request("GET","connections/"+service+"/options/"+resource)
                assert isinstance(found["items"],list)
            else:
                tid=request("POST",base+"chats",json={"title":"Live retrieval test"})["id"]
                path=base+"chats/"+tid
                def send(question,revision):
                    response=client.post(path+"/turn",json={"body":question,"revision":revision})
                    response.raise_for_status()
                    import json
                    events=[json.loads(line) for line in response.iter_lines() if line]
                    assert any(x['type']=='done' for x in events),events[-2:]
                    return request("GET",path)["messages"][-1]
                answer=send("Give the handover identifier from the scope and cite the exact excerpt ID.",0)
                assert marker in answer["body"]
                assert any(ref.get("sid")==saved["id"] for ref in answer["citations"])
                follow=send("Repeat that identifier exactly.",1)
                assert marker in follow["body"]
                print("PASS: unique identifier, saved citation, streaming and contextual follow-up.")
            passed.append(service)
            print("PASS:",service,"generation and message retrieval" if service==d["policy"]["provider"] else "identity and resource discovery")
        request("POST","logout")
        assert client.get(base+"workspace").status_code==401
        print("Sign in again using a fresh authenticator code.")
        login()
        assert any(p["id"]==pid for p in request("GET","projects"))
        assert request("GET",base+"sources/"+saved["id"])["description"]=="Custom fixture description"
        print("PASS: data persisted across logout and fresh login. Project ID:",pid)
        print("Verified live services:",", ".join(passed) or "none")

if __name__=="__main__":run()
