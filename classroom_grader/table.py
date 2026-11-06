"""Plain-text tables for command output."""

from collections import Counter
from collections.abc import Iterable, Sequence


def format_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Return ``rows`` under ``headers`` as left-aligned columns, two spaces apart."""
    lines = [list(headers), *(list(row) for row in rows)]
    widths = [max(len(cell) for cell in column) for column in zip(*lines, strict=True)]
    return "\n".join(
        "  ".join(
            cell.ljust(width) for cell, width in zip(line, widths, strict=True)
        ).rstrip()
        for line in lines
    )


def printable(text: str) -> str:
    """Return ``text`` for output, quoted when it has unprintable characters."""
    return text if text.isprintable() else repr(text)


def state_counts(states: Sequence[str], found: Iterable[str]) -> str:
    """Return how many of ``found`` are in each of ``states``, in that order.

    For example ``2 pushed, 1 refused``; ``no students`` when ``found`` is empty.
    """
    counts = Counter(found)
    return ", ".join(f"{counts[s]} {s}" for s in states if counts[s]) or "no students"
