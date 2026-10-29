import hashlib
import re
import unicodedata

SKILLS = [
    "python", "java", "javascript", "typescript", "golang", "c++", "c#", "php",
    "node.js", "react", "vue", "angular", "django", "fastapi", "flask", "spring",
    "docker", "kubernetes", "terraform", "aws", "azure", "gcp", "linux", "git",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq", "sql",
]
_SKILL_RES = {s: re.compile(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])") for s in SKILLS}


def strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm_text(s: str | None) -> str:
    s = strip_accents(s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def make_dedup_key(company: str, title: str, location: str | None) -> str:
    raw = "|".join(norm_text(x) for x in (company, title, location))
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_salary(text: str | None):
    """Return (min, max, currency), or (None, None, None) if unparseable."""
    if not text:
        return None, None, None
    t = strip_accents(text).lower().replace(",", "")
    t = re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", t)  # 1.500.000 -> 1500000
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if not nums:
        return None, None, None
    if re.search(r"usd|\$", t):
        cur, mult = "USD", 1
    elif re.search(r"trieu|\btr\b", t):
        cur, mult = "VND", 1_000_000
    else:
        cur, mult = "VND", 1
    vals = [int(float(n) * mult) for n in nums[:2]]
    if len(vals) == 2:
        return min(vals), max(vals), cur
    if re.search(r"\btoi\b|up to", t):
        return None, vals[0], cur
    if re.search(r"\btu\b|from", t):
        return vals[0], None, cur
    return vals[0], vals[0], cur


def extract_skills(*texts: str | None) -> list[str]:
    blob = " ".join(t for t in texts if t).lower()
    return [s for s, rx in _SKILL_RES.items() if rx.search(blob)]
