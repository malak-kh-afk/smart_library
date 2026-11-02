# Smart Library Management System Initial Prototype

Team: Malak kharbech & Ahmed Kouki  Python 3 (standard library only, no installation needed)

## Run
    python main.py --demo     # first run with sample data
    python main.py            # normal run (data kept in data/library.db)
    python -m unittest discover -s tests -v    # run the 11 automated tests

## Structure
    main.py                 entry point
    library/models.py       entities (Member, Book, Loan, Reservation, Penalty) + business constants
    library/schema.sql      relational schema (6 tables)
    library/database.py     SQLite persistence + safe nested transactions
    library/validators.py   input checks
    library/exceptions.py   ValidationError / NotFoundError / BusinessRuleError
    library/services.py     business logic: Book, Member, Loan, Reservation, Penalty, Statistics services
    library/cli.py          console menus
    library/seed.py         demo data
    tests/test_library.py   unit tests

## Entity-Relationship (Lucid)


## Business rules implemented
Unique members (id + email) · student 3 loans/14 days · instructor 5 loans/21 days · no borrowing of unavailable copies ·
return must match an active loan · 1 DT/day penalty · reservations served in chronological order (a freed copy is held
for the first waiting member) · clear error messages for every rejected operation.

## Not yet done (next iterations)
Reservation expiry, blocking borrowing for members with unpaid penalties, GUI, requirements document, formal ER diagram.
