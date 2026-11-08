"""Bound request size before multipart parsing or PDF handling."""
class BodyLimit:
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] in {"GET","HEAD","OPTIONS"}:
            return await self.app(scope,receive,send)
        limit=(6 if scope["path"].endswith("/files") else 2)*1024**2
        size=0
        chunks=bytearray()
        while True:
            event=await receive()
            if event["type"]=="http.disconnect":return
            part=event.get("body",b"")
            size+=len(part)
            if size>limit:
                await send({"type":"http.response.start","status":413,"headers":[(b"content-type",b"application/json")]})
                await send({"type":"http.response.body","body":b'{"detail":"Request exceeds upload limit."}'})
                return
            chunks.extend(part)
            if not event.get("more_body"):break
        pending=True
        async def replay():
            nonlocal pending
            if not pending:return await receive()
            pending=False
            return {"type":"http.request","body":bytes(chunks),"more_body":False}
        return await self.app(scope,replay,send)
