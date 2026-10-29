import pytest

from app.formatter import format_message, format_salary
from app.telegram import PermanentError, TemporaryError, classify_response


@pytest.mark.parametrize(
    "smin, smax, cur, expected",
    [
        (2000, 3000, "USD", "2,000 - 3,000 USD"),
        (1500, 1500, "USD", "1,500 USD"),
        (None, 30_000_000, "VND", "up to 30,000,000 VND"),
        (15_000_000, None, "VND", "from 15,000,000 VND"),
        (None, None, None, None),
        (2000, 3000, None, "2,000 - 3,000"),
    ],
)
def test_format_salary(smin, smax, cur, expected):
    assert format_salary(smin, smax, cur) == expected


def test_format_message_full():
    text = format_message({
        "title": "Backend Engineer", "company": "Acme", "location": "Remote",
        "salary_min": 2000, "salary_max": 3000, "salary_currency": "USD",
        "url": "https://example.com/j/1",
    })
    assert "Backend Engineer" in text
    assert "Acme | Remote" in text
    assert "Salary: 2,000 - 3,000 USD" in text
    assert text.endswith("https://example.com/j/1")


def test_format_message_minimal():
    text = format_message({"title": "Dev", "company": "Acme"})
    assert "Salary" not in text
    assert "http" not in text


def test_format_message_requires_title():
    with pytest.raises(KeyError):
        format_message({"company": "Acme"})


def test_classify_success():
    assert classify_response(200, {"ok": True}) is None


@pytest.mark.parametrize("status", [429, 500, 502])
def test_classify_temporary(status):
    assert isinstance(classify_response(status, {"description": "x"}), TemporaryError)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_classify_permanent(status):
    assert isinstance(classify_response(status, {"description": "chat not found"}), PermanentError)
