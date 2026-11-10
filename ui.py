"""
ui.py  --  DISPLAY AND INPUT  (Member B's part)

Everything the user sees or types lives here:
  * input helpers that VALIDATE and re-prompt instead of crashing
  * table printing
  * login screen, member menu and staff menu
  * one small "do_..." function per menu action

The rules themselves live in models.py. Here we only ask for input, call a
Library method, and print the result (or the LibraryError message).
"""

import re                       # regular expressions, to check the shape of IDs and PINs
import getpass                  # lets us type a PIN without it showing on screen
from datetime import date

import reports
from models import (Member, Library, LibraryError, BOOK_TYPES, hash_pin,
                    DATE_FORMAT, MAX_BOOKS_PER_MEMBER)
from storage import save_library


# ----------------------------------------------------------------------------
# SMALL FORMATTING HELPERS
# ----------------------------------------------------------------------------

def money(amount):
    """Format a number as money, e.g. 250 -> 'NGN 250.00'."""
    return f"NGN {amount:,.2f}"          # :, adds thousands commas, .2f = 2 decimals


def fit(text, width):
    """Shorten text to `width` characters, adding '...' if it was cut."""
    return text if len(text) <= width else text[:width - 3] + "..."


def show_date(day):
    """Format a date like '23 Nov 2026'."""
    return day.strftime(DATE_FORMAT)


def persist(library):
    """Save the library to disk; warn (don't crash) if saving fails."""
    try:
        save_library(library)
    except OSError as error:
        print(f"  WARNING: could not save data ({error}).")


# ----------------------------------------------------------------------------
# VALIDATED INPUT HELPERS  (every one loops until the answer is valid)
# ----------------------------------------------------------------------------

def ask_text(label):
    """Ask for text that is not empty."""
    while True:                                          # repeat until we return
        value = input(f"{label}: ").strip()              # strip() removes spaces at both ends
        if value:                                        # non-empty strings count as True
            return value
        print("  Input cannot be empty. Please try again.")


def ask_id(label, prefix):
    """Ask for an ID like B001 / M001 / S001 (prefix letter + at least 3 digits).
    Returns it upper-cased, e.g. 'b003' -> 'B003'."""
    # ^ and $ = whole text must match; \d{3,} = three or more digits.
    pattern = re.compile(rf"^{prefix}\d{{3,}}$")
    while True:
        value = input(f"{label}: ").strip().upper()
        if pattern.match(value):
            return value
        print(f"  Invalid ID. Use the letter {prefix} followed by at least 3 digits (e.g. {prefix}001).")


def ask_new_id(label, prefix, exists):
    """Ask for an ID that is valid AND not already used.
    `exists` is a function that returns True if the ID is taken."""
    while True:
        value = ask_id(label, prefix)
        if exists(value):                                # duplicate -> reject and ask again
            print(f"  '{value}' is already in use. Choose a different ID.")
        else:
            return value


