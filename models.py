"""
models.py  --  CORE CLASSES AND RULES  (Member A's part)

This file contains the "brain" of the library:
  * LibraryError   - a custom error used for every rule violation
  * hash_pin()     - turns a PIN into a hash (hashlib) so we never store raw PINs
  * Book           - a book object (plus Novel / Textbook / Magazine subclasses)
  * Member         - a library member or staff account
  * Library        - holds all books and members and enforces the rules

Nothing in this file prints or asks for input. It only holds data and rules,
so the UI (ui.py) and storage (storage.py) can be written by teammates
without touching this file.
"""

# hashlib is in the standard library; we use it to hash PINs (SHA-256).
import hashlib
# date    -> a calendar date (year, month, day) with no time of day.
# timedelta -> a length of time (e.g. 14 days) we can add to a date.
from datetime import date, timedelta

# ----------------------------------------------------------------------------
# CONSTANTS (settings in one place so they are easy to change)
# ----------------------------------------------------------------------------

# A member may have at most this many books out at the same time.
MAX_BOOKS_PER_MEMBER = 3

# A loan may be renewed this many times (the brief says "once").
MAX_RENEWALS = 1

# Format used to DISPLAY dates, e.g. "23 Nov 2026".
DATE_FORMAT = "%d %b %Y"

# A fixed "salt" mixed into every PIN before hashing. It makes our hashes
# different from a plain SHA-256 of the PIN (so common lookup tables fail).
# (Real systems use a different random salt per user; this keeps things simple.)
PIN_SALT = "library-system-v1:"


class LibraryError(Exception):
    """Raised whenever a library rule is broken (e.g. book already borrowed).

    The UI catches this error and prints its message, so the program never
    crashes because of a rule violation.
    """


def hash_pin(pin):
    """Return the SHA-256 hash (as a hex string) of a PIN.

    pin: the PIN as a string, e.g. "1234".
    """
    # Join the salt and the PIN into one string.
    text = PIN_SALT + str(pin)
    # .encode("utf-8") converts text to bytes (hashlib only accepts bytes).
    # sha256(...) creates the hash object; .hexdigest() gives it as text.
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------
# BOOK AND ITS SUBCLASSES  (inheritance + polymorphism)
# ----------------------------------------------------------------------------

class Book:
    """A single book in the catalogue.

    Subclasses (Novel, Textbook, Magazine) change only the three CLASS
    ATTRIBUTES below. Because the Library always asks the book itself
    (book.loan_days, book.fine_for(...)), the Library never needs to know
    which kind of book it is dealing with. That is polymorphism.
    """

    # Class attributes: shared by every Book unless a subclass overrides them.
    book_type = "Book"     # name shown in tables and saved in the JSON file
    loan_days = 14         # how many days a loan lasts
    daily_fine = 50.0      # fine per overdue day (in naira)

    def __init__(self, book_id, title, author):
        """Create a new, available book."""
        self.id = book_id              # unique ID such as "B001"
        self.title = title             # title text
        self.author = author           # author text
        self.is_available = True       # True = on the shelf, False = on loan
        self.borrowed_by = None        # member ID of the current borrower
        self.due_date = None           # date the current loan is due
        self.renewals = 0              # how many times this loan was renewed
        self.history = []              # list of {member_id, borrowed_on, returned_on}
        self.waiting_list = []         # queue of member IDs who reserved the book
        self.held_for = None           # member ID the book is being held for

    # ---- state changes ------------------------------------------------------

    def check_out(self, member_id, today):
        """Mark the book as borrowed by member_id on the date `today`."""
        self.is_available = False                              # no longer on the shelf
        self.borrowed_by = member_id                           # remember who has it
        # Due date = today + the loan period of THIS kind of book.
        self.due_date = today + timedelta(days=self.loan_days)
        self.renewals = 0                                      # fresh loan, no renewals yet
        self.held_for = None                                   # any hold has now been used
        # Add a history record; returned_on stays None until it comes back.
        # Dates are stored as ISO text ("2026-11-09") so JSON can save them.
        self.history.append({
            "member_id": member_id,
            "borrowed_on": today.isoformat(),
            "returned_on": None,
        })

    def check_in(self, today):
        """Mark the book as returned. Returns the member ID it is now held for
        (the first person in the waiting list), or None if nobody is waiting."""
        # Walk the history from newest to oldest to find the open record.
        for record in reversed(self.history):
            if record["returned_on"] is None:          # this loan is still open
                record["returned_on"] = today.isoformat()   # close it
                break                                  # stop after closing one
        self.is_available = True                       # back on the shelf
        self.borrowed_by = None                        # nobody has it now
        self.due_date = None                           # no due date on the shelf
        self.renewals = 0                              # reset the counter
        if self.waiting_list:                          # someone is waiting?
            # pop(0) removes and returns the FIRST name in the queue (fair: first come, first served).
            self.held_for = self.waiting_list.pop(0)
        return self.held_for

    # ---- calculations -------------------------------------------------------

    def days_overdue(self, today):
        """How many days past the due date the book is (0 if not overdue)."""
        if self.due_date is None or today <= self.due_date:
            return 0                                   # not on loan, or still on time
        return (today - self.due_date).days            # subtracting dates gives a timedelta

    def fine_for(self, today):
        """Fine owed today = overdue days x this book type's daily fine."""
        return round(self.days_overdue(today) * self.daily_fine, 2)

    def status_text(self):
        """Short text for the Status column of the book table."""
        if not self.is_available:
            return "Borrowed"
        if self.held_for:
            return "Held for " + self.held_for
        return "Available"

    # ---- saving ---------------------------------------------------------------

    def to_dict(self):
        """Convert the book to a plain dictionary that json can save."""
        return {
            "type": self.book_type,
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "is_available": self.is_available,
            "borrowed_by": self.borrowed_by,
            # Dates cannot go into JSON directly, so convert to text (or None).
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "renewals": self.renewals,
            # Copy each record so the saved data is independent of the live objects.
            "history": [dict(record) for record in self.history],
            "waiting_list": list(self.waiting_list),
            "held_for": self.held_for,
        }


