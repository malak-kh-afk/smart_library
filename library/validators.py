"""Small reusable input checks, used by the services before touching the database."""
import re
from datetime import date

from .exceptions import ValidationError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MEMBER_TYPES = ("student", "instructor")


def clean_text(value, field, max_len=150, required=True):
    text = " ".join(str(value if value is not None else "").split())
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_len:
        raise ValidationError(f"{field} is too long (maximum {max_len} characters).")
    return text


def positive_int(value, field, minimum=1):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number.")
    if number < minimum:
        raise ValidationError(f"{field} must be at least {minimum}.")
    return number


def valid_email(value):
    email = clean_text(value, "Email").lower()
    if not _EMAIL.match(email):
        raise ValidationError(f"'{email}' is not a valid email address.")
    return email


def valid_member_type(value):
    member_type = clean_text(value, "Member type").lower()
    if member_type not in MEMBER_TYPES:
        raise ValidationError(f"Member type must be one of: {', '.join(MEMBER_TYPES)}.")
    return member_type


def valid_isbn(value):
    isbn = clean_text(value, "ISBN").replace("-", "").replace(" ", "").upper()
    if not (5 <= len(isbn) <= 20 and isbn.isalnum()):
        raise ValidationError("ISBN must be 5 to 20 letters/digits (dashes allowed).")
    return isbn


def valid_year(value):
    if value in (None, ""):
        return None
    year = positive_int(value, "Publication year", minimum=1000)
    if year > date.today().year + 1:
        raise ValidationError("Publication year cannot be in the future.")
    return year


def valid_amount(value, field="Amount"):
    try:
        amount = round(float(value), 3)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number.")
    if amount <= 0:
        raise ValidationError(f"{field} must be greater than zero.")
    return amount
