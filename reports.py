"""
reports.py  --  STATISTICS AND REPORTS  (Member C's part)

These functions only CALCULATE results and return them as lists/numbers.
ui.py is responsible for printing them nicely. Keeping calculation and
display apart means each can be changed without breaking the other.
"""

from collections import Counter   # Counter counts how many times each item appears


def most_borrowed_books(library, top=5):
    """Return [(times_borrowed, Book), ...] with the most borrowed first.

    Every borrow adds one record to book.history, so the length of the
    history IS the number of times the book was borrowed.
    """
    rows = [(len(book.history), book) for book in library.books.values() if book.history]
    # Sort by count (biggest first); ties are broken alphabetically by title.
    rows.sort(key=lambda row: (-row[0], row[1].title))
    return rows[:top]                                     # keep only the top N


def most_active_members(library, top=5):
    """Return [(loans_count, member_id, name), ...] most active first."""
    counter = Counter()                                   # member ID -> number of loans
    for book in library.books.values():                   # look at every book...
        for record in book.history:                       # ...and every loan record
            counter[record["member_id"]] += 1             # count one loan for that member
    rows = []
    for member_id, count in counter.items():
        member = library.members.get(member_id)           # may be None if the member was removed
        name = member.name if member else "(removed member)"
        rows.append((count, member_id, name))
    rows.sort(key=lambda row: (-row[0], row[1]))          # most loans first, then by ID
    return rows[:top]


def overdue_report(library, today=None):
    """Overdue loans sorted by days overdue (largest first).
    The sorting itself is done by Library.overdue_loans."""
    return library.overdue_loans(today)


def total_fines_collected(library):
    """Add up every fine recorded when overdue books were returned."""
    return round(sum(entry["amount"] for entry in library.fines_log), 2)
