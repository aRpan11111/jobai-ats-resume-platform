import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def get_llm():
    # Use LLaMA 3 for fast, accurate parsing and reasoning
    model_name = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    return ChatGroq(model_name=model_name, temperature=0)

async def parse_resume_to_json(raw_text: str) -> dict:
    llm = get_llm()
    parser = JsonOutputParser()
    
    prompt = PromptTemplate(
        template="""Convert this resume into structured JSON. Do not invent information. Extract ALL sections.
CRITICAL RULES:
1. DO NOT shorten or summarize ANY text. 
2. The 'summary' field must be extracted exactly word-for-word in its entirety.
3. Be sure to extract the candidate's name, email, and ALL links (GitHub, LinkedIn) into contact_info.
Schema:
{{
  "contact_info": {{"name": "string", "email": "string", "phone": "string", "linkedin": "string", "github": "string", "links": ["string"]}},
  "summary": "string",
  "skills": ["string"],
  "experience": [{{"company": "string", "title": "string", "dates": "string", "bullets": ["string"]}}],
  "projects": [{{"name": "string", "github_url": "string or empty", "bullets": ["string"]}}],
  "education": [{{"institution": "string", "degree": "string", "dates": "string"}}],
  "certifications": ["string"],
  "achievements": ["string"],
  "other_sections": {{"section_name": ["string"]}}
}}
Resume text:
{raw_text}
Return only valid JSON.""",
        input_variables=["raw_text"],
    )
    
    chain = prompt | llm | parser
    return await chain.ainvoke({"raw_text": raw_text})

async def full_tailor_resume(parsed_resume: dict, parsed_jd: dict, correction_instruction: str = "") -> dict:
    """Rewrite entire JSON resume for the JD, enforcing strict schema preservation."""
    llm = get_llm()
    parser = JsonOutputParser()
    
    prompt = PromptTemplate(
        template="""You are an expert resume writer. Tailor this resume to the job description.
{correction_instruction}
STRICT RULES:
1. You MUST return ALL sections present in the input resume JSON, using the EXACT SAME KEYS.
2. If a section has no relevant changes, pass it through unmodified. Do not omit it.
3. DO NOT shorten or rewrite the 'summary' field unless a change is required by keyword matching against the job description. If you change it, you must log it.
4. Ensure 'contact_info' and all 'links' (GitHub, LinkedIn) are preserved exactly as they are.

Output a JSON object with this exact schema:
{{
  "tailored_resume": <the full tailored resume JSON with all original keys>,
  "changelog": [
    "string describing a specific change (e.g., 'Rewrote bullet in X to highlight Y', 'Added keyword Z to summary')"
  ]
}}

Original Resume JSON:
{resume_json}

Job Description JSON:
{jd_json}
""",
        input_variables=["correction_instruction", "resume_json", "jd_json"],
    )
    
    import json
    chain = prompt | llm | parser
    res = await chain.ainvoke({
        "correction_instruction": correction_instruction,
        "resume_json": json.dumps(parsed_resume),
        "jd_json": json.dumps(parsed_jd)
    })
    return res

async def parse_jd_to_json(jd_text: str) -> dict:
    llm = get_llm()
    parser = JsonOutputParser()
    
    prompt = PromptTemplate(
        template="""Extract structured requirements from this job description.
Schema:
{{
  "role_title": "string",
  "seniority": "string",
  "must_have_skills": ["string"],
  "nice_to_have_skills": ["string"],
  "keywords": ["string"],
  "responsibilities": ["string"]
}}
JD text:
{jd_text}
Return only valid JSON.""",
        input_variables=["jd_text"],
    )
    
    chain = prompt | llm | parser
    return await chain.ainvoke({"jd_text": jd_text})

async def tailor_decision(missing_keyword: str, parsed_resume: dict, used_bullets: list = None) -> dict:
    llm = get_llm()
    parser = JsonOutputParser()
    
    avoid_instruction = ""
    if used_bullets:
        avoid_instruction = "\nDO NOT target or rewrite any of these bullets (they are already optimized for other keywords):\n" + "\n".join([f"- {b}" for b in used_bullets])
    
    prompt = PromptTemplate(
        template="""You are an expert resume writer. The candidate has a gap for keyword: "{missing_keyword}".
Read the candidate's resume JSON and pick exactly ONE bullet point from either 'experience' or 'projects' that can be legitimately rewritten to incorporate this keyword without lying. 
{avoid_instruction}

Schema:
{{
  "original_bullet": "string (must exactly match a bullet in the JSON)",
  "suggested_bullet": "string (the rewritten bullet including the keyword naturally)",
  "reasoning": "string"
}}
Resume JSON:
{resume_json}
Return only valid JSON.""",
        input_variables=["missing_keyword", "resume_json", "avoid_instruction"],
    )
    
    import json
    chain = prompt | llm | parser
    return await chain.ainvoke({
        "missing_keyword": missing_keyword, 
        "resume_json": json.dumps(parsed_resume),
        "avoid_instruction": avoid_instruction
    })

