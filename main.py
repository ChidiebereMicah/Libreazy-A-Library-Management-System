"""
main.py  --  START HERE

Run the program:        python main.py
Run the self-tests:     python main.py --test

Default logins on first run:
    Staff   S001 / PIN 1234
    Member  M001 / PIN 1111   (Ada Obi)
    Member  M002 / PIN 2222   (Tunde Bello)
"""

import sys                                   # gives access to command-line arguments

import ui
from storage import load_library


def main():
    """Load data, run the menus, and always save on the way out."""
    # sys.argv is the list of words typed on the command line.
    if "--test" in sys.argv:
        from tests import run_tests          # imported only when needed
        run_tests()
        return                               # skip the normal program

    library, message = load_library()        # read the JSON file (or start fresh)
    print(message)                           # tell the user what happened
    try:
        ui.run(library)                      # the menus; returns when the user exits
    except (KeyboardInterrupt, EOFError):    # Ctrl+C or Ctrl+D / closed input
        print("\nInterrupted. Saving your data...")
    finally:
        ui.persist(library)                  # runs no matter how we leave the try block


# This guard means main() runs only when you execute this file directly,
# not when another file imports it.
if __name__ == "__main__":
    main()
