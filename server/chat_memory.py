"""Bounded extractive memory. Text is a conversation aid, never a scope approval."""
def digest(messages,previous=""):
    entries=previous.splitlines()
    for m in messages:
        body=" ".join(m["body"].split())
        entry=m["role"]+": "+body[:190]+" "+str(m.get("refs","[]"))[:100]
        if entry not in entries:entries.append(entry)
    # Keep opening anchors, then the most recent distinct turns.
    anchors=entries[:3]
    return "\n".join(anchors+[e for e in entries[-11:] if e not in anchors])[:4200]
