"""Compatibility facade for the bot's marriage subsystem.

The implementation lives in :mod:`marriage`.  These re-exports keep
existing imports from :mod:`main` working while the application is
incrementally split into dedicated modules.
"""

from marriage import MarriageDatabase, MarriageModule

__all__ = ["MarriageDatabase", "MarriageModule"]

if __name__ == "__main__":
    from start import main as run_bot

    run_bot()
