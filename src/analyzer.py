import json
import httpx
import config
from db import get_pending_analysis, save_analysis, delete_job

SYSTEM_PROMPT = f"""You are a job analyzer. Given a job title, company, and description, return ONLY a JSON object with these fields:
- german_required: true if German language is explicitly required (B2/C1/C2 or "Deutsch erforderlich" etc), false if not required or English is acceptable, null if completely unclear
- relevance_score: integer 1-10 scoring fit for this candidate profile: {config.PROFILE_SUMMARY}
- matched_skills: array of specific skills from the profile that match this job (max 5)
- reasoning: one sentence explaining the score and german assessment

Rules:
- A JD written in German does NOT mean German is required — many international companies write German JDs but work in English
- Look for explicit language requirements like "Deutschkenntnisse erforderlich", "C1 Deutsch", "fließend Deutsch"
- If the JD mentions "working language English" or similar, german_required is false
- For "Software Engineer" roles: only score >= 4 if Python or AI/ML is mentioned
- Return ONLY the JSON, no markdown, no explanation"""

def analyze_job(job: dict) -> dict | None:
    text = f"Title: {job['title']}\nCompany: {job['company']}\nDescription: {job['description'][:3000]}"
    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.OPENROUTER_MODEL,
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
            timeout=30,
        )
        content = r.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception as e:
        print(f"  analyzer error [{job['slug'][:8]}]: {e}")
        return None

def run_analysis(limit=50):
    jobs = get_pending_analysis(limit)
    if not jobs:
        print("No pending jobs to analyze")
        return
    print(f"Analyzing {len(jobs)} jobs...")
    kept = discarded = 0
    for job in jobs:
        result = analyze_job(job)
        if not result:
            continue
        german_required = result.get("german_required")
        score = result.get("relevance_score", 0)
        if german_required is True or score < config.MIN_RELEVANCE_SCORE:
            delete_job(job["slug"])
            discarded += 1
            continue
        save_analysis(
            slug=job["slug"],
            german_required=1 if german_required is True else (0 if german_required is False else None),
            relevance_score=score,
            matched_skills=", ".join(result.get("matched_skills", [])),
            reasoning=result.get("reasoning", ""),
        )
        kept += 1
    print(f"Analysis done: {kept} kept, {discarded} discarded")

if __name__ == "__main__":
    run_analysis()
