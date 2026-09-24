from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum

# Standardizing schemas as defined in the plan

class ApplicationStatusSchema(str, Enum):
    saved = "saved"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"

class SuggestionTypeSchema(str, Enum):
    rewrite = "rewrite"
    add = "add"
    clarify = "clarify"

class SuggestionStatusSchema(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"

class ResumeVersionCreate(BaseModel):
    user_id: int = 1
    label: str

class ResumeVersionResponse(BaseModel):
    id: int
    user_id: int
    label: str
    parsed_json: Any
    created_at: datetime
    class Config:
        from_attributes = True

class JobApplicationCreate(BaseModel):
    user_id: int = 1
    company: str
    role_title: str
    jd_text: str

class JobApplicationResponse(BaseModel):
    id: int
    company: str
    role_title: str
    ats_score: Optional[float]
    status: ApplicationStatusSchema
    created_at: datetime
    class Config:
        from_attributes = True

class MatchScoreResponse(BaseModel):
    keyword_coverage_pct: float
    semantic_coverage_pct: float
    structural_pct: float
    ats_score: float
    gaps: List[str]
    covered: List[str]
    score_logs: List[str] = []

class SuggestionResponse(BaseModel):
    id: int
    suggestion_type: SuggestionTypeSchema
    original_bullet: Optional[str]
    suggested_bullet: str
    status: SuggestionStatusSchema
    class Config:
        from_attributes = True

# --- Click-to-edit bullet rewrite schemas ---

class BulletRewriteRequest(BaseModel):
    bullet_id: str       # e.g. "experience-0-2"
    bullet_text: str     # current bullet text
    section: str         # "experience" or "projects"
    item_name: str       # job title or project name for context

class BulletRewriteResponse(BaseModel):
    bullet_id: str
    suggested_bullet: str
    reasoning: str

class BulletAcceptRequest(BaseModel):
    bullet_id: str       # e.g. "experience-0-2"
    new_text: str        # the accepted bullet text

# --- Click-to-edit summary & skills schemas ---

class SummaryRewriteResponse(BaseModel):
    suggested_summary: str
    reasoning: str

class SummaryAcceptRequest(BaseModel):
    new_summary: str

class SkillsRewriteResponse(BaseModel):
    suggested_skills: List[str]
    missing_jd_skills: List[str]
    reasoning: str

class SkillsAcceptRequest(BaseModel):
    new_skills: List[str]
