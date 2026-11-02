"""Business logic. One service class per functional area of the project statement."""
from datetime import date, datetime, timedelta

from .exceptions import BusinessRuleError, NotFoundError, ValidationError
from .models import (PENALTY_PER_DAY, Book, Loan, Member, Penalty, Reservation, ReturnResult)
from . import validators as v


# ----------------------------------------------------------------- books ----
class BookService:
    _SELECT = ("SELECT b.*, b.total_copies - (SELECT COUNT(*) FROM loans l "
               "WHERE l.book_id = b.book_id AND l.return_date IS NULL) AS available_copies FROM books b")

    def __init__(self, db):
        self.db = db
        self.on_stock_increase = None  # callback set by LibrarySystem (promotes reservations)

    def add_book(self, isbn, title, author, category, total_copies, publisher="", year=None):
        isbn = v.valid_isbn(isbn)
        if self.db.query_one("SELECT 1 FROM books WHERE isbn = ?", (isbn,)):
            raise ValidationError(f"A book with ISBN {isbn} already exists. Update its copies instead.")
        with self.db.transaction():
            cur = self.db.execute(
                "INSERT INTO books (isbn, title, author, publisher, publication_year, category, total_copies) "
                "VALUES (?,?,?,?,?,?,?)",
                (isbn, v.clean_text(title, "Title"), v.clean_text(author, "Author"),
                 v.clean_text(publisher, "Publisher", required=False), v.valid_year(year),
                 v.clean_text(category, "Category"), v.positive_int(total_copies, "Copies", 1)))
        return self.get_book(cur.lastrowid)

    def get_book(self, book_id):
        row = self.db.query_one(self._SELECT + " WHERE b.book_id = ?", (book_id,))
        if not row:
            raise NotFoundError(f"No book with id {book_id}.")
        return Book.from_row(row)

    def update_book(self, book_id, **changes):
        book = self.get_book(book_id)
        cleaners = {"title": lambda x: v.clean_text(x, "Title"), "author": lambda x: v.clean_text(x, "Author"),
                    "publisher": lambda x: v.clean_text(x, "Publisher", required=False),
                    "publication_year": v.valid_year, "category": lambda x: v.clean_text(x, "Category"),
                    "total_copies": lambda x: v.positive_int(x, "Copies", 0)}
        fields = {}
        for key, value in changes.items():
            if key not in cleaners:
                raise ValidationError(f"Field '{key}' cannot be updated.")
            fields[key] = cleaners[key](value)
        if "total_copies" in fields:
            borrowed = book.total_copies - book.available_copies
            if fields["total_copies"] < borrowed:
                raise BusinessRuleError(f"Cannot set copies to {fields['total_copies']}: {borrowed} are currently borrowed.")
        if not fields:
            return book
        with self.db.transaction():
            self.db.execute("UPDATE books SET " + ", ".join(f"{k} = ?" for k in fields) + " WHERE book_id = ?",
                            (*fields.values(), book_id))
            if fields.get("total_copies", 0) > book.total_copies and self.on_stock_increase:
                self.on_stock_increase(book_id)
        return self.get_book(book_id)

    def search(self, keyword="", category="", only_available=False):
        like = f"%{keyword.strip()}%"
        rows = self.db.query_all(
            self._SELECT + " WHERE (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?) AND b.category LIKE ? "
            "ORDER BY b.title", (like, like, like, f"%{category.strip()}%"))
        books = [Book.from_row(r) for r in rows]
        return [b for b in books if b.available_copies > 0] if only_available else books


