"""ARTG lookups against the local SQLite copy.

There is no public ARTG API. The register is exported from the TGA search tool
and loaded by scripts/load_artg.py. Treat the local copy as a monthly snapshot
and record its date in every report that relies on it.
"""


def comparable_entries(intended_purpose: str, limit: int = 10) -> list[dict]:
    """Entries whose intended purpose resembles this one, with their class."""
    raise NotImplementedError
