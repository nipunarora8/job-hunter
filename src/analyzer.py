import json
import re
import httpx
import config
from db import get_pending_analysis, save_analysis, delete_job

SYSTEM_PROMPT = f"""You are a job relevance analyzer. Analyze the job and respond with ONLY a JSON object — no markdown, no explanation, no extra text.

Candidate profile:
{config.PROFILE_SUMMARY}

Respond with exactly this JSON structure:
{{"german_required": true/false/null, "relevance_score": <1-10>, "matched_skills": ["skill1", "skill2"], "reasoning": "one sentence"}}

Rules for german_required:
- true: job explicitly requires German language skills. Triggers:
  * Any mention of "B1/B2/C1/C2 Deutsch" or "Deutschkenntnisse"
  * "fließend Deutsch", "Deutsch in Wort und Schrift", "Deutsch...Niveau"
  * "Deutsch und Englisch" as a requirement (bilingual requirement = German required)
  * Working with German government / public sector clients where German is implied
- false: English is stated as working language, or no German requirement mentioned
- null: unclear, description is missing or too short to determine
- IMPORTANT: A job description written IN German does NOT by itself mean German is required
- IMPORTANT: If the JD says "Deutsch und Englisch beherrschst du fließend" → german_required = true

Rules for relevance_score:
- 8-10: strong match, most required skills align with candidate profile
- 5-7: partial match, some relevant skills
- 3-4: weak match, tangentially related
- 1-2: not relevant
- Software Engineer roles without Python or AI/ML: score <= 3

Output ONLY the JSON object. Start your response with {{"""

def _extract_json(text: str) -> dict | None:
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return None

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
        raw = r.json()["choices"][0]["message"]["content"]
        result = _extract_json(raw)
        if result is None:
            print(f"  analyzer parse error [{job['slug'][:8]}]: could not extract JSON from: {raw[:100]}")
        return result
    except Exception as e:
        print(f"  analyzer error [{job['slug'][:8]}]: {e}")
        return None

def run_analysis(limit=50):
    jobs = get_pending_analysis(limit)
    if not jobs:
        print("No pending jobs to analyze")
        return
    print(f"Analyzing {len(jobs)} jobs...")
    kept = discarded = errors = 0
    for job in jobs:
        result = analyze_job(job)
        if not result:
            errors += 1
            continue
        german_required = result.get("german_required")
        score = int(result.get("relevance_score", 0))
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
    print(f"Analysis done: {kept} kept, {discarded} discarded, {errors} errors")

if __name__ == "__main__":
    run_analysis(limit=2000)
