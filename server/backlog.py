"""Validate the draft dependency graph before queuing any remote operations."""
from typing import Literal
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter

class Item(BaseModel):
    model_config=ConfigDict(extra="forbid",str_strip_whitespace=True)
    key:str=Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,30}$")
    kind:Literal["Epic","Story","Task","Subtask"]
    title:str=Field(min_length=1,max_length=180)
    deliverable:str=Field(min_length=1,max_length=2000)
    acceptance:str=Field(min_length=1,max_length=3000)
    milestone:str=Field(min_length=1,max_length=180)
    hours:float=Field(gt=0,le=10000,allow_inf_nan=False)
    due:date | None=None
    assignee:str=Field(default="",max_length=200)
    parent:str=""
    requires:list[str]=Field(default_factory=list,max_length=30)

def ordered_items(raw,team):
    items=TypeAdapter(list[Item]).validate_python(raw)
    index={i.key:i for i in items}
    if not 1<=len(items)<=30 or len(index)!=len(items):raise ValueError("Use 1–30 unique work items.")
    for item in items:
        if item.assignee and item.assignee not in team:raise ValueError("Unconfirmed assignee.")
        if item.parent and item.parent not in index:raise ValueError("Missing parent.")
        if item.kind=="Epic" and item.parent:raise ValueError("Epic cannot have a parent here.")
        if item.kind=="Subtask" and (not item.parent or index[item.parent].kind not in {"Task","Story"}):raise ValueError("Subtask requires a story or task parent.")
        if item.kind in {"Task","Story"} and item.parent and index[item.parent].kind!="Epic":raise ValueError("Standard issue parent must be an epic.")
        if set(item.requires)-index.keys() or len(set(item.requires))!=len(item.requires):raise ValueError("Invalid dependencies.")
    confirmed=set();ordered=[]
    while len(ordered)<len(items):
        ready=[i for i in items if i.key not in confirmed and set(i.requires+[i.parent])<=(confirmed|{""})]
        if not ready:raise ValueError("Cycle in publication graph.")
        ordered.extend(ready);confirmed.update(i.key for i in ready)
    return ordered
