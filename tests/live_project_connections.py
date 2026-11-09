"""Run inside app container on a disposable instance with two small populated test resources per provider."""
import getpass
import os
from uuid import uuid4

import httpx


def run():
    origin=os.environ["PUBLIC_ORIGIN"]
    resources={s:input("Two dedicated "+s+" IDs or keys, comma separated: ").strip().split(",") for s in ("Jira","Slack")}
    if any(len(ids)!=2 or len(set(x.strip() for x in ids))!=2 for ids in resources.values()):
        raise ValueError("Use two distinct test resources for each provider.")
    with httpx.Client(base_url="http://localhost:8080/api/",headers={"Origin":origin},timeout=150) as c:
        def call(method,path,**kwargs):
            result=c.request(method,path,**kwargs)
            result.raise_for_status()
            return result.json()
        call("POST","login",json={"login":input("Administrator: "),"password":getpass.getpass()})
        policy=call("GET","agents/pm-ai-es")
        for service in resources:
            assert call("POST","connections/"+service+"/test",json={"revision":policy["revision"],"policy":policy["policy"]})["ok"]
        for index in range(2):
            pid=call("POST","projects",json={"name":"Connection QA "+uuid4().hex[:8],"client":"Internal fixture"})["id"]
            base="projects/"+pid+"/"
            for service,ids in resources.items():
                spec={"service":service,"destination":ids[index].strip(),"expected":""}
                tested=call("POST",base+"link/test",json=spec)
                call("PUT",base+"link",json=spec)
                link=next(x for x in call("GET",base+"connections") if x["service"]==service)
                assert link["connected"] and link["external_id"]==tested["external_id"]
                while call("POST",base+"sync/"+service)["more"]:pass
                events=[x["record"] for x in call("GET",base+"delivery")["events"] if x["service"]==service]
                assert events,"Populate both fixture resources before running the test."
                assert all((r["issue"].split("-")[0] if service=="Jira" else r["channel"])==tested["destination"] for r in events)
                call("DELETE",base+"link/"+service,params={"expected":link["mapping_id"]})
                assert all(x["service"]!=service for x in call("GET",base+"delivery")["events"])
                call("PUT",base+"link",json=spec)
        print("Authenticated workspace tests, mapping persistence, scoped imports, disconnect and reconnect passed.")


if __name__=="__main__":run()
