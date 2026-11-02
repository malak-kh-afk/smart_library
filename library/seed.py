"""Demo data so the professor can try the application immediately."""
from datetime import date, timedelta


def load_demo_data(s):
    if s.books.search():
        return False
    for args in [("978-1-0000-0001", "Introduction to Python Programming", "J. Smith", "Computer Science", 5),
                 ("978-1-0000-0002", "Database Systems", "R. Elmasri", "Computer Science", 2),
                 ("978-1-0000-0003", "Linear Algebra", "G. Strang", "Mathematics", 3),
                 ("978-1-0000-0004", "Classical Mechanics", "J. Taylor", "Physics", 1),
                 ("978-1-0000-0005", "Data Structures and Algorithms", "T. Cormen", "Computer Science", 2)]:
        s.books.add_book(*args)
    for args in [("Ahmed", "Kouki", "ahmed.kouki@univ.tn", "student"), ("Sara", "Ben Ali", "sara.benali@univ.tn", "student"),
                 ("Youssef", "Trabelsi", "youssef.t@univ.tn", "student"), ("Dr. Leila", "Mansour", "leila.mansour@univ.tn", "instructor")]:
        s.members.register(*args)
    today = date.today()
    s.loans.borrow(1, 1, today - timedelta(days=3))
    s.loans.borrow(2, 1, today - timedelta(days=20))   # overdue (6 days)
    s.loans.borrow(3, 4, today - timedelta(days=2))    # only copy of Classical Mechanics
    s.loans.borrow(4, 2, today - timedelta(days=5))
    s.reservations.reserve(1, 4)                       # Ahmed waits for Classical Mechanics
    s.reservations.reserve(2, 4)
    return True
