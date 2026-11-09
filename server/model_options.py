"""Build generation options shared by chat and the administrator's model probe."""
import json
from .transport import ServiceFailure

# The adapter owns request identity, conversation, credentials, tools and delivery.
RESERVED = set("""model messages contents system systemInstruction tools tool_choice toolConfig functions function_call
mcp_servers web_search_options container apiKey apiSecret auth authorization credentials stream stream_options generationConfig headers url api_key authorization n candidateCount
max_tokens max_completion_tokens maxOutputTokens temperature top_p topP reasoning_effort""".split())

def model_config(p, fallback=False):
    prefix = "fallback_" if fallback else ""
    inherit = fallback and p.fallback_inherit
    shared = "" if inherit else prefix
    config = dict(provider=getattr(p,prefix+"provider"), model=getattr(p,prefix+"model"),
                  context_window=getattr(p,prefix+"context_window"),
                  custom=getattr(p,prefix+"parameters"), top_p=getattr(p,shared+"top_p"),
                  effort=getattr(p,shared+"reasoning_effort"))
    return config, getattr(p,shared+"max_tokens"), getattr(p,shared+"temperature")

def generation_options(config, limit, temperature):
    provider=config["provider"]
    gemini=provider=="Gemini"
    options=dict(config.get("custom") or {})
    blocked=RESERVED.intersection(options)
    if blocked:
        raise ServiceFailure("Use the dedicated field or adapter for "+", ".join(sorted(blocked))+".",422)
    if provider=="Anthropic" and limit is None:
        raise ServiceFailure("Anthropic Messages requires maximum output tokens.",422)
    if config.get("top_p") is not None and not 0<=config["top_p"]<=1:
        raise ServiceFailure("Top-p is a probability. Enter a value from 0 to 1.",422)
    if limit is not None:
        key={"OpenAI":"max_completion_tokens","Gemini":"maxOutputTokens","Anthropic":"max_tokens"}[provider]
        options[key]=limit
    if temperature is not None:options["temperature"]=temperature
    if config.get("top_p") is not None:options["topP" if gemini else "top_p"]=config["top_p"]
    effort=config.get("effort")
    if effort:
        if provider=="OpenAI":options["reasoning_effort"]=effort
        else:
            group,field=("thinkingConfig","thinkingLevel") if gemini else ("output_config","effort")
            nested=options.get(group,{})
            if not isinstance(nested,dict) or field in nested:
                raise ServiceFailure(f"Configure {group}.{field} only once.",422)
            options[group]={**nested,field:effort}
    try:json.dumps(options,allow_nan=False)
    except (ValueError,TypeError):raise ServiceFailure("Generation parameters must contain finite JSON values.",422)
    return options