class Novel(Book):
    """Fiction: 14-day loan, 50 naira/day fine."""
    book_type = "Novel"
    loan_days = 14
    daily_fine = 50.0


class Textbook(Book):
    """Textbook: short 7-day loan (high demand), bigger fine of 100 naira/day."""
    book_type = "Textbook"
    loan_days = 7
    daily_fine = 100.0


class Magazine(Book):
    """Magazine: 7-day loan, small fine of 25 naira/day."""
    book_type = "Magazine"
    loan_days = 7
    daily_fine = 25.0


# Lookup table: type name (as saved in JSON) -> class. Used when loading data
# and when staff choose which kind of book to add.
BOOK_TYPES = {
    "Book": Book,
    "Novel": Novel,
    "Textbook": Textbook,
    "Magazine": Magazine,
}


def book_from_dict(data):
    """Rebuild a Book (or subclass) from a dictionary made by Book.to_dict()."""
    cls = BOOK_TYPES[data["type"]]                       # pick the right class by name
    book = cls(data["id"], data["title"], data["author"])  # create the object
    book.is_available = bool(data["is_available"])       # restore each saved attribute
    book.borrowed_by = data["borrowed_by"]
    due = data["due_date"]
    # date.fromisoformat turns "2026-11-23" back into a date object.
    book.due_date = date.fromisoformat(due) if due else None
    book.renewals = int(data["renewals"])
    book.history = [dict(record) for record in data["history"]]
    book.waiting_list = list(data["waiting_list"])
    book.held_for = data["held_for"]
    return book


# ----------------------------------------------------------------------------
# MEMBER
# ----------------------------------------------------------------------------

