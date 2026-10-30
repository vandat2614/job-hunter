import io

import pytest
from docx import Document

from app.extract import (
    MAX_TEXT_CHARS,
    EmptyDocument,
    UnsupportedFormat,
    detect_format,
    process_cv,
    redact_pii,
)


def make_docx(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------- detect_format ----------
def test_detect_format():
    assert detect_format(b"%PDF-1.7 ...") == "pdf"
    assert detect_format(b"PK\x03\x04 ...") == "docx"
    assert detect_format(b"plain text") == "txt"


# ---------- redact_pii ----------
def test_redact_email_and_url():
    out = redact_pii("Mail me@example.com or see https://github.com/me and www.site.dev")
    assert "me@example.com" not in out and "github.com" not in out and "site.dev" not in out
    assert "[email]" in out and out.count("[url]") == 2


def test_redact_phone_numbers():
    out = redact_pii("Call +84 912 345 678 or 0912.345.678 now")
    assert "912" not in out
    assert out.count("[phone]") == 2


def test_keeps_dates_and_versions():
    text = "2019 - 2022 Backend developer, Python 3.12, 5 years"
    assert redact_pii(text) == text


# ---------- process_cv ----------
def test_txt_is_cleaned_and_redacted():
    fmt, text = process_cv(b"Hello   world\r\n\r\n\r\n\r\nmail me@example.com")
    assert fmt == "txt"
    assert text == "Hello world\n\nmail [email]"


def test_docx_roundtrip():
    fmt, text = process_cv(make_docx(["Backend developer", "Python, Kafka"]))
    assert fmt == "docx"
    assert "Backend developer" in text and "Python, Kafka" in text


def test_empty_text_rejected():
    with pytest.raises(EmptyDocument):
        process_cv(b"   \n  \n")


@pytest.mark.parametrize("data", [b"\x00\x01\xff", b"\xff\xfe\xfa invalid utf8", b"%PDF-1.4 garbage", b"PK\x03\x04garbage"])
def test_unreadable_files_rejected(data):
    with pytest.raises(UnsupportedFormat):
        process_cv(data)


def test_text_is_truncated():
    _, text = process_cv(("word " * 50_000).encode())
    assert len(text) <= MAX_TEXT_CHARS
