"""Console interface: menus, input helpers, and table printing.
Every LibraryError is caught here and shown as a clear message (no crashes)."""
from datetime import date

from .exceptions import LibraryError


def ask(prompt, cast=str, required=True):
    while True:
        raw = input(prompt).strip()
        if not raw:
            if required:
                print("  ! This field cannot be empty.")
                continue
            return ""
        try:
            return cast(raw)
        except ValueError:
            print("  ! Invalid input, please enter a valid number." if cast is not str else "  ! Invalid input.")


def table(rows, columns):
    """columns = [(header, key), ...]"""
    if not rows:
        print("  (nothing to show)")
        return
    data = [[str(r[k]) if r[k] is not None else "-" for _, k in columns] for r in rows]
    widths = [max(len(h), *(len(row[i]) for row in data)) for i, (h, _) in enumerate(columns)]
    print("  " + " | ".join(h.ljust(widths[i]) for i, (h, _) in enumerate(columns)))
    print("  " + "-+-".join("-" * w for w in widths))
    for row in data:
        print("  " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(row)))


def run_menu(title, options):
    while True:
        print(f"\n=== {title} ===")
        for i, (label, _) in enumerate(options, 1):
            print(f" {i}. {label}")
        print(" 0. Back / Exit")
        choice = ask("Choice: ")
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            try:
                options[int(choice) - 1][1]()
            except LibraryError as err:
                print(f"  X Rejected: {err}")
        else:
            print("  ! Please choose one of the listed numbers.")


