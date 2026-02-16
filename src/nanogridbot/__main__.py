"""Main entry point for NanoGridBot.

Delegates to the CLI module so that ``python -m nanogridbot`` behaves
identically to the ``nanogridbot`` console script.
"""

import sys

from nanogridbot.channels import ChannelRegistry
from nanogridbot.cli import create_channels, main, start_web_server

__all__ = ["ChannelRegistry", "create_channels", "main", "start_web_server"]

if __name__ == "__main__":
    sys.exit(main())
