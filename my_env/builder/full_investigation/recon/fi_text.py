"""Lay out the hand-authored record sources (``text/*.src.txt``) as bundle text.

The sources hold one logical item per line so that they can be edited and reviewed; the bundle
text is the same words wrapped to at most 110 characters (the bundle text convention):

- lines starting with ``#H `` are header lines, copied verbatim (without the marker);
- a line starting with an item label (``G01  ``, ``T1   ``) wraps with a five-space
  continuation indent; any other line (PART/SECTION headings, notes) wraps with none;
- blank lines are kept;
- a number, its unit and its value tag are never split across lines, so no line starts with a
  value tag.

The layout is deterministic; ``build_fi_recon.py`` writes its output and ``--check`` compares.
"""

from __future__ import annotations

import re

WIDTH = 110
TAGS = (
    "[reported]",
    "[estimated]",
    "[measured]",
    "[modelled]",
    "[digitised]",
    "[illustrative]",
)
UNITS = {"Hz", "MW", "ms", "s", "seconds", "minutes", "minute", "hours", "kV", "%"}
_ITEM = re.compile(r"^[A-Z][A-Z0-9]{0,3} {2,}")


class LayoutError(ValueError):
    """A source line cannot be laid out within the width."""


def _atoms(text: str) -> list[str]:
    out: list[str] = []
    for word in text.split(" "):
        if not word:
            continue
        bare = word.rstrip(",;.:)")
        if out and (
            word.startswith(TAGS) or (bare in UNITS and re.search(r"\d$", out[-1]))
        ):
            out[-1] = f"{out[-1]} {word}"
        else:
            out.append(word)
    return out


def _wrap(line: str, indent: str) -> list[str]:
    lines: list[str] = []
    current = ""
    label = _ITEM.match(line) if indent else None
    if label:
        current, line = label.group(0), line[label.end() :]
    for atom in _atoms(line):
        if not current.strip() or current.endswith("  "):
            candidate = current + atom
        else:
            candidate = f"{current} {atom}"
        if len(candidate) <= WIDTH or not current.strip():
            current = candidate
        else:
            lines.append(current)
            current = indent + atom
    lines.append(current)
    return lines


def layout(source: str) -> str:
    out: list[str] = []
    for line in source.rstrip("\n").split("\n"):
        if line.startswith("#H "):
            out.append(line[3:])
        elif not line.strip():
            out.append("")
        elif _ITEM.match(line):
            out.extend(_wrap(line, "     "))
        else:
            out.extend(_wrap(line, ""))
    too_long = [(i + 1, len(text)) for i, text in enumerate(out) if len(text) > WIDTH]
    if too_long:
        raise LayoutError(f"lines longer than {WIDTH} characters: {too_long}")
    return "\n".join(out) + "\n"
