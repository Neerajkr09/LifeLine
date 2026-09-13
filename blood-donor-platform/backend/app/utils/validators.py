"""Reusable validation helpers shared across Pydantic schemas."""
import re

_PASSWORD_MIN_LENGTH = 8
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{%d,}$" % _PASSWORD_MIN_LENGTH
)
_CONTACT_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s'\-]{0,79}$")


def validate_strong_password(password: str) -> str:
    if not _PASSWORD_PATTERN.match(password):
        raise ValueError(
            "Password must be at least 8 characters and include an uppercase letter, "
            "a lowercase letter, a digit, and a special character."
        )
    return password


def validate_contact_number(contact: str) -> str:
    cleaned = contact.strip().replace(" ", "")
    if not _CONTACT_PATTERN.match(cleaned):
        raise ValueError("Contact number must be 7-15 digits, optionally prefixed with '+'.")
    return cleaned


def validate_human_name(name: str) -> str:
    cleaned = name.strip()
    if not _NAME_PATTERN.match(cleaned):
        raise ValueError("Name may only contain letters, spaces, hyphens, and apostrophes.")
    return cleaned


def sanitize_free_text(value: str, max_length: int = 500) -> str:
    """
    Defensive sanitation for free-text fields that end up stored in Mongo and
    later rendered in the frontend: strips control characters and enforces a
    hard length ceiling. This is a defense-in-depth measure -- the primary
    XSS defense is that React escapes rendered text by default, and the
    primary NoSQL-injection defense is that we never build queries from raw
    strings without typing them through Pydantic first.
    """
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
    return cleaned[:max_length]
