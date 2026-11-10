"""
tests.py  --  SELF-TESTS  (Member C's part)

run_tests() is a single function containing 12 assert-based checks of the
core rules: borrow, return, limits, fines, reservations, renewals, removal,
saving, PIN hashing, duplicates and reports.

Run with:   python main.py --test      (or)      python tests.py
An `assert` does nothing when its condition is True and stops the program
with an AssertionError (showing our message) when it is False.
"""

import json
from datetime import date, timedelta

import reports
from models import (Library, Member, Novel, Textbook, Magazine, LibraryError,
                    hash_pin, MAX_BOOKS_PER_MEMBER)


def run_tests():
    """Run every self-test. Prints a summary if all pass."""

    # A fixed "today" so results never depend on the real date.
    today = date(2026, 11, 9)
    passed = 0                                   # counts finished checks

    def make_library():
        """Build a small fresh library used by the tests."""
        lib = Library()
        lib.add_book(Novel("B001", "Half of a Yellow Sun", "C. Adichie"))
        lib.add_book(Novel("B002", "Purple Hibiscus", "C. Adichie"))
        lib.add_book(Novel("B003", "Things Fall Apart", "C. Achebe"))
        lib.add_book(Textbook("B004", "Python Basics", "E. Matthes"))
        lib.add_book(Magazine("B005", "Tech Monthly", "Various"))
        lib.register_member(Member("M001", "Ada Obi", hash_pin("1111"), "member"))
        lib.register_member(Member("M002", "Tunde Bello", hash_pin("2222"), "member"))
        lib.register_member(Member("S001", "Librarian", hash_pin("1234"), "staff"))
        return lib

    def raises(function, *args, **kwargs):
        """True if calling function(...) raises LibraryError (i.e. a rule blocked it)."""
        try:
            function(*args, **kwargs)
        except LibraryError:
            return True
        return False

    # ---- TEST 1: borrowing marks the book out and sets a 14-day due date -----
    lib = make_library()
    book = lib.borrow_book("M001", "B003", today)
    assert book.is_available is False, "book should be unavailable after borrowing"
    assert book.due_date == today + timedelta(days=14), "novel due date should be 14 days away"
    assert lib.find_member("M001").borrowed_books == ["B003"], "member should list the book"
    passed += 1

    # ---- TEST 2: a book that is already out cannot be borrowed again ----------
    assert raises(lib.borrow_book, "M002", "B003", today), "double borrow must be blocked"
    passed += 1

    # ---- TEST 3: unknown book / member IDs are rejected ----------------------
    assert raises(lib.borrow_book, "M001", "B999", today), "unknown book must be rejected"
    assert raises(lib.borrow_book, "M999", "B001", today), "unknown member must be rejected"
    passed += 1

    # ---- TEST 4: a member can hold at most 3 books ---------------------------
    lib = make_library()
    for book_id in ["B001", "B002", "B003"]:
        lib.borrow_book("M001", book_id, today)
    assert len(lib.find_member("M001").borrowed_books) == MAX_BOOKS_PER_MEMBER
    assert raises(lib.borrow_book, "M001", "B004", today), "4th book must be blocked"
    passed += 1

    # ---- TEST 5: only the borrower can return a book -------------------------
    assert raises(lib.return_book, "M002", "B001", today), "non-borrower cannot return"
    lib.return_book("M001", "B001", today)
    assert lib.find_book("B001").is_available is True, "returned book is available again"
    assert "B001" not in lib.find_member("M001").borrowed_books
    passed += 1

    # ---- TEST 6: fines, and polymorphism (different types, different rules) --
    lib = make_library()
    lib.borrow_book("M001", "B001", today)       # Novel: 14 days, 50/day
    lib.borrow_book("M001", "B004", today)       # Textbook: 7 days, 100/day
    assert lib.find_book("B004").due_date == today + timedelta(days=7), "textbook loan is 7 days"
    late = today + timedelta(days=14 + 5)        # 5 days after the novel's due date
    assert lib.find_book("B001").fine_for(late) == 250.0, "5 days x 50 = 250"
    assert lib.find_book("B004").fine_for(late) == 1200.0, "12 days x 100 = 1200"
    result = lib.return_book("M001", "B001", late)
    assert result["fine"] == 250.0 and result["days_overdue"] == 5
    assert reports.total_fines_collected(lib) == 250.0, "fine must be logged"
    passed += 1

    # ---- TEST 7: reservation queue ------------------------------------------
    lib = make_library()
    lib.borrow_book("M001", "B002", today)
    assert lib.reserve_book("M002", "B002") == 1, "first in queue gets position 1"
    assert raises(lib.reserve_book, "M002", "B002"), "cannot join the queue twice"
    result = lib.return_book("M001", "B002", today)
    assert result["next_member"] == "M002", "returned book is offered to the first in queue"
    assert lib.find_book("B002").held_for == "M002"
    assert raises(lib.borrow_book, "M001", "B002", today), "others cannot take a held book"
    lib.borrow_book("M002", "B002", today)       # the reserving member can
    assert lib.find_book("B002").held_for is None, "hold is cleared once borrowed"
    passed += 1

    # ---- TEST 8: renewals (once only; not when someone is waiting) ----------
    lib = make_library()
    lib.borrow_book("M001", "B001", today)
    new_due = lib.renew_book("M001", "B001", today + timedelta(days=3))
    assert new_due == today + timedelta(days=3 + 14), "renewal restarts the loan period"
    assert raises(lib.renew_book, "M001", "B001", today), "second renewal must be blocked"
    lib.borrow_book("M001", "B002", today)
    lib.reserve_book("M002", "B002")
    assert raises(lib.renew_book, "M001", "B002", today), "reserved book cannot be renewed"
    passed += 1

    # ---- TEST 9: a book can only be removed when it is not borrowed ---------
    lib = make_library()
    lib.borrow_book("M001", "B001", today)
    assert raises(lib.remove_book, "B001"), "borrowed book cannot be removed"
    lib.remove_book("B005")
    assert "B005" not in lib.books, "available book can be removed"
    passed += 1

    # ---- TEST 10: save/load round trip through real JSON text ---------------
    lib = make_library()
    lib.borrow_book("M001", "B004", today)
    lib.reserve_book("M002", "B004")
    text = json.dumps(lib.to_dict())             # object -> JSON text
    copy = Library.from_dict(json.loads(text))   # JSON text -> new object
    assert copy.find_book("B004").due_date == lib.find_book("B004").due_date
    assert copy.find_book("B004").waiting_list == ["M002"]
    assert type(copy.find_book("B004")) is Textbook, "subclass type must survive saving"
    assert copy.find_book("B004").history == lib.find_book("B004").history
    passed += 1

    # ---- TEST 11: PINs are hashed and logins work ---------------------------
    lib = make_library()
    assert lib.find_member("M001").pin_hash != "1111", "PIN must not be stored in plain text"
    assert lib.authenticate("m001", "1111").id == "M001", "correct PIN logs in (ID is case-insensitive)"
    assert raises(lib.authenticate, "M001", "9999"), "wrong PIN rejected"
    passed += 1

    # ---- TEST 12: duplicate IDs, search and reports --------------------------
    lib = make_library()
    assert raises(lib.add_book, Novel("B001", "Copy", "Someone")), "duplicate book ID rejected"
    assert raises(lib.register_member, Member("M001", "Dup", "x")), "duplicate member ID rejected"
    assert [b.id for b in lib.search_books("ADICHIE")] == ["B001", "B002"], "case-insensitive author search"
    assert [b.id for b in lib.search_books("fall")] == ["B003"], "partial title search"
    lib.borrow_book("M001", "B001", today)
    lib.return_book("M001", "B001", today)
    lib.borrow_book("M002", "B001", today)
    lib.borrow_book("M002", "B002", today)
    top = reports.most_borrowed_books(lib)
    assert top[0][1].id == "B001" and top[0][0] == 2, "B001 was borrowed twice"
    assert reports.most_active_members(lib)[0][1] == "M002", "M002 has the most loans"
    overdue = reports.overdue_report(lib, today + timedelta(days=20))
    assert len(overdue) == 2 and overdue[0][2] >= overdue[1][2], "overdue list sorted, largest first"
    passed += 1

    print(f"All {passed} self-test groups passed.")


if __name__ == "__main__":
    run_tests()
