import pytest
import json
import base64
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from fastapi.testclient import TestClient
import main
from database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, JobApplication, ResumeVersion

app = main.app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test data
    resume_json = {
        "contact_info": {"name": "Test User", "linkedin": "in/test", "github": "github.com/test"},
        "summary": "This is a summary of length more than fifty characters to test truncation behavior properly.",
        "skills": ["Python", "Testing"],
        "certifications": ["AWS Certified"],
        "achievements": ["Employee of the month"]
    }
    
    resume = ResumeVersion(raw_text="Test", parsed_json=resume_json)
    db.add(resume)
    db.commit()
    
    app_job = JobApplication(resume_version_id=resume.id, jd_text="Need Python", jd_parsed={"keywords": ["Python"]})
    db.add(app_job)
    db.commit()
    
    yield {"app_id": app_job.id, "resume_json": resume_json}
    
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_full_tailor_and_export(setup_db, monkeypatch):
    app_id = setup_db["app_id"]
    original_json = setup_db["resume_json"]
    
    # Mock the LLM to return valid output without calling API
    async def mock_full_tailor(parsed_resume, parsed_jd, correction_instruction=""):
        # Simulate dropping 'certifications' if no correction instruction is given
        if not correction_instruction:
            ret = parsed_resume.copy()
            ret.pop("certifications", None)
            return {"tailored_resume": ret, "changelog": ["Mock changed"]}
        else:
            # On retry (correction instruction given), return correctly preserved keys
            return {"tailored_resume": parsed_resume, "changelog": ["Mock changed"]}
            
    import main
    monkeypatch.setattr(main.ai, "full_tailor_resume", mock_full_tailor)
    
    # Run endpoint
    response = client.post(f"/applications/{app_id}/full-tailor-and-export")
    
    # Test valid response
    assert response.status_code == 200
    
    # Test PDF generation (magic bytes)
    # The first 4 bytes of a PDF are '%PDF'
    assert response.content.startswith(b"%PDF")
    
    # Test changelog header
    changelog_b64 = response.headers.get("X-Changelog")
    assert changelog_b64 is not None
    changelog = json.loads(base64.b64decode(changelog_b64).decode('utf-8'))
    assert "Mock changed" in changelog
    
    # Test database update
    db = TestingSessionLocal()
    updated_resume = db.query(ResumeVersion).first()
    # Ensure certifications were restored by the retry mechanism or the fallback logic
    assert "certifications" in updated_resume.parsed_json
    assert "achievements" in updated_resume.parsed_json
    
    # Ensure summary is not inappropriately truncated
    assert len(updated_resume.parsed_json["summary"]) >= len(original_json["summary"]) * 0.5
    
    db.close()

def test_summary_and_skills_tailoring(setup_db, monkeypatch):
    app_id = setup_db["app_id"]
    
    # Mock LLM summary & skills tailoring
    async def mock_tailor_summary(parsed_resume, jd_parsed):
        return {
            "suggested_summary": "Tailored Summary with Python experience.",
            "reasoning": "Emphasized Python."
        }
        
    async def mock_tailor_skills(parsed_resume, jd_parsed):
        return {
            "suggested_skills": ["Languages: Python, JavaScript", "Testing: pytest"],
            "missing_jd_skills": ["SQL (no evidence found)"],
            "reasoning": "Added Python, kept others."
        }
        
    import main
    monkeypatch.setattr(main.ai, "tailor_summary", mock_tailor_summary)
    monkeypatch.setattr(main.ai, "tailor_skills", mock_tailor_skills)
    
    # 1. Summary suggestion
    res = client.post(f"/applications/{app_id}/tailor-summary")
    assert res.status_code == 200
    assert res.json()["suggested_summary"] == "Tailored Summary with Python experience."
    
    # 2. Accept summary
    res_accept = client.post(f"/applications/{app_id}/accept-summary", json={"new_summary": "Tailored Summary with Python experience."})
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "accepted"
    
    # 3. Skills suggestion
    res_skills = client.post(f"/applications/{app_id}/tailor-skills")
    assert res_skills.status_code == 200
    assert "missing_jd_skills" in res_skills.json()
    
    # 4. Accept skills
    res_skills_accept = client.post(f"/applications/{app_id}/accept-skills", json={"new_skills": ["Languages: Python, JavaScript"]})
    assert res_skills_accept.status_code == 200
    assert res_skills_accept.json()["status"] == "accepted"

