"""Document container of the R09/R11/R12 builders (increment A's DocBuild with a chosen STATUS)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fi_real_common import require, wrap
from real_docbuild import (
    LABEL_REAL_AND_TABLES,
    STATUS_REAL_AND_TABLES_BASE,
    Artifact,
    DocBuild,
)

LABEL_REAL = "REAL DATA EXTRACTS"
STATUS_REAL_BASE = (
    "STATUS: REAL DATA EXTRACTS — dataset values, identifiers and publication dates are "
    "unchanged from the publishers' files (only rows and columns were selected)."
)
STATUS_BASES = {
    LABEL_REAL_AND_TABLES: STATUS_REAL_AND_TABLES_BASE,
    LABEL_REAL: STATUS_REAL_BASE,
}

VALUE_LEGEND = (
    "Value-status legend: [measured] metered or observed value as published; [reported] value, "
    "time or statement given by its publisher or by a report; [estimated] value its source "
    "describes as an estimate; [modelled] value produced by a model; [digitised] and "
    "[illustrative] are not used."
)

__all__ = ["Artifact", "FiDocBuild", "LABEL_REAL", "LABEL_REAL_AND_TABLES"]


@dataclass
class FiDocBuild(DocBuild):
    #: Manifest-fragment extras (proposals for the integration step).
    party_aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)

    def header(self, owner_line: str, clock_lines: list[str]) -> None:
        require(
            self.label in STATUS_BASES, f"{self.doc_id}: unknown label {self.label!r}"
        )
        doc = self.text
        doc.frame(
            "Header: title, originator, record type, STATUS label, clock basis, value legend",
            f"DOCUMENT {self.doc_id} — {self.title}",
            *wrap(f"Owner/originator: {owner_line}"),
            *wrap(f"Record type: {self.record_type}"),
            *wrap(f"{STATUS_BASES[self.label]} {self.status_scope}"),
            *clock_lines,
            *wrap(VALUE_LEGEND),
        )
