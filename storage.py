"""
storage.py  --  SAVING AND LOADING  (Member C's part)

Responsibilities:
  * seed_library()  - the starting data (5+ books, a staff account, sample members)
  * save_library()  - write the whole library to a JSON file safely
  * load_library()  - read it back at startup, coping with a missing, empty
                      or corrupted file WITHOUT crashing
"""

import json   # converts Python dictionaries/lists to text and back
import os     # file-system helpers (exists, replace)

from models import (Library, Member, Novel, Textbook, Magazine, hash_pin)

# The file where all data is saved (created next to where you run the program).
DATA_FILE = "library_data.json"


def seed_library():
    """Build a brand-new library with starter books and accounts."""
    library = Library()                                   # empty library

    # Preload 6 books (requirement: at least 5). Different subclasses show polymorphism.
    starter_books = [
        Novel("B001", "Half of a Yellow Sun", "Chimamanda Ngozi Adichie"),
        Novel("B002", "Purple Hibiscus", "Chimamanda Ngozi Adichie"),
        Novel("B003", "Things Fall Apart", "Chinua Achebe"),
        Textbook("B004", "Python Crash Course", "Eric Matthes"),
        Textbook("B005", "Introduction to Algorithms", "Thomas H. Cormen"),
        Magazine("B006", "Tech Monthly - November 2026", "Various Authors"),
    ]
    for book in starter_books:                            # add each one to the library
        library.add_book(book)

    # One staff account so someone can log in and manage the library.
    # Default login -> ID: S001   PIN: 1234
    library.register_member(Member("S001", "Head Librarian", hash_pin("1234"), "staff"))
    # Two sample members. Default logins -> M001 / 1111  and  M002 / 2222
    library.register_member(Member("M001", "Ada Obi", hash_pin("1111"), "member"))
    library.register_member(Member("M002", "Tunde Bello", hash_pin("2222"), "member"))
    return library


def save_library(library, path=DATA_FILE):
    """Write the library to `path` as JSON.

    We write to a temporary file first and then swap it in. That way, if the
    program crashes halfway through writing, the old good file is untouched.
    """
    temp_path = path + ".tmp"                             # temporary file name
    with open(temp_path, "w", encoding="utf-8") as file:  # "w" = write; "with" closes it for us
        # indent=2 makes the file human-readable.
        json.dump(library.to_dict(), file, indent=2)
    os.replace(temp_path, path)                           # atomically replace the real file


def _start_fresh(reason, path):
    """Helper: return (new seeded library, message) after a load problem."""
    return seed_library(), f"{reason} Starting with a fresh library with sample data."


def load_library(path=DATA_FILE):
    """Load the library from `path`.

    Returns a tuple (library, message). The message tells the user what
    happened. This function never raises for bad files.
    """
    # Case 1: the file does not exist yet (first run).
    if not os.path.exists(path):
        return seed_library(), "No saved data found. Starting a new library with sample data."

    # Try to read the file's text.
    try:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
    except OSError as error:                              # permissions, disk problems, etc.
        return _start_fresh(f"Could not read '{path}' ({error}).", path)

    # Case 2: the file exists but is empty (or only spaces/newlines).
    if not text.strip():
        return _start_fresh(f"The data file '{path}' is empty.", path)

    # Case 3: the file has content; try to parse and rebuild the library.
    try:
        data = json.loads(text)                           # text -> dictionaries/lists
        library = Library.from_dict(data)                 # dictionaries -> objects
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
        # The file is damaged. Keep a copy so nothing is lost, then start fresh.
        backup = path + ".corrupt"
        try:
            os.replace(path, backup)                      # rename the bad file
            note = f" The damaged file was kept as '{backup}'."
        except OSError:
            note = ""
        return _start_fresh(f"The data file '{path}' is corrupted.{note}", path)

    # Success!
    return library, (f"Loaded {len(library.books)} books and "
                     f"{len(library.members)} members from '{path}'.")
