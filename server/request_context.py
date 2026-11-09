"""Bound UTF-8 input conservatively and keep recent turns and relevant evidence."""
import json
from .transport import ServiceFailure

def fit_context(model, prompt, evidence, history, policy, max_output, question=None, window_override=0):
    # Application ceiling for larger models. Use a conservative ceiling for unknown IDs.
    large = model.startswith(("gpt-4o","gpt-4.1","gpt-5","claude-3","claude-sonnet","claude-opus","gemini-"))
    window = 65536 if large else 16385 if model == "gpt-3.5-turbo" else 8192
    window = window_override or window
    budget = min(48000, window - max_output - 256) - len(policy.encode())
    def encode():
        return json.dumps(dict(request=prompt, excerpts=refs, prior_messages=turns),
                          default=str, ensure_ascii=False, separators=(",",":"))
    refs, turns = [], []
    if question is not None and prompt.startswith(question):
        supplemental=prompt[len(question):]
        while supplemental and len(encode().encode())>budget//2:
            supplemental=supplemental[:len(supplemental)//2]
            prompt=question+supplemental
    if len(encode().encode()) > budget:
        raise ServiceFailure("Request exceeds the model input budget. Shorten the message or reduce the output limit.",413)
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
