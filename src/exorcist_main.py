"""Frozen-exe / console-script entry point. Keeps package context for relative imports."""
import sys

from exorcist.cli import main

if __name__ == "__main__":
    sys.exit(main())
