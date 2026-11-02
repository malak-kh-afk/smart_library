"""Smart Library Management System - facade that wires all services together."""
from .database import Database
from .services import (BookService, LoanService, MemberService, PenaltyService,
                       ReservationService, StatisticsService)


class LibrarySystem:
    def __init__(self, db_path="data/library.db"):
        self.db = Database(db_path)
        self.books = BookService(self.db)
        self.members = MemberService(self.db)
        self.reservations = ReservationService(self.db, self.books, self.members)
        self.penalties = PenaltyService(self.db)
        self.loans = LoanService(self.db, self.books, self.members, self.reservations, self.penalties)
        self.stats = StatisticsService(self.db, self.loans, self.books)
        self.books.on_stock_increase = self.reservations.promote_waiting

    def close(self):
        self.db.close()
