import time
import httpx
import config
from typing import Literal
from pydantic import BaseModel, Field, ValidationError
from concurrent.futures import ThreadPoolExecutor, as_completed
from db import get_pending_analysis, save_analysis, reject_job


class JobAnalysis(BaseModel):
    german_required: bool | None = Field(
        description="True if German language is explicitly required, false if not, null if unclear"
    )
    job_type: Literal["full_time", "part_time", "contract", "internship", "werkstudent", "freelance", "unknown"]
    relevance_score: int = Field(ge=1, le=10)
    matched_skills: list[str] = Field(
        description="Short skill names from the job that match the candidate (e.g. ['PyTorch', 'ROS2']). Max 5 items."
    )
    reasoning: str = Field(description="One short sentence explaining the score.", max_length=200)
    experience_years_required: int | None = Field(
        description="Minimum years of experience explicitly required by the job. null if not mentioned."
    )


_SCHEMA = {
    "name": "job_analysis",
    "strict": True,
    "schema": JobAnalysis.model_json_schema(),
}

SYSTEM_PROMPT = f"""You are a job relevance analyzer.

Candidate profile:
{config.PROFILE_SUMMARY}

Rules for german_required:
- true: The JD explicitly states German is required — e.g. "Deutschkenntnisse erforderlich",
  "fließend Deutsch", "Deutsch in Wort und Schrift", "Deutsch B1/B2/C1", "German required",
  "fluent German". If you see any such phrase, you MUST return true.
- false: German is clearly NOT required — English stated as working language,
  "German is a plus / von Vorteil", or JD is written entirely in English.
- null: No language requirement is mentioned at all and you cannot tell.
  Use null freely — it is not a rejection.
- Decision rule: explicit phrase present → true. Clearly not needed → false. Unclear → null.

Rules for job_type:
- full_time: permanent full-time (Festanstellung, Vollzeit)
- part_time: permanent part-time (Teilzeit)
- contract: fixed-term or project-based
- internship: Praktikum
- werkstudent: Werkstudent / working student
- freelance: freelance / self-employed
- unknown: not mentioned

Rules for relevance_score:
- 8-10: strong match, most required skills align with candidate
- 5-7: partial match, some relevant skills
- 3-4: weak match, tangentially related
- 1-2: not relevant
- Software Engineer roles without Python: score <= 3

Rules for experience_years_required:
- Extract the minimum years of professional experience explicitly stated (e.g. "3+ years", "at least 5 years experience").
- Return the integer (e.g. 3, 5). If a range is given (e.g. "3-5 years"), return the lower bound.
- Return null if no experience requirement is mentioned."""


def analyze_job(job: dict) -> JobAnalysis | None:
    text = f"Title: {job['title']}\nCompany: {job['company']}\nDescription: {job['description'][:3000]}"

    for attempt in range(3):
        try:
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "max_tokens": 600,
                    "provider": {"allow_fallbacks": True},
                    "reasoning": {"enabled": False},
                    "response_format": {"type": "json_schema", "json_schema": _SCHEMA},
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                },
                timeout=30,
            )
            data = r.json()
            if data.get("error"):
                time.sleep(2 ** attempt)
                continue
            choice = data["choices"][0]
            raw = choice["message"]["content"]
            if not raw:
                # Reasoning model burned all tokens — retry without sleeping
                if choice.get("finish_reason") == "length":
                    continue
                time.sleep(2 ** attempt)
                continue
            return JobAnalysis.model_validate_json(raw)
        except ValidationError as e:
            # Schema mismatch — likely truncated output, retry
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  analyzer error [{job['slug'][:8]}]: {e}")
            time.sleep(2 ** attempt)
    return None


# Company name fragments that are known to be English-friendly regardless of JD language.
# If the LLM incorrectly flags german_required=True for these, we override to None.
_ENGLISH_FRIENDLY_COMPANIES = [
    "max planck", "max-planck", "fraunhofer", "helmholtz", "dlr", "leibniz",
    "dfki", "hhi", "kit ", "tum ", "lmu ", "rwth", "fau ", "tu berlin",
    "tu münchen", "tu munich", "universität", "university", "hochschule",
    "research center", "research centre", "forschungszentrum",
]

def _is_english_friendly(company: str) -> bool:
    c = company.lower()
    return any(kw in c for kw in _ENGLISH_FRIENDLY_COMPANIES)


def _process(job: dict) -> str:
    result = analyze_job(job)
    if result is None:
        reject_job(job["slug"])
        return "error"

    # Override LLM if it wrongly flags a known English-friendly institution
    if result.german_required is True and _is_english_friendly(job.get("company", "")):
        result.german_required = None

    type_mismatch = (
        result.job_type != "unknown"
        and result.job_type not in config.JOB_TYPES
    )

    if result.german_required is True or result.relevance_score < config.MIN_RELEVANCE_SCORE or type_mismatch:
        reject_job(job["slug"])
        return "discard"

    # Experience routing: <=3 yrs → new, 3-5 yrs → stretch, 5+ yrs → reject
    exp = result.experience_years_required
    if exp is not None and exp > 5:
        reject_job(job["slug"])
        return "discard"
    status = "stretch" if (exp is not None and exp > 3) else "new"

    save_analysis(
        slug=job["slug"],
        german_required=1 if result.german_required is True else (0 if result.german_required is False else None),
        relevance_score=result.relevance_score,
        matched_skills=", ".join(result.matched_skills),
        reasoning=result.reasoning,
        experience_years_required=exp,
        status=status,
    )
    return "keep"


def run_analysis(limit=50, workers=25):
    jobs = get_pending_analysis(limit)
    if not jobs:
        return
    print(f"Analyzing {len(jobs)} jobs ({workers} parallel)...")
    kept = discarded = errors = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process, job): job for job in jobs}
        for future in as_completed(futures):
            outcome = future.result()
            if outcome == "keep":
                kept += 1
            elif outcome == "discard":
                discarded += 1
            else:
                errors += 1
    print(f"Analysis done: {kept} kept, {discarded} discarded, {errors} errors")


if __name__ == "__main__":
    run_analysis(limit=2000)
