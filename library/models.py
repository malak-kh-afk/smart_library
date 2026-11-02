"""Domain model: plain classes (dataclasses) describing the library's entities,
plus the business constants (loan limits, loan durations, penalty rate)."""
from dataclasses import dataclass
from typing import Optional

# ---- Business rules (section 5 of the project statement) -------------------
PENALTY_PER_DAY = 1.0  # DT per day of delay


@dataclass(frozen=True)
class MemberRules:
    max_loans: int
    loan_days: int


MEMBER_RULES = {
    "student": MemberRules(max_loans=3, loan_days=14),
    "instructor": MemberRules(max_loans=5, loan_days=21),
}


# ---- Entities ---------------------------------------------------------------
@dataclass
class Member:
    member_id: int
    first_name: str
    last_name: str
    email: str
    member_type: str
    registered_on: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def rules(self) -> MemberRules:
        return MEMBER_RULES[self.member_type]

    @classmethod
    def from_row(cls, row):
        return cls(**dict(row))


@dataclass
class Book:
    book_id: int
    isbn: str
    title: str
    author: str
    publisher: Optional[str]
    publication_year: Optional[int]
    category: str
    total_copies: int
    available_copies: int  # computed by the query, never stored

    @classmethod
    def from_row(cls, row):
        return cls(**dict(row))


@dataclass
class Loan:
    loan_id: int
    member_id: int
    book_id: int
    borrow_date: str
    due_date: str
    return_date: Optional[str]

    @property
    def is_active(self) -> bool:
        return self.return_date is None

    @classmethod
    def from_row(cls, row):
        return cls(**dict(row))


@dataclass
class Reservation:
    reservation_id: int
    member_id: int
    book_id: int
    created_at: str
    status: str  # WAITING | READY | FULFILLED | CANCELLED

    @classmethod
    def from_row(cls, row):
        return cls(**dict(row))


@dataclass
class Penalty:
    penalty_id: int
    loan_id: int
    member_id: int
    days_late: int
    amount: float
    created_on: str
    paid: float = 0.0  # sum of payments, computed by the query

    @property
    def outstanding(self) -> float:
        return round(self.amount - self.paid, 3)

    @classmethod
    def from_row(cls, row):
        return cls(**dict(row))


@dataclass
class ReturnResult:
    """What happened when a book was returned (used to give feedback to the librarian)."""
    loan: Loan
    days_late: int
    penalty: Optional[Penalty]
    promoted: list  # reservations that became READY because a copy was freed
