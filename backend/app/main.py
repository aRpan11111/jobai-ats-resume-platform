from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from typing import List
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from . import models, schemas, database, parsing, ai, matching, export

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="JobAI Resume Tailoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from sqlalchemy import event, inspect

@event.listens_for(Session, 'before_flush')
def receive_before_flush(session, flush_context, instances):
    for obj in session.dirty:
        if isinstance(obj, models.ResumeVersion):
            state = inspect(obj)
            history = state.get_history('parsed_json', passive=True)
            if history.has_changes():
                for app in obj.applications:
                    try:
                        score_data = matching.calculate_ats_score(obj, app)
                        app.ats_score = score_data["ats_score"]
                    except Exception as e:
                        print(f"Auto-update ATS score failed for app {app.id}: {e}")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "JobAI API is running"}

@app.post("/resumes/upload", response_model=schemas.ResumeVersionResponse)
async def upload_resume(label: str, file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    """Parse and store a resume version"""
    # 1. Read file bytes
    file_bytes = await file.read()
    
    # 2. Extract raw text
    try:
        raw_text = parsing.extract_text(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # 3. Use LLM to structure text
    try:
        parsed_json = await ai.parse_resume_to_json(raw_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to structure resume: {str(e)}")

    # 4. Save to DB
    db_resume = models.ResumeVersion(
        label=label,
        raw_text=raw_text,
        parsed_json=parsed_json
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    return db_resume

@app.get("/resumes", response_model=List[schemas.ResumeVersionResponse])
def list_resumes(db: Session = Depends(database.get_db)):
    return db.query(models.ResumeVersion).all()

@app.post("/applications", response_model=schemas.JobApplicationResponse)
async def create_application(app_in: schemas.JobApplicationCreate, resume_id: int, db: Session = Depends(database.get_db)):
    # Extract JD requirements using LLM
    try:
        jd_parsed = await ai.parse_jd_to_json(app_in.jd_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse JD: {str(e)}")

    db_app = models.JobApplication(
        user_id=app_in.user_id,
        company=app_in.company,
        role_title=app_in.role_title,
        jd_text=app_in.jd_text,
        jd_parsed=jd_parsed,
        resume_version_id=resume_id
    )
    db.add(db_app)
    db.commit()
    db.refresh(db_app)
    return db_app

@app.post("/applications/{id}/match", response_model=schemas.MatchScoreResponse)
async def run_match(id: int, db: Session = Depends(database.get_db)):
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    # Run matching
    score_data = matching.calculate_ats_score(db_resume, db_app)
    
    # Update score in DB
    db_app.ats_score = score_data["ats_score"]
    db.commit()
    
    return score_data

@app.post("/applications/{id}/tailor")
async def tailor_resume(id: int, db: Session = Depends(database.get_db)):
    """Run intent routing for gaps and generate suggestions"""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    # Re-calculate gaps
    score_data = matching.calculate_ats_score(db_resume, db_app)
    gaps = score_data["gaps"]
    
    # Take top 3 gaps
    gaps = gaps[:3] if gaps else []
    
    used_bullets = set()
    suggestions = []
    
    for gap in gaps:
        decision = await ai.tailor_decision(gap, db_resume.parsed_json, list(used_bullets))
        if isinstance(decision, list) and len(decision) > 0:
            decision = decision[0]
        elif isinstance(decision, list):
            decision = {}
        original_bullet = decision.get("original_bullet")
        
        # Don't target the same bullet point twice in one run
        if original_bullet and original_bullet != "None" and original_bullet in used_bullets:
            continue
            
        if original_bullet and original_bullet != "None":
            used_bullets.add(original_bullet)
            
        db_suggestion = models.TailoringSession(
            application_id=id,
            suggestion_type=decision.get("action", "rewrite"),
            suggested_bullet=decision.get("suggested_bullet") or decision.get("new_bullet", ""),
            original_bullet=original_bullet # if any
        )
        db.add(db_suggestion)
        suggestions.append(db_suggestion)
    
    db.commit()
    return {"suggestions": [s.id for s in suggestions]}

@app.get("/applications", response_model=List[schemas.JobApplicationResponse])
def list_applications(db: Session = Depends(database.get_db)):
    return db.query(models.JobApplication).all()

from fastapi.responses import Response

@app.get("/applications/{id}/resume")
def get_resume(id: int, db: Session = Depends(database.get_db)):
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    return db_resume.parsed_json or {}

@app.get("/applications/{id}/export")
def export_tailored_resume(id: int, db: Session = Depends(database.get_db)):
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    try:
        from latex_template import json_to_latex
        latex_code = json_to_latex(db_resume.parsed_json)
        
        from pdf_compiler import compile_latex_to_pdf
        pdf_bytes = compile_latex_to_pdf(latex_code)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=tailored_resume_{id}.pdf"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"PDF export compilation failed: {str(e)}. Check server logs for details."
        )

from fastapi.responses import Response

@app.get("/applications/{id}/export-latex")
def export_tailored_resume_latex(id: int, db: Session = Depends(database.get_db)):
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume.raw_text or "\\documentclass" not in db_resume.raw_text:
        raise HTTPException(status_code=400, detail="Original resume is not in LaTeX format.")
        
    return Response(
        content=db_resume.raw_text,
        media_type="application/x-tex",
        headers={"Content-Disposition": f"attachment; filename=tailored_resume_{id}.tex"}
    )

import urllib.request
import urllib.parse
from .latex_template import json_to_latex

@app.post("/applications/{id}/full-tailor-and-export")
async def full_tailor_and_export(id: int, db: Session = Depends(database.get_db)):
    """Runs a full JSON rewrite, validates keys, saves it, and exports PDF."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    original_json = dict(db_resume.parsed_json) if isinstance(db_resume.parsed_json, dict) else json.loads(db_resume.parsed_json)
    jd_json = db_app.jd_parsed or {}
    
    correction = ""
    for attempt in range(2):
        try:
            res = await ai.full_tailor_resume(original_json, jd_json, correction)
            tailored = res.get("tailored_resume", {})
            changelog = res.get("changelog", [])
            
            # Validation: diff keys
            missing_keys = set(original_json.keys()) - set(tailored.keys())
            
            # Check links specifically
            orig_contact = original_json.get("contact_info", {})
            new_contact = tailored.get("contact_info", {})
            dropped_links = []
            for field in ["linkedin", "github"]:
                if orig_contact.get(field) and not new_contact.get(field):
                    dropped_links.append(field)
            
            if missing_keys or dropped_links:
                err = []
                if missing_keys: err.append(f"missing sections: {missing_keys}")
                if dropped_links: err.append(f"dropped links: {dropped_links}")
                if attempt == 0:
                    correction = f"CORRECTION: You dropped information! Regenerate, restoring {', '.join(err)} exactly as they were."
                    continue
                else:
                    # After 1 retry, just force restore the missing sections
                    for k in missing_keys:
                        tailored[k] = original_json[k]
                    for field in dropped_links:
                        if "contact_info" not in tailored: tailored["contact_info"] = {}
                        tailored["contact_info"][field] = orig_contact[field]
            
            break # Success
        except Exception as e:
            if attempt == 1:
                raise HTTPException(status_code=500, detail=f"LLM failure: {e}")
            correction = f"CORRECTION: JSON error or formatting error: {e}"
            
    # Save the new tailored JSON
    db_resume.parsed_json = tailored
    db.commit()
    
    # Generate PDF
    latex_code = json_to_latex(tailored)
    try:
        from pdf_compiler import compile_latex_to_pdf
        pdf_bytes = compile_latex_to_pdf(latex_code)
        
        # We put the changelog in a header
        import base64
        import json as json_lib
        b64_changelog = base64.b64encode(json_lib.dumps(changelog).encode('utf-8')).decode('utf-8')
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=tailored_resume_{id}.pdf",
                "X-Changelog": b64_changelog
            }
        )
    except Exception as e:
        print(f"PDF compilation failed: {e}. Falling back to docx source.")
        import export
        doc_io = export.export_docx(tailored)
        return StreamingResponse(
            doc_io,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=tailored_resume_{id}.docx"}
        )

@app.get("/applications/{id}/export-pdf")
def export_tailored_resume_pdf(id: int, db: Session = Depends(database.get_db)):
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    # Generate dynamic LaTeX from JSON
    try:
        latex_code = json_to_latex(db_resume.parsed_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate LaTeX from JSON: {e}")
        
    try:
        from pdf_compiler import compile_latex_to_pdf
        pdf_bytes = compile_latex_to_pdf(latex_code)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=tailored_resume_{id}.pdf"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"PDF compilation failed: {str(e)}. Check server logs for details."
        )

@app.get("/applications/{id}/suggestions", response_model=List[schemas.SuggestionResponse])
def get_suggestions(id: int, db: Session = Depends(database.get_db)):
    return db.query(models.TailoringSession).filter(models.TailoringSession.application_id == id).all()

@app.post("/applications/{id}/suggestions/{sid}/accept")
async def accept_suggestion(id: int, sid: int, db: Session = Depends(database.get_db)):
    db_sug = db.query(models.TailoringSession).filter(models.TailoringSession.id == sid, models.TailoringSession.application_id == id).first()
    if not db_sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")
        
    db_sug.status = models.SuggestionStatus.accepted
    
    # Update parsed JSON
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    parsed = dict(db_resume.parsed_json)
    if db_sug.suggestion_type == models.SuggestionType.rewrite:
        for exp in parsed.get("experience", []):
            if db_sug.original_bullet in exp.get("bullets", []):
                idx = exp["bullets"].index(db_sug.original_bullet)
                exp["bullets"][idx] = db_sug.suggested_bullet
                break
    
    db_resume.parsed_json = parsed
    
    # Removed raw_text update since LaTeX is now dynamically generated from parsed_json
            
    score_data = matching.calculate_ats_score(db_resume, db_app)
    db_app.ats_score = score_data["ats_score"]
    
    db.commit()
    return {"status": "accepted", "new_score": db_app.ats_score}

@app.post("/applications/{id}/suggestions/{sid}/reject")
def reject_suggestion(id: int, sid: int, db: Session = Depends(database.get_db)):
    db_sug = db.query(models.TailoringSession).filter(models.TailoringSession.id == sid, models.TailoringSession.application_id == id).first()
    if not db_sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")
        
    db_sug.status = models.SuggestionStatus.rejected
    db.commit()
    return {"status": "rejected"}

class AnswerPayload(schemas.BaseModel):
    answer: str

@app.post("/applications/{id}/suggestions/{sid}/answer")
async def answer_suggestion(id: int, sid: int, payload: AnswerPayload, db: Session = Depends(database.get_db)):
    db_sug = db.query(models.TailoringSession).filter(models.TailoringSession.id == sid, models.TailoringSession.application_id == id).first()
    if not db_sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")
        
    new_bullet = await ai.generate_bullet_from_answer(db_sug.suggested_bullet, payload.answer)
    
    db_sug.status = models.SuggestionStatus.accepted
    db_sug.suggested_bullet = new_bullet
    
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    
    parsed = dict(db_resume.parsed_json)
    if parsed.get("experience"):
        parsed["experience"][0]["bullets"].insert(0, new_bullet)
        
    db_resume.parsed_json = parsed
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_resume, "parsed_json")
            
    score_data = matching.calculate_ats_score(db_resume, db_app)
    db_app.ats_score = score_data["ats_score"]
    
    db.commit()
    return {"status": "answered", "new_bullet": new_bullet, "new_score": db_app.ats_score}

# --- Click-to-edit bullet rewrite endpoints ---

@app.post("/applications/{id}/bullet-rewrite", response_model=schemas.BulletRewriteResponse)
async def bullet_rewrite(id: int, req: schemas.BulletRewriteRequest, db: Session = Depends(database.get_db)):
    """Stateless: generate one AI rewrite suggestion for a single bullet, avoiding repetitions."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    jd_parsed = db_app.jd_parsed or {}
    
    # Gather other bullets in resume to prevent action verb repetition
    existing_bullets = []
    parsed_json = db_resume.parsed_json or {}
    for exp in parsed_json.get("experience", []):
        for b in exp.get("bullets", []):
            if b != req.bullet_text:
                existing_bullets.append(b)
    for proj in parsed_json.get("projects", []):
        for b in proj.get("bullets", []):
            if b != req.bullet_text:
                existing_bullets.append(b)
                
    result = await ai.rewrite_single_bullet(
        bullet_text=req.bullet_text,
        section=req.section,
        item_name=req.item_name,
        jd_parsed=jd_parsed,
        existing_bullets=existing_bullets
    )
    
    return schemas.BulletRewriteResponse(
        bullet_id=req.bullet_id,
        suggested_bullet=result.get("suggested_bullet", req.bullet_text),
        reasoning=result.get("reasoning", "")
    )

@app.post("/applications/{id}/bullet-accept")
def bullet_accept(id: int, req: schemas.BulletAcceptRequest, db: Session = Depends(database.get_db)):
    """Persist an accepted bullet edit into the resume's parsed_json."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    parsed = dict(db_resume.parsed_json) if isinstance(db_resume.parsed_json, dict) else {}
    
    parts = req.bullet_id.split("-")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail=f"Invalid bullet_id format: {req.bullet_id}")
    
    section = parts[0]
    try:
        item_idx = int(parts[1])
        bullet_idx = int(parts[2])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid bullet_id indices: {req.bullet_id}")
    
    items = parsed.get(section, [])
    if item_idx >= len(items):
        raise HTTPException(status_code=404, detail=f"Item index {item_idx} out of range for section '{section}'")
    
    bullets = items[item_idx].get("bullets", [])
    if bullet_idx >= len(bullets):
        raise HTTPException(status_code=404, detail=f"Bullet index {bullet_idx} out of range")
    
    bullets[bullet_idx] = req.new_text
    
    db_resume.parsed_json = parsed
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_resume, "parsed_json")
    
    db.commit()
    db.refresh(db_app)
    
    # Recalculate directly to return the score logs as well
    score_data = matching.calculate_ats_score(db_resume, db_app)
    
    return {
        "status": "accepted",
        "bullet_id": req.bullet_id,
        "new_score": db_app.ats_score,
        "score_data": score_data
    }

# --- Summary & Skills Tailoring endpoints ---

@app.post("/applications/{id}/tailor-summary", response_model=schemas.SummaryRewriteResponse)
async def endpoint_tailor_summary(id: int, db: Session = Depends(database.get_db)):
    """Stateless: Generate a tailored Summary suggestion."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    result = await ai.tailor_summary(db_resume.parsed_json, db_app.jd_parsed or {})
    return schemas.SummaryRewriteResponse(
        suggested_summary=result.get("suggested_summary", ""),
        reasoning=result.get("reasoning", "")
    )

@app.post("/applications/{id}/accept-summary")
def accept_summary(id: int, req: schemas.SummaryAcceptRequest, db: Session = Depends(database.get_db)):
    """Persist the accepted Summary and return the recalculated score."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    parsed = dict(db_resume.parsed_json) if isinstance(db_resume.parsed_json, dict) else {}
    parsed["summary"] = req.new_summary
    db_resume.parsed_json = parsed
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_resume, "parsed_json")
    
    db.commit()
    db.refresh(db_app)
    
    score_data = matching.calculate_ats_score(db_resume, db_app)
    return {
        "status": "accepted",
        "new_score": db_app.ats_score,
        "score_data": score_data
    }

@app.post("/applications/{id}/tailor-skills", response_model=schemas.SkillsRewriteResponse)
async def endpoint_tailor_skills(id: int, db: Session = Depends(database.get_db)):
    """Stateless: Generate tailored Skills suggestions."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    result = await ai.tailor_skills(db_resume.parsed_json, db_app.jd_parsed or {})
    return schemas.SkillsRewriteResponse(
        suggested_skills=result.get("suggested_skills", []),
        missing_jd_skills=result.get("missing_jd_skills", []),
        reasoning=result.get("reasoning", "")
    )

@app.post("/applications/{id}/accept-skills")
def accept_skills(id: int, req: schemas.SkillsAcceptRequest, db: Session = Depends(database.get_db)):
    """Persist the accepted tailored Skills list and return the recalculated score."""
    db_app = db.query(models.JobApplication).filter(models.JobApplication.id == id).first()
    if not db_app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db_resume = db.query(models.ResumeVersion).filter(models.ResumeVersion.id == db_app.resume_version_id).first()
    if not db_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
        
    parsed = dict(db_resume.parsed_json) if isinstance(db_resume.parsed_json, dict) else {}
    parsed["skills"] = req.new_skills
    db_resume.parsed_json = parsed
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(db_resume, "parsed_json")
    
    db.commit()
    db.refresh(db_app)
    
    score_data = matching.calculate_ats_score(db_resume, db_app)
    return {
        "status": "accepted",
        "new_score": db_app.ats_score,
        "score_data": score_data
    }
