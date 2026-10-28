"""Plain-text tables for command output."""

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
