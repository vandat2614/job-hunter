import asyncio
import logging
from dataclasses import dataclass

from app.config import settings
from app.llm import LLMError
from app.skills import analyze_skills

log = logging.getLogger("scoring")

EXP_VALUE = {"below": 0.3, "meets": 0.8, "exceeds": 1.0}
SKILL_WEIGHT = 70
EXP_WEIGHT = 30


@dataclass
class Assessment:
    experience: str
    note: str


def parse_assessment(raw) -> Assessment:
    """Validate the LLM output. Never trust it, even when a schema was requested."""
    if not isinstance(raw, dict):
        raise LLMError("assessment is not an object")
    experience = raw.get("experience")
    if experience not in EXP_VALUE:
        raise LLMError(f"invalid experience level: {experience!r}")
    note = raw.get("note")
    note = " ".join(note.split())[:300] if isinstance(note, str) else ""
    return Assessment(experience, note)


def compute_score(skill_ratio: float | None, experience: str | None) -> tuple[int | None, str]:
    """Return (score 0-100 or None, basis)."""
    exp_value = EXP_VALUE.get(experience) if experience else None
    if skill_ratio is not None and exp_value is not None:
        return int(SKILL_WEIGHT * skill_ratio + EXP_WEIGHT * exp_value + 0.5), "skills_and_experience"
    if skill_ratio is not None:
        return int(100 * skill_ratio + 0.5), "skills_only"
    if exp_value is not None:
        return int(100 * exp_value + 0.5), "experience_only"
    return None, "none"


async def score_match(cv_text: str, cv_skills: list[str], job: dict, llm, retry_delay: float = 2) -> dict:
    matched, missing, ratio = analyze_skills(job.get("skills") or [], cv_skills)

    assessment = None
    for attempt in range(1, settings.llm_attempts + 1):
        try:
            assessment = parse_assessment(await llm.assess(cv_text, job))
            break
        except LLMError as e:
            log.warning("llm attempt %d/%d failed: %s", attempt, settings.llm_attempts, e)
            if attempt < settings.llm_attempts:
                await asyncio.sleep(retry_delay)

    # If the LLM is unavailable the user still gets a score, from skills alone
    score, basis = compute_score(ratio, assessment.experience if assessment else None)
    return {
        "score": score,
        "basis": basis,
        "matched_skills": matched,
        "missing_skills": missing,
        "experience": assessment.experience if assessment else None,
        "note": assessment.note if assessment else None,
        "llm": assessment is not None,
    }