class ConsoleApp:
    def __init__(self, system):
        self.s = system

    # ---- books
    def add_book(self):
        b = self.s.books.add_book(ask("ISBN: "), ask("Title: "), ask("Author: "), ask("Category: "),
                                  ask("Number of copies: ", int), ask("Publisher (optional): ", required=False),
                                  ask("Year (optional): ", int, required=False) or None)
        print(f"  OK Book registered with id {b.book_id}.")

    def search_books(self):
        found = self.s.books.search(ask("Keyword (title/author/ISBN, Enter = all): ", required=False),
                                    ask("Category (Enter = all): ", required=False),
                                    ask("Only available? (y/n): ", required=False).lower() == "y")
        table([vars(b) for b in found], [("ID", "book_id"), ("Title", "title"), ("Author", "author"),
                                         ("Category", "category"), ("Total", "total_copies"),
                                         ("Available", "available_copies")])

    def update_book(self):
        book_id = ask("Book id: ", int)
        print("  Leave a field empty to keep its current value.")
        changes = {}
        for field, label, cast in [("title", "Title", str), ("author", "Author", str), ("category", "Category", str),
                                   ("publisher", "Publisher", str), ("publication_year", "Year", int),
                                   ("total_copies", "Total copies", int)]:
            value = ask(f"New {label}: ", cast, required=False)
            if value != "":
                changes[field] = value
        self.s.books.update_book(book_id, **changes)
        print("  OK Book updated.")

    # ---- members
    def register_member(self):
        m = self.s.members.register(ask("First name: "), ask("Last name: "), ask("Email: "),
                                    ask("Type (student/instructor): "))
        print(f"  OK Member registered with id {m.member_id}.")

    def update_member(self):
        member_id = ask("Member id: ", int)
        print("  Leave a field empty to keep its current value.")
        changes = {}
        for field, label in [("first_name", "First name"), ("last_name", "Last name"),
                             ("email", "Email"), ("member_type", "Type (student/instructor)")]:
            value = ask(f"New {label}: ", required=False)
            if value:
                changes[field] = value
        self.s.members.update_member(member_id, **changes)
        print("  OK Member updated.")

    def list_members(self):
        table([vars(m) for m in self.s.members.list_members()],
              [("ID", "member_id"), ("First", "first_name"), ("Last", "last_name"), ("Email", "email"),
               ("Type", "member_type")])

    def member_history(self):
        table(self.s.members.history(ask("Member id: ", int)),
              [("Loan", "loan_id"), ("Title", "title"), ("Borrowed", "borrow_date"), ("Due", "due_date"),
               ("Returned", "return_date")])

    # ---- loans
    def borrow(self):
        member_id = ask("Member id: ", int)
        ids = ask("Book id(s), separated by commas: ")
        try:
            book_ids = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            print("  ! Book ids must be numbers.")
            return
        for book_id, loan, error in self.s.loans.borrow_many(member_id, book_ids):
            if loan:
                print(f"  OK Book {book_id} approved, due on {loan.due_date}.")
            else:
                print(f"  X Book {book_id} refused: {error}")

    def return_book(self):
        r = self.s.loans.return_book(ask("Member id: ", int), ask("Book id: ", int))
        if r.days_late:
            print(f"  OK Returned {r.days_late} day(s) late. Penalty: {r.penalty.amount:g} DT (id {r.penalty.penalty_id}).")
        else:
            print("  OK Returned on time.")
        for res in r.promoted:
            m = self.s.members.get_member(res.member_id)
            print(f"  -> Reservation {res.reservation_id}: {m.full_name} (id {m.member_id}) can now borrow this book.")

    def active_loans(self):
        table(self.s.loans.active_loans(), [("Loan", "loan_id"), ("Member", "member"), ("Title", "title"),
                                            ("Borrowed", "borrow_date"), ("Due", "due_date")])

    # ---- reservations
    def reserve(self):
        r = self.s.reservations.reserve(ask("Member id: ", int), ask("Book id: ", int))
        print(f"  OK Reservation {r.reservation_id} registered.")

    def cancel_reservation(self):
        self.s.reservations.cancel(ask("Reservation id: ", int))
        print("  OK Reservation cancelled.")

    def show_queue(self):
        table(self.s.reservations.queue(ask("Book id: ", int)),
              [("Pos", "position"), ("Res.", "reservation_id"), ("Member", "member"), ("Status", "status"),
               ("Created", "created_at")])

    def member_reservations(self):
        table(self.s.reservations.for_member(ask("Member id: ", int)),
              [("Res.", "reservation_id"), ("Title", "title"), ("Status", "status"), ("Created", "created_at")])

    # ---- penalties
    def show_penalties(self):
        rows = [{**vars(p), "outstanding": p.outstanding} for p in self.s.penalties.outstanding()]
        table(rows, [("Penalty", "penalty_id"), ("Member", "member_id"), ("Loan", "loan_id"),
                     ("Days late", "days_late"), ("Amount", "amount"), ("Paid", "paid"), ("Owed", "outstanding")])

    def pay_penalty(self):
        p = self.s.penalties.pay(ask("Penalty id: ", int), ask("Amount paid (DT): ", float))
        print(f"  OK Payment recorded. Remaining: {p.outstanding:g} DT.")

    # ---- statistics
    def statistics(self):
        st = self.s.stats
        print("\n--- Most borrowed books ---")
        table(st.most_borrowed(), [("Title", "title"), ("Times borrowed", "times_borrowed")])
        print(f"\n--- Active loans: {st.active_loans_count()}")
        print("\n--- Overdue resources ---")
        table(st.overdue(), [("Loan", "loan_id"), ("Member", "member"), ("Title", "title"), ("Due", "due_date"),
                             ("Days late", "days_late"), ("Penalty so far (DT)", "penalty_so_far")])
        print("\n--- Books currently unavailable ---")
        table([vars(b) for b in st.unavailable_books()], [("ID", "book_id"), ("Title", "title"), ("Copies", "total_copies")])
        print("\n--- Members with outstanding penalties ---")
        table(st.members_with_penalties(), [("ID", "member_id"), ("Member", "member"), ("Amount due (DT)", "amount_due")])
        print("\n--- Borrowing by category ---")
        table(st.borrowing_by_category(), [("Category", "category"), ("Loans", "loans")])
        print(f"\n--- Total penalties collected: {st.total_penalties_collected():g} DT")

    def run(self):
        print(f"Smart Library Management System  -  {date.today().isoformat()}")
        run_menu("MAIN MENU", [
            ("Books", lambda: run_menu("BOOKS", [("Register a book", self.add_book), ("Search catalog / availability", self.search_books),
                                                 ("Update a book", self.update_book)])),
            ("Members", lambda: run_menu("MEMBERS", [("Register a member", self.register_member), ("Update a member", self.update_member),
                                                     ("List members", self.list_members), ("Borrowing history", self.member_history)])),
            ("Borrow books", self.borrow),
            ("Return a book", self.return_book),
            ("Active loans", self.active_loans),
            ("Reservations", lambda: run_menu("RESERVATIONS", [("Reserve a book", self.reserve), ("Cancel a reservation", self.cancel_reservation),
                                                               ("Waiting queue of a book", self.show_queue), ("Reservations of a member", self.member_reservations)])),
            ("Penalties", lambda: run_menu("PENALTIES", [("Outstanding penalties", self.show_penalties), ("Record a payment", self.pay_penalty)])),
            ("Statistics", self.statistics),
        ])
        print("Goodbye! All data has been saved.")