# --------------------------------------------------------------- members ----
class MemberService:
    def __init__(self, db):
        self.db = db

    def register(self, first_name, last_name, email, member_type):
        email = v.valid_email(email)
        if self.db.query_one("SELECT 1 FROM members WHERE email = ?", (email,)):
            raise ValidationError(f"A member with email {email} already exists (duplicate record).")
        with self.db.transaction():
            cur = self.db.execute(
                "INSERT INTO members (first_name, last_name, email, member_type, registered_on) VALUES (?,?,?,?,?)",
                (v.clean_text(first_name, "First name", 60), v.clean_text(last_name, "Last name", 60),
                 email, v.valid_member_type(member_type), date.today().isoformat()))
        return self.get_member(cur.lastrowid)

    def get_member(self, member_id):
        row = self.db.query_one("SELECT * FROM members WHERE member_id = ?", (member_id,))
        if not row:
            raise NotFoundError(f"No member with id {member_id}.")
        return Member.from_row(row)

    def update_member(self, member_id, **changes):
        self.get_member(member_id)
        cleaners = {"first_name": lambda x: v.clean_text(x, "First name", 60),
                    "last_name": lambda x: v.clean_text(x, "Last name", 60),
                    "email": v.valid_email, "member_type": v.valid_member_type}
        fields = {}
        for key, value in changes.items():
            if key not in cleaners:
                raise ValidationError(f"Field '{key}' cannot be updated.")
            fields[key] = cleaners[key](value)
        if "email" in fields and self.db.query_one(
                "SELECT 1 FROM members WHERE email = ? AND member_id <> ?", (fields["email"], member_id)):
            raise ValidationError("Another member already uses this email.")
        if fields.get("member_type") == "student":
            active = self.db.query_one("SELECT COUNT(*) c FROM loans WHERE member_id=? AND return_date IS NULL",
                                       (member_id,))["c"]
            if active > 3:
                raise BusinessRuleError("Cannot become a student: more than 3 active loans.")
        if fields:
            with self.db.transaction():
                self.db.execute("UPDATE members SET " + ", ".join(f"{k} = ?" for k in fields) +
                                " WHERE member_id = ?", (*fields.values(), member_id))
        return self.get_member(member_id)

    def list_members(self):
        return [Member.from_row(r) for r in self.db.query_all("SELECT * FROM members ORDER BY last_name, first_name")]

    def history(self, member_id):
        """Current loans and previous returns, newest first."""
        self.get_member(member_id)
        return [dict(r) for r in self.db.query_all(
            "SELECT l.loan_id, b.title, l.borrow_date, l.due_date, l.return_date FROM loans l "
            "JOIN books b ON b.book_id = l.book_id WHERE l.member_id = ? ORDER BY l.loan_id DESC", (member_id,))]


# ---------------------------------------------------------- reservations ----
class ReservationService:
    def __init__(self, db, books, members):
        self.db, self.books, self.members = db, books, members

    def count_ready(self, book_id):
        return self.db.query_one("SELECT COUNT(*) c FROM reservations WHERE book_id=? AND status='READY'",
                                 (book_id,))["c"]

    def get_ready(self, member_id, book_id):
        row = self.db.query_one("SELECT * FROM reservations WHERE member_id=? AND book_id=? AND status='READY'",
                                (member_id, book_id))
        return Reservation.from_row(row) if row else None

    def reserve(self, member_id, book_id):
        member, book = self.members.get_member(member_id), self.books.get_book(book_id)
        if self.db.query_one("SELECT 1 FROM loans WHERE member_id=? AND book_id=? AND return_date IS NULL",
                             (member_id, book_id)):
            raise BusinessRuleError(f"{member.full_name} already has a copy of '{book.title}'.")
        if self.db.query_one("SELECT 1 FROM reservations WHERE member_id=? AND book_id=? "
                             "AND status IN ('WAITING','READY')", (member_id, book_id)):
            raise BusinessRuleError(f"{member.full_name} already has an open reservation for '{book.title}'.")
        if book.available_copies - self.count_ready(book_id) > 0:
            raise BusinessRuleError(f"'{book.title}' is available: borrow it directly instead of reserving.")
        with self.db.transaction():
            cur = self.db.execute("INSERT INTO reservations (member_id, book_id, created_at, status) VALUES (?,?,?,'WAITING')",
                                  (member_id, book_id, datetime.now().isoformat(timespec="seconds")))
        return Reservation.from_row(self.db.query_one("SELECT * FROM reservations WHERE reservation_id=?", (cur.lastrowid,)))

    def promote_waiting(self, book_id):
        """Give free copies to the oldest WAITING reservations (chronological priority)."""
        promoted = []
        with self.db.transaction():
            while self.books.get_book(book_id).available_copies - self.count_ready(book_id) > 0:
                nxt = self.db.query_one("SELECT * FROM reservations WHERE book_id=? AND status='WAITING' "
                                        "ORDER BY reservation_id LIMIT 1", (book_id,))
                if not nxt:
                    break
                self.db.execute("UPDATE reservations SET status='READY' WHERE reservation_id=?", (nxt["reservation_id"],))
                promoted.append(Reservation.from_row({**dict(nxt), "status": "READY"}))
        return promoted

    def cancel(self, reservation_id):
        row = self.db.query_one("SELECT * FROM reservations WHERE reservation_id=?", (reservation_id,))
        if not row:
            raise NotFoundError(f"No reservation with id {reservation_id}.")
        if row["status"] not in ("WAITING", "READY"):
            raise BusinessRuleError(f"Reservation {reservation_id} is already {row['status']}.")
        with self.db.transaction():
            self.db.execute("UPDATE reservations SET status='CANCELLED' WHERE reservation_id=?", (reservation_id,))
            if row["status"] == "READY":
                self.promote_waiting(row["book_id"])

    def queue(self, book_id):
        self.books.get_book(book_id)
        rows = self.db.query_all(
            "SELECT r.reservation_id, r.member_id, m.first_name||' '||m.last_name AS member, r.status, r.created_at "
            "FROM reservations r JOIN members m USING(member_id) "
            "WHERE r.book_id=? AND r.status IN ('WAITING','READY') ORDER BY r.reservation_id", (book_id,))
        return [{"position": i + 1, **dict(r)} for i, r in enumerate(rows)]

    def for_member(self, member_id):
        self.members.get_member(member_id)
        return [dict(r) for r in self.db.query_all(
            "SELECT r.reservation_id, b.title, r.status, r.created_at FROM reservations r "
            "JOIN books b USING(book_id) WHERE r.member_id=? ORDER BY r.reservation_id DESC", (member_id,))]


