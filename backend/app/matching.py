import chromadb
from rapidfuzz import fuzz
import os
import re

# ChromaDB persistence directory
chroma_client = chromadb.PersistentClient(path="./chroma_resumes")

def keyword_coverage(jd_keywords: list[str], resume_text: str) -> dict:
    results = {}
    for kw in jd_keywords:
        score = fuzz.partial_token_set_ratio(kw.lower(), resume_text.lower())
        results[kw] = score
    matched = [k for k, v in results.items() if v >= 80]
    coverage_pct = len(matched) / len(jd_keywords) * 100 if jd_keywords else 100
    
    return {
        "matched": matched,
        "missing": [k for k in jd_keywords if k not in matched],
        "coverage_pct": coverage_pct,
    }

def index_resume_bullets(resume_id: str, bullets: list[str]):
    collection = chroma_client.get_or_create_collection(f"resume_{resume_id}")
    if not bullets:
        return
    collection.add(
        documents=bullets,
        ids=[f"{resume_id}_{i}" for i in range(len(bullets))],
    )

def semantic_gap_check(resume_id: str, jd_requirements: list[str], threshold=0.55):
    try:
        collection = chroma_client.get_collection(f"resume_{resume_id}")
    except Exception:
        # Collection might not exist if no bullets
        return {"covered": [], "gaps": jd_requirements, "coverage_pct": 0.0}
        
    covered, gaps = [], []
    for req in jd_requirements:
        result = collection.query(query_texts=[req], n_results=1)
        if result["distances"] and len(result["distances"][0]) > 0:
            dist = result["distances"][0][0]
            # Chroma uses L2 distance by default (0 is identical, >1.5 is unrelated)
            if dist <= 1.4:
                covered.append(req)
            else:
                gaps.append(req)
        else:
            gaps.append(req)
            
    semantic_cov = (len(covered) / len(jd_requirements) * 100) if jd_requirements else 100
    return {"covered": covered, "gaps": gaps, "coverage_pct": semantic_cov}

def structural_checks(parsed_resume: dict, raw_text: str) -> dict:
    # A simple deterministic check
    has_contact = bool(re.search(r"[\w.+-]+@[\w-]+\.\w+", raw_text))
    has_sections = all(s in parsed_resume for s in ["experience", "skills", "education"])
    
    # We omit docx/page check since it's just raw text here for simplicity, but we could pass original doc.
    checks = {
        "has_contact_info": has_contact,
        "has_standard_sections": has_sections,
    }
    passed = sum(checks.values())
    return {"checks": checks, "structural_pct": passed / len(checks) * 100}

def reconstruct_resume_text(parsed: dict) -> str:
    """Reconstruct a unified plain text from structured parsed JSON to ensure edits are evaluated."""
    parts = []
    
    # Contact
    contact = parsed.get("contact_info", {})
    if isinstance(contact, dict):
        parts.append(contact.get("name", ""))
        parts.append(contact.get("email", ""))
        parts.append(contact.get("phone", ""))
        parts.append(contact.get("linkedin", ""))
        parts.append(contact.get("github", ""))
        
    # Summary
    if parsed.get("summary"):
        parts.append(parsed["summary"])
        
    # Skills
    skills = parsed.get("skills", [])
    if isinstance(skills, list):
        parts.append(" ".join(skills))
    elif isinstance(skills, dict):
        for k, v in skills.items():
            parts.append(k)
            parts.append(" ".join(v) if isinstance(v, list) else str(v))
            
    # Experience
    for exp in parsed.get("experience", []):
        parts.append(exp.get("company", ""))
        parts.append(exp.get("title", ""))
        parts.extend(exp.get("bullets", []))
        
    # Projects
    for proj in parsed.get("projects", []):
        parts.append(proj.get("name", ""))
        parts.extend(proj.get("bullets", []))
        
    # Education
    for edu in parsed.get("education", []):
        parts.append(edu.get("institution", ""))
        parts.append(edu.get("degree", ""))
        
    # Certs & Achievements
    parts.extend(parsed.get("certifications", []))
    parts.extend(parsed.get("achievements", []))
    
    return "\n".join(str(p) for p in parts if p)

def calculate_ats_score(db_resume, db_app) -> dict:
    jd_parsed = db_app.jd_parsed or {}
    jd_keywords = jd_parsed.get("keywords", [])
    # Only use must_have_skills for semantic gap check to reduce false positive gaps from long responsibilities
    jd_reqs = jd_parsed.get("must_have_skills", [])
    
    import json
    parsed = db_resume.parsed_json
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except:
            parsed = {}
    elif not isinstance(parsed, dict):
        parsed = {}
        
    # Reconstruct live resume text
    live_resume_text = reconstruct_resume_text(parsed)
    
    kw_result = keyword_coverage(jd_keywords, live_resume_text)
    
    # Index resume bullets
    bullets = []
    for exp in parsed.get("experience", []):
        bullets.extend(exp.get("bullets", []))
    for proj in parsed.get("projects", []):
        bullets.extend(proj.get("bullets", []))
    
    index_resume_bullets(str(db_resume.id), bullets)
    
    sem_result = semantic_gap_check(str(db_resume.id), jd_reqs)
    struct_result = structural_checks(parsed, live_resume_text)
    
    base_ats_score = (0.5 * kw_result["coverage_pct"]) + \
                     (0.3 * sem_result["coverage_pct"]) + \
                     (0.2 * struct_result["structural_pct"])
                     
    # --- Repetitive opening check & Keyword stuffing check ---
    penalties = 0.0
    score_logs = []
    
    # 1. Bullet opening repetitions (check first 2 words)
    openings = {}
    for bullet in bullets:
        words = [w.lower().strip() for w in re.split(r'\s+', bullet) if w.strip()]
        if len(words) >= 2:
            opening = " ".join(words[:2])
            openings[opening] = openings.get(opening, 0) + 1
            
    rep_groups = {op: count for op, count in openings.items() if count > 1}
    for op, count in rep_groups.items():
        penalty = 2.0
        penalties += penalty
        score_logs.append(f"Repetitive bullet opening: '{op}' appears {count} times. Penalty applied: -{penalty}%.")
        
    # 2. Keyword stuffing (mentions of a JD keyword > 3 times)
    for kw in jd_keywords:
        pattern = re.compile(rf'\b{re.escape(kw.lower())}\b')
        count = len(pattern.findall(live_resume_text.lower()))
        if count > 3:
            penalty = 2.0
            penalties += penalty
            score_logs.append(f"Keyword stuffing: '{kw}' is mentioned {count} times. Penalty applied: -{penalty}%.")
            
    final_ats_score = max(0.0, min(100.0, base_ats_score - penalties))
    
    if penalties > 0:
        score_logs.append(f"Total penalties applied: -{penalties}%. Base score: {base_ats_score:.1f}% -> Final score: {final_ats_score:.1f}%.")
    else:
        score_logs.append("No repetitiveness or keyword density penalties applied.")
        
    # Print to console for debuggability
    print(f"--- ATS SCORE RECALCULATION (App ID: {db_app.id}) ---")
    for log in score_logs:
        print(f"  [Scorer] {log}")
    print("-----------------------------------------------------")
    
    return {
        "keyword_coverage_pct": kw_result["coverage_pct"],
        "semantic_coverage_pct": sem_result["coverage_pct"],
        "structural_pct": struct_result["structural_pct"],
        "ats_score": final_ats_score,
        "gaps": kw_result["missing"] + sem_result["gaps"],
        "covered": kw_result["matched"] + sem_result["covered"],
        "score_logs": score_logs
    }