class Member:
    """A person with an account. role is "member" or "staff"."""

    def __init__(self, member_id, name, pin_hash, role="member"):
        self.id = member_id            # e.g. "M001" (members) or "S001" (staff)
        self.name = name               # full name
        self.pin_hash = pin_hash       # hash of the PIN (never the PIN itself)
        self.role = role               # "member" or "staff"
        self.borrowed_books = []       # list of book IDs currently on loan

    def is_staff(self):
        """True if this account has staff powers."""
        return self.role == "staff"

    def to_dict(self):
        """Plain dictionary for saving."""
        return {
            "id": self.id,
            "name": self.name,
            "pin_hash": self.pin_hash,
            "role": self.role,
            "borrowed_books": list(self.borrowed_books),
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Member from a saved dictionary."""
        member = cls(data["id"], data["name"], data["pin_hash"], data["role"])
        member.borrowed_books = list(data["borrowed_books"])
        return member


# ----------------------------------------------------------------------------
# LIBRARY
# ----------------------------------------------------------------------------

class Library:
    """Holds every book and member and enforces all the borrowing rules.

    Every method that can fail raises LibraryError with a clear message.
    Methods that depend on today's date take an optional `today` argument so
    the self-tests can pretend time has passed.
    """

    def __init__(self):
        self.books = {}        # dictionary: book ID -> Book object
        self.members = {}      # dictionary: member ID -> Member object
        self.fines_log = []    # list of fines collected (for the reports)

    # ---- small helpers ------------------------------------------------------

    @staticmethod
    def _norm(item_id):
        """Normalise an ID: remove spaces and upper-case it ("m001 " -> "M001")."""
        return str(item_id).strip().upper()

    def _get_book(self, book_id):
        """Return the Book with this ID or raise LibraryError if it is unknown."""
        book = self.books.get(self._norm(book_id))      # dict.get returns None if missing
        if book is None:
            raise LibraryError(f"No book with ID '{self._norm(book_id)}' exists.")
        return book

    def _get_member(self, member_id):
        """Return the Member with this ID or raise LibraryError if unknown."""
        member = self.members.get(self._norm(member_id))
        if member is None:
            raise LibraryError(f"No member with ID '{self._norm(member_id)}' exists.")
        return member

    def find_book(self, book_id):
        """Public lookup (raises LibraryError if not found)."""
        return self._get_book(book_id)

    def find_member(self, member_id):
        """Public lookup (raises LibraryError if not found)."""
        return self._get_member(member_id)

    def list_books(self):
        """All books sorted by ID."""
        return [self.books[key] for key in sorted(self.books)]

    def loans_for(self, member_id):
        """The Book objects a member currently has out."""
        member = self._get_member(member_id)
        return [self.books[b_id] for b_id in member.borrowed_books if b_id in self.books]

    # ---- catalogue management (staff) -----------------------------------------

    def add_book(self, book):
        """Add a Book object. Duplicate IDs are rejected."""
        if book.id in self.books:
            raise LibraryError(f"A book with ID '{book.id}' already exists.")
        self.books[book.id] = book

    def remove_book(self, book_id):
        """Remove a book from the catalogue, only if it is not borrowed."""
        book = self._get_book(book_id)
        if not book.is_available:
            raise LibraryError(f"'{book.title}' is currently borrowed and cannot be removed.")
        del self.books[book.id]                          # delete the dictionary entry

    # ---- member management ------------------------------------------------------

    def register_member(self, member):
        """Add a Member object. Duplicate IDs are rejected."""
        if member.id in self.members:
            raise LibraryError(f"A member with ID '{member.id}' already exists.")
        self.members[member.id] = member

    def remove_member(self, member_id):
        """Remove an account. Not allowed while they hold books, or if they
        are the last staff account (the library would be locked out)."""
        member = self._get_member(member_id)
        if member.borrowed_books:
            raise LibraryError(f"{member.name} still has books out and cannot be removed.")
        if member.is_staff():
            # Count staff accounts; we must always keep at least one.
            staff_count = sum(1 for m in self.members.values() if m.is_staff())
            if staff_count <= 1:
                raise LibraryError("Cannot remove the last staff account.")
        # Clean up this member's reservations so no book waits for a deleted person.
        for book in self.books.values():
            if member.id in book.waiting_list:
                book.waiting_list.remove(member.id)
            if book.held_for == member.id:
                # Pass the hold to the next person waiting (or free the book).
                book.held_for = book.waiting_list.pop(0) if book.waiting_list else None
        del self.members[member.id]

    def authenticate(self, member_id, pin):
        """Check an ID and PIN. Returns the Member, or raises LibraryError.
        The message is deliberately vague so attackers cannot tell which part was wrong."""
        member = self.members.get(self._norm(member_id))
        if member is None or member.pin_hash != hash_pin(pin):
            raise LibraryError("Invalid ID or PIN.")
        return member

    # ---- borrowing rules ----------------------------------------------------------

    def borrow_book(self, member_id, book_id, today=None):
        """Let a member borrow a book. Returns the Book on success."""
        today = today or date.today()                    # default to the real date
        member = self._get_member(member_id)             # raises if unknown member
        book = self._get_book(book_id)                   # raises if unknown book
        if book.borrowed_by == member.id:
            raise LibraryError("You already have this book.")
        if not book.is_available:
            raise LibraryError(f"'{book.title}' is already borrowed.")
        # A book being held for someone else cannot be taken by anybody else.
        if book.held_for is not None and book.held_for != member.id:
            raise LibraryError(f"'{book.title}' is being held for another member who reserved it.")
        if len(member.borrowed_books) >= MAX_BOOKS_PER_MEMBER:
            raise LibraryError(
                f"{member.name} already has the maximum of {MAX_BOOKS_PER_MEMBER} books out.")
        book.check_out(member.id, today)                 # update the book
        member.borrowed_books.append(book.id)            # update the member
        return book

    def return_book(self, member_id, book_id, today=None):
        """Return a book. Gives back a dictionary describing what happened."""
        today = today or date.today()
        member = self._get_member(member_id)
        book = self._get_book(book_id)
        # Only the borrower may return it.
        if book.id not in member.borrowed_books:
            raise LibraryError(f"{member.name} has not borrowed '{book.title}'.")
        days_late = book.days_overdue(today)             # work these out BEFORE check_in clears the due date
        fine = book.fine_for(today)
        next_member = book.check_in(today)               # book goes back on the shelf
        member.borrowed_books.remove(book.id)            # member no longer has it
        if fine > 0:                                     # record fines for the reports
            self.fines_log.append({
                "member_id": member.id,
                "book_id": book.id,
                "days_overdue": days_late,
                "amount": fine,
                "date": today.isoformat(),
            })
        return {"fine": fine, "days_overdue": days_late, "next_member": next_member}

    def renew_book(self, member_id, book_id, today=None):
        """Renew a loan (once). Returns the new due date."""
        today = today or date.today()
        member = self._get_member(member_id)
        book = self._get_book(book_id)
        if book.id not in member.borrowed_books:
            raise LibraryError(f"{member.name} has not borrowed '{book.title}'.")
        if book.renewals >= MAX_RENEWALS:
            raise LibraryError("This loan has already been renewed once.")
        if book.days_overdue(today) > 0:
            raise LibraryError("Overdue books cannot be renewed. Please return it.")
        if book.waiting_list:
            raise LibraryError("Someone has reserved this book, so it cannot be renewed.")
        book.due_date = today + timedelta(days=book.loan_days)  # fresh loan period from today
        book.renewals += 1
        return book.due_date

    def reserve_book(self, member_id, book_id):
        """Join a book's waiting list. Returns the member's position in the queue."""
        member = self._get_member(member_id)
        book = self._get_book(book_id)
        if book.borrowed_by == member.id:
            raise LibraryError("You already have this book.")
        if book.is_available and book.held_for is None:
            raise LibraryError("This book is available now, so just borrow it.")
        if book.held_for == member.id:
            raise LibraryError("This book is already being held for you. Borrow it now.")
        if member.id in book.waiting_list:
            raise LibraryError("You are already on the waiting list for this book.")
        book.waiting_list.append(member.id)              # join the back of the queue
        return len(book.waiting_list)                    # position = queue length

    # ---- searching and reports data -----------------------------------------------

    def search_books(self, term):
        """Case-insensitive partial match on title OR author."""
        needle = term.strip().lower()                    # lower-case so case does not matter
        return [b for b in self.list_books()
                if needle in b.title.lower() or needle in b.author.lower()]

    def overdue_loans(self, today=None):
        """List of (book, member, days_overdue, fine), most overdue first."""
        today = today or date.today()
        rows = []
        for book in self.list_books():
            days = book.days_overdue(today)
            if days > 0:                                 # only books past due
                member = self.members.get(book.borrowed_by)
                rows.append((book, member, days, book.fine_for(today)))
        # key=lambda ... sorts by the 3rd item (days); reverse=True = biggest first.
        rows.sort(key=lambda row: row[2], reverse=True)
        return rows

    # ---- saving ---------------------------------------------------------------------

    def to_dict(self):
        """Whole library as a dictionary for saving."""
        return {
            "books": [b.to_dict() for b in self.list_books()],
            "members": [m.to_dict() for m in self.members.values()],
            "fines_log": [dict(f) for f in self.fines_log],
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a Library from a saved dictionary (may raise KeyError/
        TypeError/ValueError if the data is damaged; storage.py handles that)."""
        library = cls()
        for book_data in data["books"]:
            book = book_from_dict(book_data)
            library.books[book.id] = book
        for member_data in data["members"]:
            member = Member.from_dict(member_data)
            library.members[member.id] = member
        library.fines_log = [dict(f) for f in data["fines_log"]]
        return library