async def rewrite_single_bullet(bullet_text: str, section: str, item_name: str, jd_parsed: dict, existing_bullets: list[str] = None) -> dict:
    """Rewrite a single bullet point to better match the job description."""
    llm = get_llm()
    parser = JsonOutputParser()
    
    import json
    jd_keywords = jd_parsed.get("keywords", [])
    jd_skills = jd_parsed.get("must_have_skills", []) + jd_parsed.get("nice_to_have_skills", [])
    jd_role = jd_parsed.get("role_title", "")
    
    existing_list_str = "\n".join(f"- {b}" for b in existing_bullets) if existing_bullets else "None"
    
    prompt = PromptTemplate(
        template="""You are an expert resume writer optimizing a single bullet point for ATS matching.

CONTEXT:
- Section: {section}
- Position/Project: {item_name}
- Target Role: {jd_role}
- Target Keywords: {jd_keywords}
- Target Skills: {jd_skills}

EXISTING BULLETS ON RESUME (to avoid repetitive openings):
{existing_list_str}

CURRENT BULLET:
{bullet_text}

RULES:
1. Rewrite this ONE bullet to naturally incorporate relevant keywords from the job description.
2. Do NOT fabricate experience or add skills/tools the candidate did not mention.
3. Keep the same fundamental meaning and achievement — just optimize the wording.
4. Use strong action verbs and quantify impact where the original already does.
5. The rewritten bullet should be roughly the same length (±20 words).
6. CRITICAL REPETITION CONSTRAINT: Do NOT start this rewritten bullet with the same action verb or opening phrase (first 2-3 words) as any of the "EXISTING BULLETS ON RESUME" listed above. Ensure a unique action verb and varied sentence opening.

Return ONLY valid JSON:
{{
  "suggested_bullet": "the rewritten bullet text",
  "reasoning": "brief explanation of what was changed and why"
}}""",
        input_variables=["section", "item_name", "jd_role", "jd_keywords", "jd_skills", "existing_list_str", "bullet_text"],
    )
    
    chain = prompt | llm | parser
    result = await chain.ainvoke({
        "section": section,
        "item_name": item_name,
        "jd_role": jd_role,
        "jd_keywords": ", ".join(jd_keywords),
        "jd_skills": ", ".join(jd_skills),
        "existing_list_str": existing_list_str,
        "bullet_text": bullet_text
    })
    
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    elif isinstance(result, list):
        result = {"suggested_bullet": bullet_text, "reasoning": "No changes suggested."}
    
    return result

async def tailor_summary(parsed_resume: dict, jd_parsed: dict) -> dict:
    """Stateless: Rewrite the Summary to align with the JD, using only evidenced claims."""
    llm = get_llm()
    parser = JsonOutputParser()
    
    import json
    
    prompt = PromptTemplate(
        template="""You are an expert resume writer. Rewrite the candidate's Summary section to align with the job description.

JOB DESCRIPTION:
{jd_json}

CANDIDATE RESUME EVIDENCE:
{resume_json}

RULES:
1. Emphasize domains, achievements, and skills from the JD that the candidate has CLEAR EVIDENCE of having in their resume (look at their experience, projects, skills, education).
2. HARD CONSTRAINT: Never fabricate any experience, domains, credentials, or skills. Only reorder and reword claims that are already evidenced in the candidate's resume data.
3. Keep the Summary concise and professional (3-4 sentences maximum).

Return ONLY valid JSON:
{{
  "suggested_summary": "the rewritten summary text",
  "reasoning": "explanation of what was emphasized and why, referencing the resume evidence"
}}""",
        input_variables=["jd_json", "resume_json"],
    )
    
    chain = prompt | llm | parser
    result = await chain.ainvoke({
        "jd_json": json.dumps(jd_parsed),
        "resume_json": json.dumps(parsed_resume)
    })
    
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    return result

async def tailor_skills(parsed_resume: dict, jd_parsed: dict) -> dict:
    """Stateless: Tailor the Technical Skills list to reflect the JD, adding only evidenced skills."""
    llm = get_llm()
    parser = JsonOutputParser()
    
    import json
    
    prompt = PromptTemplate(
        template="""You are an expert technical resume writer. Optimize the candidate's Skills section to match the job description.

JOB DESCRIPTION:
{jd_json}

CANDIDATE RESUME EVIDENCE (full resume sections to look for tools/skills evidence):
{resume_json}

RULES:
1. Examine the JD required/preferred skills.
2. Cross-reference them against the candidate's full resume (look in experience, projects, education, and current skills).
3. If a JD required/preferred skill is mentioned or evidenced in the candidate's work history or projects, but is missing from their current Skills list, ADD IT to the tailored skills list.
4. HARD CONSTRAINT: Never add a skill that has ZERO supporting evidence anywhere in the candidate's resume.
5. Respect and maintain the existing category structure of the skills. The candidate's skills are grouped by category (e.g. "GenAI/LLM:", "Languages:", "DevOps/MLOps:"). Place any added skills in the correct category. Do not create new categories unless absolutely necessary.
6. If a JD-required skill is completely missing from the candidate's resume (zero evidence), do NOT add it. Instead, include it in the "missing_jd_skills" list so we can warn the user.

Return ONLY valid JSON:
{{
  "suggested_skills": [
    "Category Name: Skill1, Skill2, AddedSkill3",
    "Another Category: SkillA, SkillB"
  ],
  "missing_jd_skills": [
    "SkillName (reason: required in JD but no evidence found in your resume)"
  ],
  "reasoning": "explanation of what skills were added and where the evidence was found"
}}""",
        input_variables=["jd_json", "resume_json"],
    )
    
    chain = prompt | llm | parser
    result = await chain.ainvoke({
        "jd_json": json.dumps(jd_parsed),
        "resume_json": json.dumps(parsed_resume)
    })
    
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    return result
