"""Project-specific improvement and report scheduling rules."""
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field, field_validator

def suggested_instruction(category):
    category=category.casefold()
    if "estim" in category or "schedule" in category:
        return "State the capacity, dependencies and review time behind each estimate. Flag missing inputs."
    if "scope" in category or "requirement" in category:
        return "Compare each proposed deliverable with the current approved scope. List uncovered requirements and cite their source."
    if "status" in category or "report" in category:
        return "Cite dated activity for status claims. Mark work without recent evidence as unverified."
    return "Cross-check the answer against approved project sources and call out unsupported conclusions before finalising."

class ScheduleRule(BaseModel):
    frequency:Literal["Off","Daily","Weekly"]="Off"
    zone:str="Asia/Karachi"
    hour:int=Field(default=9,ge=0,le=23)
    weekday:int=Field(default=0,ge=0,le=6)
    audience:Literal["CEO","Client"]="CEO"
    heading:str=Field(default="Project progress report",min_length=1,max_length=180)
    recipient:str=Field(default="",pattern=r"^$|^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$",max_length=254)
    @field_validator("zone")
    @classmethod
    def valid_zone(cls,value):
        try:ZoneInfo(value)
        except (ValueError,ZoneInfoNotFoundError):raise ValueError("Use a valid time zone such as Asia/Karachi.")
        return value

def reporting_window(rule,instant):
    now=instant.astimezone(ZoneInfo(rule.zone))
    if rule.frequency=="Off" or now.hour<rule.hour or (rule.frequency=="Weekly" and now.weekday()!=rule.weekday):return None
    end=now.date()-timedelta(days=1)
    return now.date(),end-timedelta(days=6 if rule.frequency=="Weekly" else 0),end
