"""JSON HTTP transport. Only type and status escape an unsuccessful provider call."""
import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class ServiceFailure(Exception):
    def __init__(self, category, code):
        self.category, self.code = category, code
        super().__init__(category)


def failure(status, body=b""):
    try:
        payload=json.loads(body)
        e=payload.get("error",{})
        reason=str(e).lower()
    except (ValueError,AttributeError):reason=""
    if any(s in reason for s in ("insufficient_quota","billing","credit balance","resource_exhausted","quota_exceeded")) or status==402:
        return ServiceFailure("Quota or billing limit reached",429)
    if status==401 or any(s in reason for s in ("api_key_invalid","invalid_auth","invalid_api_key","token_revoked","not_authed")):
        return ServiceFailure("Invalid credentials",401)
    if status==403 or any(s in reason for s in ("missing_scope","insufficient_permissions","not_in_channel")):
        return ServiceFailure("Insufficient permissions",403)
    if status==404 or any(s in reason for s in ("model_not_found","unknown_model")):
        return ServiceFailure("Requested model or resource unavailable",404)
    if status==429:return ServiceFailure("Service rate limit reached",429)
    if status in (400,422):return ServiceFailure("Service rejected the selected model parameters or request fields",422)
    return ServiceFailure("Network or service error",502)


class Result:
    def __init__(self,status,body,headers=None):
        self.status_code,self.body,self.headers=status,body,headers or {}

    def raise_for_status(self):
        if not 200<=self.status_code<300:raise failure(self.status_code,self.body)

    def json(self):return json.loads(self.body)


class Client:
    def __init__(self,timeout=30):
        self.timeout=timeout
        self.opener=build_opener(NoRedirect())

    def __enter__(self):return self
    def __exit__(self,*exc):return False

    def request(self,method,url,*,headers=None,auth=None,params=None,payload=None):
        headers=dict(headers or {})
        if auth:
            credentials=(auth[0]+":"+auth[1]).encode()
            headers["Authorization"]="Basic "+base64.b64encode(credentials).decode()
        if params:url+="?"+urlencode(params)
        data=None
        if payload is not None:
            data=json.dumps(payload).encode()
            headers["Content-Type"]="application/json"
        request=Request(url,data=data,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=self.timeout) as response:
                body=response.read(4*1024*1024+1)
                if len(body)>4*1024*1024:raise ServiceFailure("Service response exceeded the limit",502)
                return Result(response.status,body,response.headers)
        except HTTPError as error:
            try:return Result(error.code,error.read(32768),error.headers)
            finally:error.close()
        except (URLError,TimeoutError,OSError) as exc:
            raise ServiceFailure("Network or service error",502) from exc

    def events(self,url,headers,payload):
        request=Request(url,data=json.dumps(payload).encode(),headers={**headers,"Content-Type":"application/json","Accept":"text/event-stream"},method="POST")
        try:
            with self.opener.open(request,timeout=self.timeout) as response:
                total=0
                for line in response:
                    total+=len(line)
                    if total>8*1024**2:raise ServiceFailure("Stream size limit reached",502)
                    if line.startswith(b"data:"):
                        value=line[5:].strip()
                        if value==b"[DONE]":return
                        if value:yield json.loads(value)
        except HTTPError as e:
            try:raise failure(e.code,e.read(32768))
            finally:e.close()
        except (URLError,TimeoutError,OSError) as e:raise ServiceFailure("Stream disconnected",502) from e

    def post(self,url,*,headers=None,auth=None,json=None):
        return self.request("POST",url,headers=headers,auth=auth,payload=json)

    def get(self,url,*,headers=None,auth=None,params=None):
        return self.request("GET",url,headers=headers,auth=auth,params=params)
