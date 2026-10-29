import re
import unicodedata


def norm_text(s: str | None) -> str:
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s.lower())).strip()


def is_match(job: dict, sub) -> bool:
    """Return True if the job satisfies every criterion set on the subscription.

    `job` is a job.created payload; `sub` is any object with the subscription attributes.
    """
    if not sub.active:
        return False

    job_skills = {s.lower() for s in job.get("skills") or []}
    if not set(sub.skills or []) <= job_skills:
        return False

    if sub.location and norm_text(sub.location) not in norm_text(job.get("location")):
        return False

    if sub.min_salary is not None:
        top = job.get("salary_max") or job.get("salary_min")
        if top is None:
            return False
        if sub.currency and job.get("salary_currency") != sub.currency:
            return False
        if top < sub.min_salary:
            return False

    return True