def ask_pin(label="PIN"):
    """Ask for a 4-digit PIN (hidden while typing when possible)."""
    while True:
        try:
            value = getpass.getpass(f"{label} (4 digits): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise                                        # let main handle quitting
        except Exception:
            # Some consoles (e.g. IDLE) cannot hide input; fall back to normal input.
            value = input(f"{label} (4 digits): ").strip()
        if re.fullmatch(r"\d{4}", value):                # exactly four digits
            return value
        print("  The PIN must be exactly 4 digits.")


def ask_new_pin():
    """Ask for a new PIN twice so typing mistakes are caught."""
    while True:
        first = ask_pin("Choose a PIN")
        second = ask_pin("Confirm PIN")
        if first == second:
            return first
        print("  The PINs did not match. Try again.")


def ask_choice(label, valid):
    """Ask until the answer is one of the strings in `valid`."""
    while True:
        value = input(f"{label}: ").strip()
        if value in valid:
            return value
        print(f"  Please enter one of: {', '.join(valid)}")


# ----------------------------------------------------------------------------
# TABLE PRINTING
# ----------------------------------------------------------------------------

def print_books(books):
    """Print a list of Book objects as an aligned table."""
    if not books:
        print("  No books to show.")
        return
    # Header line. :<6 means "left-align in 6 characters".
    header = f"{'ID':<6}{'Title':<30}{'Author':<26}{'Type':<10}{'Status':<16}{'Queue'}"
    print(header)
    print("-" * len(header))                             # underline as wide as the header
    for book in books:
        print(f"{book.id:<6}{fit(book.title, 28):<30}{fit(book.author, 24):<26}"
              f"{book.book_type:<10}{book.status_text():<16}{len(book.waiting_list)}")


def print_loans(library, books, today):
    """Print the loans of one member (due dates, overdue days, fines)."""
    if not books:
        print("  No books currently borrowed.")
        return
    header = f"{'ID':<6}{'Title':<30}{'Due date':<14}{'Notes'}"
    print(header)
    print("-" * len(header))
    for book in books:
        days = book.days_overdue(today)
        if days > 0:
            note = f"OVERDUE {days} day(s), fine so far {money(book.fine_for(today))}"
        else:
            note = f"Renewals used: {book.renewals}"
        print(f"{book.id:<6}{fit(book.title, 28):<30}{show_date(book.due_date):<14}{note}")


# ----------------------------------------------------------------------------
# ACTIONS (each one is a menu option)
# Every action takes (library, user): `user` is the logged-in Member.
# ----------------------------------------------------------------------------

def target_member_id(user):
    """Members act as themselves; staff are asked which member they act for."""
    if user.is_staff():
        return ask_id("Member ID", "M")
    return user.id


def do_list_books(library, user):
    """Show every book and whether it is available."""
    print_books(library.list_books())


def do_search(library, user):
    """Case-insensitive, partial-match search by title or author."""
    term = ask_text("Search for (part of a title or author)")
    results = library.search_books(term)
    print(f"\n  {len(results)} match(es):")
    print_books(results)


def do_borrow(library, user):
    """Borrow a book and print a receipt like the one in the brief."""
    member_id = target_member_id(user)
    book_id = ask_id("Book ID", "B")
    try:
        book = library.borrow_book(member_id, book_id)
        member = library.find_member(member_id)
    except LibraryError as error:
        print(f"  Cannot borrow: {error}")
        return
    persist(library)
    print(f'\nBorrowed: "{book.title}" by {book.author}')
    print(f"Member: {member.name} ({member.id})    "
          f"Books out: {len(member.borrowed_books)} of {MAX_BOOKS_PER_MEMBER}")
    print(f"Due date: {show_date(book.due_date)}\n")
    print_books(library.list_books())


def do_return(library, user):
    """Return a book; show any fine and tell the library who is next in the queue."""
    member_id = target_member_id(user)
    book_id = ask_id("Book ID", "B")
    try:
        result = library.return_book(member_id, book_id)
        book = library.find_book(book_id)
    except LibraryError as error:
        print(f"  Cannot return: {error}")
        return
    persist(library)
    print(f'\nReturned: "{book.title}"')
    if result["fine"] > 0:
        print(f"  It was {result['days_overdue']} day(s) late. Fine collected: {money(result['fine'])}")
    if result["next_member"]:
        print(f"  Offered first to member {result['next_member']} (reservation).")


def do_renew(library, user):
    """Renew a loan once."""
    member_id = target_member_id(user)
    book_id = ask_id("Book ID", "B")
    try:
        new_due = library.renew_book(member_id, book_id)
    except LibraryError as error:
        print(f"  Cannot renew: {error}")
        return
    persist(library)
    print(f"  Renewed. New due date: {show_date(new_due)}")


def do_reserve(library, user):
    """Join the waiting list for a book that is out."""
    member_id = target_member_id(user)
    book_id = ask_id("Book ID", "B")
    try:
        position = library.reserve_book(member_id, book_id)
    except LibraryError as error:
        print(f"  Cannot reserve: {error}")
        return
    persist(library)
    print(f"  Reserved. You are number {position} in the queue.")


def do_my_loans(library, user):
    """Show the books a member currently has."""
    member_id = target_member_id(user)
    try:
        books = library.loans_for(member_id)
    except LibraryError as error:
        print(f"  {error}")
        return
    print_loans(library, books, date.today())


def do_add_book(library, user):
    """Staff: add a new book of a chosen type."""
    book_id = ask_new_id("New book ID", "B", lambda i: i in library.books)
    title = ask_text("Title")
    author = ask_text("Author")
    types = list(BOOK_TYPES)                              # ["Book", "Novel", "Textbook", "Magazine"]
    for number, name in enumerate(types, start=1):        # show a numbered list
        cls = BOOK_TYPES[name]
        print(f"  {number}. {name} ({cls.loan_days}-day loan, {money(cls.daily_fine)}/day fine)")
    pick = ask_choice("Type number", [str(n) for n in range(1, len(types) + 1)])
    cls = BOOK_TYPES[types[int(pick) - 1]]                # look up the chosen class
    try:
        library.add_book(cls(book_id, title, author))     # create the object and add it
    except LibraryError as error:
        print(f"  {error}")
        return
    persist(library)
    print(f"  Added {book_id}: {title}")


def do_remove_book(library, user):
    """Staff: remove a book (only if not borrowed)."""
    book_id = ask_id("Book ID to remove", "B")
    try:
        library.remove_book(book_id)
    except LibraryError as error:
        print(f"  Cannot remove: {error}")
        return
    persist(library)
    print(f"  Removed {book_id}.")


def register_account(library, role):
    """Create a new account of the given role ('member' or 'staff')."""
    prefix = "S" if role == "staff" else "M"
    member_id = ask_new_id("New ID", prefix, lambda i: i in library.members)
    name = ask_text("Full name")
    pin = ask_new_pin()
    library.register_member(Member(member_id, name, hash_pin(pin), role))
    persist(library)
    print(f"  Account created: {name} ({member_id})")


def do_register_member(library, user):
    """Staff: register a new member."""
    register_account(library, "member")


def do_register_staff(library, user):
    """Staff: create another staff account."""
    register_account(library, "staff")


def do_remove_member(library, user):
    """Staff: remove an account (not themselves)."""
    # "[MS]" is a regex character class: the ID may start with M (member) or S (staff).
    member_id = ask_id("ID of account to remove", "[MS]")
    if member_id == user.id:
        print("  You cannot remove the account you are logged in with.")
        return
    try:
        library.remove_member(member_id)
    except LibraryError as error:
        print(f"  Cannot remove: {error}")
        return
    persist(library)
    print(f"  Removed {member_id}.")


def do_list_members(library, user):
    """Staff: list all accounts."""
    print(f"{'ID':<6}{'Name':<24}{'Role':<9}{'Books out'}")
    print("-" * 50)
    for member in sorted(library.members.values(), key=lambda m: m.id):
        print(f"{member.id:<6}{fit(member.name, 22):<24}{member.role:<9}{len(member.borrowed_books)}")


def do_overdue(library, user):
    """Staff: overdue list, most overdue first."""
    rows = reports.overdue_report(library, date.today())
    if not rows:
        print("  No overdue books.")
        return
    print(f"{'ID':<6}{'Title':<28}{'Member':<20}{'Days':<6}{'Fine'}")
    print("-" * 70)
    for book, member, days, fine in rows:
        who = member.name if member else "(unknown)"
        print(f"{book.id:<6}{fit(book.title, 26):<28}{fit(who, 18):<20}{days:<6}{money(fine)}")


def do_reports(library, user):
    """Staff: all the statistics in one screen."""
    print("\n=== Most borrowed books ===")
    rows = reports.most_borrowed_books(library)
    if not rows:
        print("  No borrowing yet.")
    for count, book in rows:
        print(f"  {count} x  {book.id}  {book.title}")

    print("\n=== Most active members ===")
    rows = reports.most_active_members(library)
    if not rows:
        print("  No borrowing yet.")
    for count, member_id, name in rows:
        print(f"  {count} loan(s)  {member_id}  {name}")

    print("\n=== Overdue (most overdue first) ===")
    do_overdue(library, user)

    print(f"\n=== Total fines collected: {money(reports.total_fines_collected(library))} ===")


def do_book_history(library, user):
    """Staff: show who borrowed one book and when it came back."""
    book_id = ask_id("Book ID", "B")
    try:
        book = library.find_book(book_id)
    except LibraryError as error:
        print(f"  {error}")
        return
    print(f'\nHistory of "{book.title}":')
    if not book.history:
        print("  Never borrowed.")
    for record in book.history:
        returned = record["returned_on"] or "not returned yet"
        print(f"  {record['member_id']}  borrowed {record['borrowed_on']}  returned {returned}")


# ----------------------------------------------------------------------------
# MENUS
# Each menu is a dictionary: choice -> (label, function).
# The loop below prints it and calls the right function, so adding an option
# means adding one line here.
# ----------------------------------------------------------------------------

MEMBER_MENU = {
    "1": ("List all books", do_list_books),
    "2": ("Borrow a book", do_borrow),
    "3": ("Return a book", do_return),
    "4": ("Renew a loan", do_renew),
    "5": ("Reserve a book that is out", do_reserve),
    "6": ("Search books", do_search),
    "7": ("My loans", do_my_loans),
}

STAFF_MENU = {
    "1": ("List all books", do_list_books),
    "2": ("Borrow a book for a member", do_borrow),
    "3": ("Return a book for a member", do_return),
    "4": ("Renew a loan for a member", do_renew),
    "5": ("Reserve a book for a member", do_reserve),
    "6": ("Search books", do_search),
    "7": ("Member's loans", do_my_loans),
    "8": ("Add a book", do_add_book),
    "9": ("Remove a book", do_remove_book),
    "10": ("Register a member", do_register_member),
    "11": ("Remove an account", do_remove_member),
    "12": ("List accounts", do_list_members),
    "13": ("Overdue books", do_overdue),
    "14": ("Reports", do_reports),
    "15": ("Book borrowing history", do_book_history),
    "16": ("Create a staff account", do_register_staff),
}


def run_menu(library, user):
    """Show the menu for this user's role until they choose to log out."""
    menu = STAFF_MENU if user.is_staff() else MEMBER_MENU
    while True:
        print(f"\n--- {'STAFF' if user.is_staff() else 'MEMBER'} MENU  (logged in: {user.name}) ---")
        for key, (label, _function) in menu.items():       # _function is unused here
            print(f"  {key:>2}. {label}")
        print("   0. Log out")
        choice = ask_choice("Menu choice", ["0"] + list(menu))
        if choice == "0":
            return                                         # back to the login screen
        print()
        menu[choice][1](library, user)                     # call the chosen function


# ----------------------------------------------------------------------------
# LOGIN SCREEN AND MAIN LOOP
# ----------------------------------------------------------------------------

def login(library):
    """Ask for ID and PIN (3 tries). Returns a Member or None."""
    for _attempt in range(3):
        member_id = ask_id("ID (M... for members, S... for staff)", "[MS]")
        pin = ask_pin()
        try:
            return library.authenticate(member_id, pin)
        except LibraryError as error:
            print(f"  {error}")
    print("  Too many failed attempts.")
    return None


def run(library):
    """The outermost loop: login screen -> menu -> login screen ... until Exit."""
    print("=" * 50)
    print("   LIBRARY MANAGEMENT SYSTEM")
    print("=" * 50)
    while True:
        print("\n1. Log in\n2. Join as a new member\n0. Exit")
        choice = ask_choice("Choice", ["0", "1", "2"])
        if choice == "0":
            print("Goodbye!")
            return
        if choice == "2":
            register_account(library, "member")
            continue                                       # back to the login screen
        user = login(library)
        if user is not None:
            run_menu(library, user)
