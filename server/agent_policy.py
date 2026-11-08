"""Typed, versioned configuration for the Project Management agent."""
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["OpenAI","Anthropic","Gemini"]
Action = Literal["answer","plan","health"]
class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(default="PM AI ES", min_length=1,max_length=80)
    department: str = Field(default="Project Management", min_length=1,max_length=100)
    description: str = Field(default="Review project evidence, draft plans and identify delivery risks.",max_length=600)
    enabled: bool = True
    language: str = Field(default="English",min_length=1,max_length=60)
    timezone: str = "Asia/Karachi"
    mode: Literal["Analyse","Draft","Approved actions"] = "Draft"
    provider: Provider = "OpenAI"
    model: str = Field(default="",pattern=r"^[A-Za-z0-9._:-]{0,120}$")
    instructions: str = Field(default="Use simple English. Cite approved scope and flag missing evidence.",max_length=4000)
    response_preference:Literal["Concise","Balanced","Detailed"]="Concise"
    temperature: float | None = Field(default=None,ge=0,le=1,allow_inf_nan=False)
    jira_default: str = Field(default="",pattern=r"^$|^[A-Z][A-Z0-9]{1,19}$")
    jira_status_map: dict[str,Literal["Remaining","In progress","Review","Done","Blocked"]] = Field(default_factory=dict,max_length=100)
    poll_minutes: Literal[0,5,15,30,60] = 0
    sync_jira: bool = True
    sync_slack: bool = True
    slack_notifications: bool = False
    max_tokens: int = Field(default=2400,ge=128,le=8000)
    monthly_budget: float = Field(default=0,ge=0,le=100000,allow_inf_nan=False)
    input_rate: float = Field(default=0,ge=0,le=1000,allow_inf_nan=False)
    output_rate: float = Field(default=0,ge=0,le=1000,allow_inf_nan=False)
    hourly_calls: int = Field(default=30,ge=1,le=120)
    context_passages: int = Field(default=8,ge=1,le=20)
    history_messages: int = Field(default=6,ge=0,le=12)
    fallback_provider: Literal["","OpenAI","Anthropic","Gemini"] = ""
    fallback_model: str = Field(default="",pattern=r"^[A-Za-z0-9._:-]{0,120}$")
    approved_only: bool = False
    allow_chat: bool = True
    allow_plan: bool = True
    allow_health: bool = True
    jira_site: str = Field(default="",pattern=r"^$|^https://[a-z0-9][a-z0-9-]*\.atlassian\.net$")
    jira_email: str = Field(default="",max_length=254)
    slack_team: str = Field(default="",pattern=r"^$|^T[A-Z0-9]+$")
    email_sender: str = Field(default="",max_length=254)
    daily_digest: bool = False
    digest_frequency: Literal["Daily","Weekly"] = "Daily"
    digest_weekday: int = Field(default=0,ge=0,le=6)
    digest_hour: int = Field(default=9,ge=0,le=23)

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except (ValueError,KeyError): raise ValueError("Select an IANA time zone.")
        return value


def permitted(policy, action):
    if not policy.enabled: raise ValueError("The agent is paused.")
    flag={"answer":policy.allow_chat,"plan":policy.allow_plan,"health":policy.allow_health}.get(action)
    if not flag: raise ValueError("This tool is disabled in Permissions.")
    if action=="plan" and policy.mode=="Analyse": raise ValueError("Enable Draft or Approved actions to generate plans.")


def health_snapshot(sources,plans,issues=(),today=None):
    from datetime import datetime,timezone
    day=(today or datetime.now(timezone.utc).date()).isoformat()
    flags=[]
    for row in issues:
        item=row["record"]
        group=item.get("status_group") or item.get("status","")
        if group.casefold() in {"done","resolved","closed"}:continue
        if "block" in group.casefold():flags.append(item["issue"]+" blocked")
        if item.get("due") and item["due"]<day:flags.append(item["issue"]+" past due "+item["due"])
    evidence=(" Imported snapshots: "+str(len(issues))+". Risks: "+(", ".join(flags) if flags else "none identified in the available statuses and dates")+".") if issues else " No Jira snapshots imported."

    approved=sum(x["state"]=="approved" for x in sources)
    pending=sum(x["state"]=="draft" for x in plans)
    return (f"Approved sources: {approved}. Draft sources awaiting review: {sum(x['state']=='draft' for x in sources)}. "
            f"Plans awaiting approval: {pending}. "
            +("Approve a scope before planning. " if not approved else "")
            +evidence+" QA verification requires acceptance evidence.")

def reserve_estimate(policy,prompt_bytes):
    if policy.monthly_budget and not (policy.input_rate>0 and policy.output_rate>0):
        raise ValueError("Set conservative input and output prices before enabling a budget.")
    return ((prompt_bytes+512)*policy.input_rate+policy.max_tokens*policy.output_rate)/1_000_000

def choose_tool(request):
    """Route explicit commands; open-ended questions use project evidence."""
    import re
    text=" ".join(request.casefold().split())
    if re.match(r"^(please )?(generate|draft|create|prepare|build) (a |the |our )?(project |implementation |milestone )?plan\b",text):
        return "plan"
    if re.match(r"^(please )?(run |check |review |show |summarise |summarize )?(the |our )?project health\b",text):
        return "health"
    return "answer"

ROLES=("Super Admin","CEO","Project Manager","Employee","Read-Only")
def may_edit(role):return role in ROLES[:3]
def may_admin(role):return role in ROLES[:2]
