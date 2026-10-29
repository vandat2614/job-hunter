import pytest

from app.normalize import extract_skills, make_dedup_key, norm_text, parse_salary


# ---------- parse_salary ----------
@pytest.mark.parametrize(
    "text, expected",
    [
        ("25 - 35 triệu", (25_000_000, 35_000_000, "VND")),
        ("$2000 - $3000", (2000, 3000, "USD")),
        ("1,500 USD", (1500, 1500, "USD")),
        ("1.500.000", (1_500_000, 1_500_000, "VND")),
        ("Tới 30 triệu", (None, 30_000_000, "VND")),
        ("Từ 15 triệu", (15_000_000, None, "VND")),
        ("Thỏa thuận", (None, None, None)),
        ("", (None, None, None)),
        (None, (None, None, None)),
    ],
)
def test_parse_salary(text, expected):
    assert parse_salary(text) == expected


# ---------- norm_text / dedup ----------
def test_norm_text_removes_accents_and_punctuation():
    assert norm_text("  Hồ Chí  Minh! ") == "ho chi minh"
    assert norm_text("Đà Nẵng") == "da nang"
    assert norm_text(None) == ""


def test_dedup_key_ignores_accents_and_case():
    a = make_dedup_key("ABC Corp", "Senior Python Developer", "Hồ Chí Minh")
    b = make_dedup_key("abc corp", "senior python developer", "Ho Chi Minh")
    assert a == b
    assert len(a) == 64


def test_dedup_key_differs_for_different_company():
    a = make_dedup_key("ABC Corp", "Python Dev", "Hanoi")
    b = make_dedup_key("XYZ Corp", "Python Dev", "Hanoi")
    assert a != b


# ---------- extract_skills ----------
def test_extract_skills_basic():
    assert extract_skills("Python, FastAPI, Docker, Kafka") == ["python", "fastapi", "docker", "kafka"]


def test_extract_skills_no_partial_match():
    # "java" không được khớp trong "javascript", "sql" không khớp trong "postgresql"
    assert extract_skills("JavaScript developer") == ["javascript"]
    assert extract_skills("PostgreSQL") == ["postgresql"]


def test_extract_skills_handles_none():
    assert extract_skills(None, "Python") == ["python"]
    assert extract_skills(None, None) == []
