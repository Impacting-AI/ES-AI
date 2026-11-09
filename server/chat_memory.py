"""Bounded extractive memory. Text is a conversation aid, never a scope approval."""
def digest(messages,previous=""):
    entries=previous.splitlines()
    for m in messages:
        body=" ".join(m["body"].split())
        entry=m["role"]+": "+body[:190]+" "+str(m.get("refs","[]"))[:100]
        if entry not in entries:entries.append(entry)
    # Keep opening anchors, then the most recent distinct turns.
    anchors=entries[:3]
    important=[e for e in entries if any(term in e.lower() for term in ("approved","decided","blocked","unresolved","pending","decision"))][-4:]
    ordered=list(dict.fromkeys(anchors+important+entries[-7:]))
    return "\n".join(ordered)[:4200]
