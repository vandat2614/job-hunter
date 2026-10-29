import pytest

from app.security import extract_bearer


@pytest.mark.parametrize(
    "header, expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer abc", "abc"),
        ("Bearer   abc  ", "abc"),
        ("Basic abc", None),
        ("Bearer", None),
        ("Bearer ", None),
        ("", None),
        (None, None),
    ],
)
def test_extract_bearer(header, expected):
    assert extract_bearer(header) == expected