# ------------------------------------------------------------- penalties ----
class PenaltyService:
    _SELECT = ("SELECT p.*, COALESCE((SELECT SUM(amount) FROM payments x WHERE x.penalty_id = p.penalty_id), 0) "
               "AS paid FROM penalties p")

    def __init__(self, db):
        self.db = db

    @staticmethod
    def calculate(days_late):
        return round(max(0, days_late) * PENALTY_PER_DAY, 3)

    def create_for_loan(self, loan, days_late, today):
        with self.db.transaction():
            cur = self.db.execute("INSERT INTO penalties (loan_id, member_id, days_late, amount, created_on) "
                                  "VALUES (?,?,?,?,?)", (loan.loan_id, loan.member_id, days_late,
                                                         self.calculate(days_late), today.isoformat()))
        return self.get(cur.lastrowid)

    def get(self, penalty_id):
        row = self.db.query_one(self._SELECT + " WHERE p.penalty_id = ?", (penalty_id,))
        if not row:
            raise NotFoundError(f"No penalty with id {penalty_id}.")
        return Penalty.from_row(row)

    def outstanding(self, member_id=None):
        sql = self._SELECT + (" WHERE p.member_id = ?" if member_id else "") + " ORDER BY p.penalty_id"
        rows = self.db.query_all(sql, (member_id,) if member_id else ())
        return [p for p in map(Penalty.from_row, rows) if p.outstanding > 0]

    def pay(self, penalty_id, amount, today=None):
        amount = v.valid_amount(amount)
        penalty = self.get(penalty_id)
        if penalty.outstanding <= 0:
            raise BusinessRuleError(f"Penalty {penalty_id} is already fully paid.")
        if amount > penalty.outstanding + 1e-9:
            raise BusinessRuleError(f"Payment ({amount:g} DT) exceeds the amount owed ({penalty.outstanding:g} DT).")
        with self.db.transaction():
            self.db.execute("INSERT INTO payments (penalty_id, amount, paid_on) VALUES (?,?,?)",
                            (penalty_id, amount, (today or date.today()).isoformat()))
        return self.get(penalty_id)


