import os, tempfile, unittest
from datetime import date, timedelta

from library import LibrarySystem
from library.exceptions import BusinessRuleError, ValidationError

D = date(2026, 1, 10)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.s = LibrarySystem(":memory:")
        self.book = self.s.books.add_book("12345", "Intro Python", "Smith", "CS", 5)
        self.stu = [self.s.members.register("S", str(i), f"s{i}@u.tn", "student") for i in range(5)]
        self.ins = self.s.members.register("Dr", "I", "i@u.tn", "instructor")

    def test_available_copies(self):
        for m in self.stu[:3]:
            self.s.loans.borrow(m.member_id, self.book.book_id, D)
        self.assertEqual(self.s.books.get_book(self.book.book_id).available_copies, 2)

    def test_limits_and_due_dates(self):
        books = [self.s.books.add_book(f"B000{i}", f"T{i}", "A", "CS", 2) for i in range(6)]
        loans = [self.s.loans.borrow(self.stu[0].member_id, b.book_id, D) for b in books[:3]]
        self.assertEqual(loans[0].due_date, (D + timedelta(days=14)).isoformat())
        with self.assertRaises(BusinessRuleError):
            self.s.loans.borrow(self.stu[0].member_id, books[3].book_id, D)
        for b in books[:5]:
            l = self.s.loans.borrow(self.ins.member_id, b.book_id, D)
        self.assertEqual(l.due_date, (D + timedelta(days=21)).isoformat())
        with self.assertRaises(BusinessRuleError):
            self.s.loans.borrow(self.ins.member_id, books[5].book_id, D)

    def test_partial_borrow_many(self):
        full = self.s.books.add_book("FULL1", "Full", "A", "CS", 1)
        self.s.loans.borrow(self.stu[1].member_id, full.book_id, D)
        res = self.s.loans.borrow_many(self.stu[0].member_id, [self.book.book_id, full.book_id], D)
        self.assertIsNotNone(res[0][1]); self.assertIsNone(res[1][1]); self.assertIn("reserve", res[1][2])

    def test_late_return_penalty(self):
        self.s.loans.borrow(self.stu[0].member_id, self.book.book_id, D)
        r = self.s.loans.return_book(self.stu[0].member_id, self.book.book_id, D + timedelta(days=19))
        self.assertEqual(r.days_late, 5); self.assertEqual(r.penalty.amount, 5)

    def test_return_without_loan(self):
        with self.assertRaises(BusinessRuleError):
            self.s.loans.return_book(self.stu[0].member_id, self.book.book_id, D)

    def test_reservation_order_and_hold(self):
        one = self.s.books.add_book("ONE11", "One", "A", "CS", 1)
        self.s.loans.borrow(self.stu[0].member_id, one.book_id, D)
        for m in self.stu[1:4]:
            self.s.reservations.reserve(m.member_id, one.book_id)
        r = self.s.loans.return_book(self.stu[0].member_id, one.book_id, D + timedelta(days=1))
        self.assertEqual(r.promoted[0].member_id, self.stu[1].member_id)
        with self.assertRaises(BusinessRuleError):  # copy is held for stu[1]
            self.s.loans.borrow(self.stu[2].member_id, one.book_id, D)
        self.s.loans.borrow(self.stu[1].member_id, one.book_id, D)

    def test_reserve_available_rejected(self):
        with self.assertRaises(BusinessRuleError):
            self.s.reservations.reserve(self.stu[0].member_id, self.book.book_id)

    def test_validation(self):
        with self.assertRaises(ValidationError):
            self.s.members.register("A", "B", "S0@u.tn", "student")      # duplicate email
        with self.assertRaises(ValidationError):
            self.s.members.register("A", "B", "bad-email", "student")
        with self.assertRaises(ValidationError):
            self.s.books.add_book("99999", "X", "Y", "Z", 0)

    def test_payments_and_stats(self):
        self.s.loans.borrow(self.stu[0].member_id, self.book.book_id, D)
        r = self.s.loans.return_book(self.stu[0].member_id, self.book.book_id, D + timedelta(days=18))
        self.assertEqual(r.penalty.amount, 4)
        with self.assertRaises(BusinessRuleError):
            self.s.penalties.pay(r.penalty.penalty_id, 10)
        self.s.penalties.pay(r.penalty.penalty_id, 1.5)
        self.assertEqual(self.s.stats.members_with_penalties()[0]["amount_due"], 2.5)
        self.assertEqual(self.s.stats.total_penalties_collected(), 1.5)
        self.assertEqual(self.s.stats.most_borrowed()[0]["times_borrowed"], 1)

    def test_overdue_stat(self):
        self.s.loans.borrow(self.stu[0].member_id, self.book.book_id, D)
        self.assertEqual(self.s.stats.overdue(D + timedelta(days=16))[0]["days_late"], 2)

    def test_persistence(self):
        path = os.path.join(tempfile.mkdtemp(), "lib.db")
        a = LibrarySystem(path); a.books.add_book("PERS1", "Persist", "A", "CS", 2); a.close()
        b = LibrarySystem(path)
        self.assertEqual(b.books.search("Persist")[0].total_copies, 2); b.close()


if __name__ == "__main__":
    unittest.main()
