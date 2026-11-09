"""Keep passage identifiers on the server and render conversational text separately."""
import re

UUID = r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}"
MARKER = re.compile(r" *\[(?:S\d+|"+UUID+r"(?:\.\d+)?)(?:\s*[,;]\s*(?:S\d+|"+UUID+r"(?:\.\d+)?))*\]")
RAW_CHUNK = re.compile(r"\b"+UUID+r"\.\d+\b")

def clean_text(text):
    return RAW_CHUNK.sub("",MARKER.sub("",text)).replace(". .",".")

def public_messages(messages):
    for message in messages:
        if message["role"]=="assistant":
            text=clean_text(message["body"])
            for source in message.get("citations") or []:
                text=re.sub(r" *"+re.escape("["+source["id"]+"]"),"",text)
            message["body"]=clean_text(text)
    return messages

def chat_evidence(refs):
    # The server retains the full source record for document navigation.
    return [dict({k:r[k] for k in ("title","state","location","version","body","happened") if k in r},
                 id=f"S{i}") for i,r in enumerate(refs,1)]

def cited_sources(text, refs, used):
    labels={token for marker in MARKER.finditer(text) for token in re.findall(r"S\d+",marker[0])}
    return [{k:r[k] for k in ("id","sid","title","state","location","body","kind","version") if k in r}
            for i,r in enumerate(refs,1) if f"S{i}" in labels and f"S{i}" in used]

STREAM_TOKEN=re.compile(r" *\[[^\]\n]*(?:\]|\n)| *[^\s\[]+(?=[\s\[])| *[\t\r\n]+")

class VisibleStream:
    """Hold the unfinished word or bracketed reference across provider events."""
    def __init__(self,emit):
        self.emit=emit
        self.pending=""
    def write(self,value):
        self.pending+=value
        # A bracket expression is atomic even when a provider splits it at a comma.
        end=0
        while end<len(self.pending):
            match=STREAM_TOKEN.match(self.pending,end)
            if not match:break
            end=match.end()
        if end:
            ready,self.pending=self.pending[:end],self.pending[end:]
            value=clean_text(ready)
            if value:self.emit(value)
    def finish(self):
        if self.pending:self.emit(clean_text(self.pending))
        self.pending=""