# ----------------------------------------------------------------- loans ----
class LoanService:
    def __init__(self, db, books, members, reservations, penalties):
        self.db, self.books, self.members = db, books, members
        self.reservations, self.penalties = reservations, penalties

    def active_count(self, member_id):
        return self.db.query_one("SELECT COUNT(*) c FROM loans WHERE member_id=? AND return_date IS NULL",
                                 (member_id,))["c"]

    def borrow(self, member_id, book_id, today=None):
        today = today or date.today()
        member, book = self.members.get_member(member_id), self.books.get_book(book_id)
        rules = member.rules
        if self.active_count(member_id) >= rules.max_loans:
            raise BusinessRuleError(f"{member.full_name} ({member.member_type}) already has "
                                    f"{rules.max_loans} active loans, the maximum allowed.")
        if self.db.query_one("SELECT 1 FROM loans WHERE member_id=? AND book_id=? AND return_date IS NULL",
                             (member_id, book_id)):
            raise BusinessRuleError(f"{member.full_name} already borrowed '{book.title}'.")
        if book.available_copies <= 0:
            raise BusinessRuleError(f"All {book.total_copies} copies of '{book.title}' are borrowed. You can reserve it.")
        mine = self.reservations.get_ready(member_id, book_id)
        if not mine and book.available_copies - self.reservations.count_ready(book_id) <= 0:
            raise BusinessRuleError(f"The free copy of '{book.title}' is held for a member whose reservation is ready.")
        due = today + timedelta(days=rules.loan_days)
        with self.db.transaction():
            cur = self.db.execute("INSERT INTO loans (member_id, book_id, borrow_date, due_date) VALUES (?,?,?,?)",
                                  (member_id, book_id, today.isoformat(), due.isoformat()))
            if mine:
                self.db.execute("UPDATE reservations SET status='FULFILLED' WHERE reservation_id=?", (mine.reservation_id,))
        return Loan.from_row(self.db.query_one("SELECT * FROM loans WHERE loan_id=?", (cur.lastrowid,)))

    def borrow_many(self, member_id, book_ids, today=None):
        """Handle several requests: approve what is possible, explain what is not."""
        results = []
        for book_id in book_ids:
            try:
                results.append((book_id, self.borrow(member_id, book_id, today), None))
            except (BusinessRuleError, NotFoundError, ValidationError) as err:
                results.append((book_id, None, str(err)))
        return results

    def return_book(self, member_id, book_id, today=None):
        today = today or date.today()
        row = self.db.query_one("SELECT * FROM loans WHERE member_id=? AND book_id=? AND return_date IS NULL",
                                (member_id, book_id))
        if not row:
            raise BusinessRuleError("No active loan matches this member and book: nothing to return.")
        loan = Loan.from_row(row)
        if today < date.fromisoformat(loan.borrow_date):
            raise ValidationError("Return date cannot be before the borrow date.")
        days_late = max(0, (today - date.fromisoformat(loan.due_date)).days)
        with self.db.transaction():
            self.db.execute("UPDATE loans SET return_date=? WHERE loan_id=?", (today.isoformat(), loan.loan_id))
            penalty = self.penalties.create_for_loan(loan, days_late, today) if days_late else None
            promoted = self.reservations.promote_waiting(book_id)
        loan = Loan.from_row(self.db.query_one("SELECT * FROM loans WHERE loan_id=?", (loan.loan_id,)))
        return ReturnResult(loan, days_late, penalty, promoted)

    def active_loans(self, member_id=None):
        sql = ("SELECT l.loan_id, l.member_id, m.first_name||' '||m.last_name AS member, l.book_id, b.title, "
               "l.borrow_date, l.due_date FROM loans l JOIN members m USING(member_id) JOIN books b USING(book_id) "
               "WHERE l.return_date IS NULL" + (" AND l.member_id = ?" if member_id else "") + " ORDER BY l.due_date")
        return [dict(r) for r in self.db.query_all(sql, (member_id,) if member_id else ())]


# ------------------------------------------------------------ statistics ----
class StatisticsService:
    def __init__(self, db, loans, books):
        self.db, self.loans, self.books = db, loans, books

    def most_borrowed(self, limit=5):
        return [dict(r) for r in self.db.query_all(
            "SELECT b.title, COUNT(*) AS times_borrowed FROM loans l JOIN books b USING(book_id) "
            "GROUP BY b.book_id ORDER BY times_borrowed DESC, b.title LIMIT ?", (limit,))]

    def active_loans_count(self):
        return self.db.query_one("SELECT COUNT(*) c FROM loans WHERE return_date IS NULL")["c"]

    def overdue(self, today=None):
        today = today or date.today()
        rows = [r for r in self.loans.active_loans() if r["due_date"] < today.isoformat()]
        for r in rows:
            r["days_late"] = (today - date.fromisoformat(r["due_date"])).days
            r["penalty_so_far"] = PenaltyService.calculate(r["days_late"])
        return rows

    def unavailable_books(self):
        return [b for b in self.books.search() if b.available_copies == 0]

    def members_with_penalties(self):
        return [dict(r) for r in self.db.query_all(
            "SELECT m.member_id, m.first_name||' '||m.last_name AS member, "
            "SUM(p.amount - COALESCE(pay.paid, 0)) AS amount_due FROM penalties p JOIN members m USING(member_id) "
            "LEFT JOIN (SELECT penalty_id, SUM(amount) paid FROM payments GROUP BY penalty_id) pay "
            "ON pay.penalty_id = p.penalty_id GROUP BY m.member_id HAVING amount_due > 0.0005")]

    def borrowing_by_category(self):
        return [dict(r) for r in self.db.query_all(
            "SELECT b.category, COUNT(*) AS loans FROM loans l JOIN books b USING(book_id) "
            "GROUP BY b.category ORDER BY loans DESC")]

    def total_penalties_collected(self):
        return round(self.db.query_one("SELECT COALESCE(SUM(amount),0) s FROM payments")["s"], 3)
