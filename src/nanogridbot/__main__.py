"""Main entry point for NanoGridBot.

Delegates to the CLI module so that ``python -m nanogridbot`` behaves
identically to the ``nanogridbot`` console script.
"""

import sys

from nanogridbot.cli import main

if __name__ == "__main__":
    sys.exit(main())
