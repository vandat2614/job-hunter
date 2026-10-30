import re

# NOTE: copied from job-service/app/normalize.py. The two lists must stay in sync.
SKILLS = [
    "python", "java", "javascript", "typescript", "golang", "c++", "c#", "php",
    "node.js", "react", "vue", "angular", "django", "fastapi", "flask", "spring",
    "docker", "kubernetes", "terraform", "aws", "azure", "gcp", "linux", "git",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq", "sql",
]
_SKILL_RES = {s: re.compile(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])") for s in SKILLS}


def extract_skills(*texts: str | None) -> list[str]:
    blob = " ".join(t for t in texts if t).lower()
    return [s for s, rx in _SKILL_RES.items() if rx.search(blob)]


def analyze_skills(job_skills: list[str], cv_skills: list[str]):
    """Return (matched, missing, ratio). ratio is None when the job lists no skills."""
    job = {s.lower() for s in job_skills}
    cv = {s.lower() for s in cv_skills}
    matched = sorted(job & cv)
    missing = sorted(job - cv)
    ratio = len(matched) / len(job) if job else None
    return matched, missing, ratio
