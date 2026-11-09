"""Bound UTF-8 input conservatively and keep recent turns and relevant evidence."""
import json
from .transport import ServiceFailure

def fit_context(model, prompt, evidence, history, policy, max_output, question=None, window_override=0):
    # Only an explicitly configured window triggers local evidence trimming.
    # UTF-8 bytes are a conservative estimate. The provider validates the final token count.
    budget = max(0,window_override-(max_output or 0)-len(policy.encode())) if window_override else float("inf")
    def encode():
        return json.dumps(dict(request=prompt, excerpts=refs, prior_messages=turns),
                          default=str, ensure_ascii=False, separators=(",",":"))
    refs, turns = [], []
    if question is not None and prompt.startswith(question):
        supplemental=prompt[len(question):]
        while supplemental and len(encode().encode())>budget//2:
            supplemental=supplemental[:len(supplemental)//2]
            prompt=question+supplemental
    if window_override and max_output and max_output>=window_override:
        raise ServiceFailure("Maximum output tokens must leave room for input in the configured context window.",413)
    seen = set()
    for ref in evidence:
        key = (ref.get("id"), ref.get("body",""))
        if key not in seen:
            refs.append(ref)
            seen.add(key)
    turns.extend(history)
    while len(encode().encode()) > budget:
        if len(turns)>2:turns.pop(0)
        elif len(refs)>1:refs.pop()
        elif refs and len(refs[0].get("body",""))>256:
            ref=refs[0]
            refs[0]=dict(ref,body=ref["body"][:len(ref["body"])//2])
        elif turns:turns.pop(0)
        elif refs:refs.pop()
        else:break
    return encode()
