"""JSON HTTP transport. Only type and status escape an unsuccessful provider call."""
import base64
import json
import re
import random
import time
from email.utils import parsedate_to_datetime
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class ServiceFailure(Exception):
    def __init__(self, category, code, *, transient=False):
        self.category, self.code = category, code
        self.transient = transient
        self.retry_after = 0.0
        self.request_id = ""
        self.rejected = False
        super().__init__(category)


def retry_delay(exc, index, emitted, cancelled):
    """Return a bounded pre-output retry delay, or None when replay is unsafe."""
    if index or emitted or cancelled or not exc.transient:
        return None
    delay=max(exc.retry_after,0.5*(2**index)+random.uniform(0,0.4))
    return delay if delay<=4 else None


def response_metadata(headers):
    headers = {k.lower():v for k,v in (headers or {}).items()}
    request_id = headers.get("x-request-id") or headers.get("request-id") or headers.get("x-goog-request-id","")
    return request_id if re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}",request_id) else ""

def failure(status, body=b"", headers=None):
    exc = classify(status, body)
    exc.rejected = status in (400,401,402,403,404,413,422,429)
    exc.request_id = response_metadata(headers)
    delay = (headers or {}).get("Retry-After","0")
    try:exc.retry_after = max(0,float(delay))
    except (ValueError,TypeError):
        try:exc.retry_after = max(0,parsedate_to_datetime(delay).timestamp()-time.time())
        except (ValueError,TypeError,OverflowError):pass
    return exc

def classify(status, body):
    e={}
    try:
        payload=json.loads(body)
        e=payload.get("error",{})
        reason=str(e).lower()
    except (ValueError,AttributeError):reason=""
    if any(s in reason for s in ("context_length_exceeded","context window","too many input tokens","input is too long")):
        return ServiceFailure("Model context limit reached. Shorten the message or lower the output limit.",413)
    if any(s in reason for s in ("insufficient_quota","billing","credit balance","quota_exceeded")) or status==402:
        return ServiceFailure("Quota or billing limit reached",429)
    if status==401 or any(s in reason for s in ("api_key_invalid","invalid_auth","invalid_api_key","token_revoked","not_authed")):
        return ServiceFailure("Invalid credentials",401)
    if status==403 or any(s in reason for s in ("missing_scope","insufficient_permissions","not_in_channel","not_allowed_token_type")):
        return ServiceFailure("Insufficient permissions",403)
    if status==404 or any(s in reason for s in ("model_not_found","unknown_model","channel_not_found","thread_not_found")):
        return ServiceFailure("Requested model or resource unavailable",404)
    if status==429 or "rate_limit_exceeded" in reason or "rate_limit_error" in reason:return ServiceFailure("Service rate limit reached",429,transient=True)
    if status in (400,422) and re.search(r"\b(stream|stream_options|streaming)\b",reason) and any(s in reason for s in ("unsupported","not support","unrecognized","unknown parameter")):return ServiceFailure("Unsupported stream parameters",422)
    if status in (400,422) and isinstance(e,dict):
        param=e.get("param") or ""
        msg=str(e.get("message",""))
        if not param:
            match=re.search(r"(?:parameter|field|argument|unknown name)[: ]+['\"]([A-Za-z_][.\w]*)['\"]|^([a-z_][.\w]*)\s*:",msg,re.I)
            param=next((g for g in match.groups() if g),"") if match else ""
        if isinstance(param,str) and re.fullmatch(r"[a-zA-Z_][.\w]{0,95}",param):
            limits=re.search(r"(?:at most|less than or equal to|maximum(?: value)?(?: is| of)?|supports at most)\s+([\d,.]+)",msg,re.I)
            note=(" Provider maximum: "+limits[1].rstrip(".")+".") if limits else ""
            return ServiceFailure("The selected model rejected parameter "+param+". Change or remove it."+note,422)
    if status in (400,422):return ServiceFailure("Service rejected the selected model parameters or request fields",422)
    return ServiceFailure("Network or service error",502,transient=status in (408,500,502,503,504,529))


class Result:
    def __init__(self,status,body,headers=None):
        self.status_code,self.body,self.headers=status,body,headers or {}

    def raise_for_status(self):
        if not 200<=self.status_code<300:raise failure(self.status_code,self.body,self.headers)

    def json(self):return json.loads(self.body)


class Client:
    def __init__(self,timeout=30):
        self.request_id=""
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
        except (URLError,TimeoutError,OSError,IncompleteRead) as exc:
            raise ServiceFailure("Network or service error",502,transient=True) from exc

    def events(self,url,headers,payload):
        request=Request(url,data=json.dumps(payload).encode(),headers={**headers,"Content-Type":"application/json","Accept":"text/event-stream"},method="POST")
        try:
            with self.opener.open(request,timeout=self.timeout) as response:
                self.request_id=response_metadata(response.headers)
                total=0
                deadline=time.monotonic()+120
                for line in response:
                    if time.monotonic()>deadline:
                        raise ServiceFailure("Response timed out. Retry your message.",504,transient=True)
                    total+=len(line)
                    if total>8*1024**2:raise ServiceFailure("Stream size limit reached",502)
                    if line.startswith(b"data:"):
                        value=line[5:].strip()
                        if value==b"[DONE]":return
                        if value:yield json.loads(value)
        except HTTPError as e:
            try:raise failure(e.code,e.read(32768),e.headers)
            finally:e.close()
        except (URLError,TimeoutError,OSError,IncompleteRead) as e:raise ServiceFailure("Stream disconnected",502,transient=True) from e

    def post(self,url,*,headers=None,auth=None,json=None):
        return self.request("POST",url,headers=headers,auth=auth,payload=json)

    def get(self,url,*,headers=None,auth=None,params=None):
        return self.request("GET",url,headers=headers,auth=auth,params=params)
