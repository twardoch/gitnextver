# this_file: src/gitnextver/versioning.py
"""Pure semantic-tag selection; importing or calling this module never runs Git."""

import re
from collections.abc import Iterable

TAG_PATTERN = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def next_version(
    tags: Iterable[str], bump: str = "patch", initial: str = "v1.0.0"
) -> str:
    """Increment the highest stable tag, or return initial when none exist.

    Accept only canonical vMAJOR.MINOR.PATCH tags. Legacy host suffixes,
    prereleases and malformed tags are ignored. Minor/major bumps reset the
    smaller components. Invalid options raise before any repository I/O.
    """
    if bump not in ("major", "minor", "patch"):
        raise ValueError("bump must be major, minor or patch")
    if not TAG_PATTERN.fullmatch(initial):
        raise ValueError("initial must be a canonical vMAJOR.MINOR.PATCH tag")
    versions = [
        tuple(map(int, match.groups()))
        for tag in tags
        if (match := TAG_PATTERN.fullmatch(tag))
    ]
    if not versions:
        return initial
    major, minor, patch = max(versions)
    match bump:
        case "major":
            major, minor, patch = major + 1, 0, 0
        case "minor":
            minor, patch = minor + 1, 0
        case "patch":
            patch += 1
    return f"v{major}.{minor}.{patch}"
