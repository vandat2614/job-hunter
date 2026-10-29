from types import SimpleNamespace

from app.matcher import is_match


def sub(**kw):
    base = dict(active=True, skills=[], location=None, min_salary=None, currency=None)
    return SimpleNamespace(**{**base, **kw})


JOB = {
    "skills": ["python", "kafka", "docker"],
    "location": "Hồ Chí Minh",
    "salary_min": 2000,
    "salary_max": 3000,
    "salary_currency": "USD",
}


def test_empty_subscription_matches_everything():
    assert is_match(JOB, sub())


def test_inactive_subscription_never_matches():
    assert not is_match(JOB, sub(active=False))


def test_all_skills_required():
    assert is_match(JOB, sub(skills=["python", "kafka"]))
    assert not is_match(JOB, sub(skills=["python", "java"]))


def test_job_without_skills():
    assert not is_match({**JOB, "skills": []}, sub(skills=["python"]))


def test_location_ignores_accents_and_case():
    assert is_match(JOB, sub(location="ho chi minh"))
    assert not is_match(JOB, sub(location="Hanoi"))


def test_salary_threshold():
    assert is_match(JOB, sub(min_salary=2500, currency="USD"))
    assert not is_match(JOB, sub(min_salary=4000, currency="USD"))


def test_salary_currency_must_match():
    assert not is_match(JOB, sub(min_salary=1000, currency="VND"))


def test_job_without_salary_fails_salary_filter():
    no_salary = {**JOB, "salary_min": None, "salary_max": None, "salary_currency": None}
    assert not is_match(no_salary, sub(min_salary=1000, currency="USD"))
    assert is_match(no_salary, sub(skills=["python"]))
