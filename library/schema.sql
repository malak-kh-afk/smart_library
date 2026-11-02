-- Smart Library Management System : relational schema (SQLite)
-- Dates are stored as ISO text (YYYY-MM-DD). Available copies are NOT stored:
-- they are computed as total_copies - (number of active loans), so the
-- information can never become inconsistent.

CREATE TABLE IF NOT EXISTS members (
    member_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    member_type   TEXT NOT NULL CHECK (member_type IN ('student', 'instructor')),
    registered_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    book_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn             TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    author           TEXT NOT NULL,
    publisher        TEXT,
    publication_year INTEGER,
    category         TEXT NOT NULL,
    total_copies     INTEGER NOT NULL CHECK (total_copies >= 0)
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id   INTEGER NOT NULL REFERENCES members(member_id),
    book_id     INTEGER NOT NULL REFERENCES books(book_id),
    borrow_date TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    return_date TEXT                       -- NULL = loan still active
);

CREATE TABLE IF NOT EXISTS reservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,  -- increasing id = chronological order
    member_id      INTEGER NOT NULL REFERENCES members(member_id),
    book_id        INTEGER NOT NULL REFERENCES books(book_id),
    created_at     TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('WAITING', 'READY', 'FULFILLED', 'CANCELLED'))
);

CREATE TABLE IF NOT EXISTS penalties (
    penalty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id    INTEGER NOT NULL UNIQUE REFERENCES loans(loan_id),  -- one penalty per late loan
    member_id  INTEGER NOT NULL REFERENCES members(member_id),
    days_late  INTEGER NOT NULL CHECK (days_late > 0),
    amount     REAL NOT NULL CHECK (amount > 0),
    created_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    penalty_id INTEGER NOT NULL REFERENCES penalties(penalty_id),
    amount     REAL NOT NULL CHECK (amount > 0),
    paid_on    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_loans_active ON loans(book_id, return_date);
CREATE INDEX IF NOT EXISTS idx_res_queue    ON reservations(book_id, status);
