from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, Enum, TIMESTAMP, Date, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from database import Base

class ApplicationStatus(enum.Enum):
    saved = "saved"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"

class SuggestionType(enum.Enum):
    rewrite = "rewrite"
    add = "add"
    clarify = "clarify"

class SuggestionStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"

class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, default=1) # Defaulting for local usage
    label = Column(String(100))
    raw_text = Column(Text)
    parsed_json = Column(JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    applications = relationship("JobApplication", back_populates="resume_version")

class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, default=1)
    company = Column(String(150))
    role_title = Column(String(150))
    jd_text = Column(Text)
    jd_parsed = Column(JSON)
    resume_version_id = Column(Integer, ForeignKey("resume_versions.id"))
    ats_score = Column(Float)
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.saved)
    applied_at = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    resume_version = relationship("ResumeVersion", back_populates="applications")
    tailoring_sessions = relationship("TailoringSession", back_populates="application")

class TailoringSession(Base):
    __tablename__ = "tailoring_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("job_applications.id"))
    suggestion_type = Column(Enum(SuggestionType))
    original_bullet = Column(Text)
    suggested_bullet = Column(Text)
    status = Column(Enum(SuggestionStatus), default=SuggestionStatus.pending)
    created_at = Column(TIMESTAMP, server_default=func.now())

    application = relationship("JobApplication", back_populates="tailoring_sessions")
