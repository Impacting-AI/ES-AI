"""Authenticated notifications schedule a scoped provider read."""
import hashlib
import hmac
import time
from urllib.parse import urlsplit


def authenticated(provider,secret,headers,body,now=None):
    if not secret:
        return False
    if provider=="Slack":
        stamp=headers.get("x-slack-request-timestamp","")
        if not stamp.isascii() or not stamp.isdigit() or len(stamp)>12 or abs((now if now is not None else time.time())-int(stamp))>300:
            return False
        prefix="v0="
        payload=b"v0:"+stamp.encode()+b":"+body
        signature=headers.get("x-slack-signature","")
    else:
        prefix="sha256="
        payload=body
        signature=headers.get("x-hub-signature","")
    expected=prefix+hmac.new(secret.encode(),payload,hashlib.sha256).hexdigest()
    return signature.isascii() and hmac.compare_digest(expected,signature)


def destination(provider,event):
    if provider=="Slack":
        message=event.get("event") or {}
        return event.get("team_id"),message.get("channel"),bool(message.get("thread_ts")) or message.get("subtype") in ("message_changed","message_deleted")
    issue=event.get("issue") or {}
    project=(issue.get("fields") or {}).get("project") or event.get("project") or {}
    url=urlsplit(project.get("self") or issue.get("self") or "")
    return url.scheme+"://"+url.netloc,project.get("key"),event.get("webhookEvent") in ("jira:issue_deleted","project_deleted")
