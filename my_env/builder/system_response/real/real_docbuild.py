"""Document container shared by the R02/R04/R06/R07 builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from real_common import TextDoc, require, sha256_bytes

STATUS_REAL_AND_TABLES_BASE = (
    "STATUS: REAL DATA EXTRACTS WITH TRANSCRIBED REPORT TABLES — dataset values are unchanged from "
    "the publishers' files (only rows and columns were selected); report tables, captions and "
    "quotations are reproduced as printed."
)
NOTHING_SYNTHESISED = "Nothing in this record is synthesised."
STATUS_REAL_AND_TABLES = f"{STATUS_REAL_AND_TABLES_BASE} {NOTHING_SYNTHESISED}"
LABEL_REAL_AND_TABLES = "REAL DATA EXTRACTS WITH TRANSCRIBED REPORT TABLES"

VALUE_LEGEND = (
    "Value-status legend: [measured] metered or observed value as published; [reported] value "
    "stated by its publisher or by a report; [estimated] value its source describes as an "
    "estimate; [modelled] value produced by a model; [digitised] and [illustrative] are not used."
)


@dataclass
class Artifact:
    name: str
    media_type: str
    description: str
    data: bytes
    provenance: dict[str, Any]
    timeseries: dict[str, Any] | None = None

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.data)


@dataclass
class DocBuild:
    doc_id: str
    title: str
    owner: str
    category: str
    record_type: str
    construction: str
    text: TextDoc
    label: str = LABEL_REAL_AND_TABLES
    date: str = "2019-08-09"
    #: Last sentence of the STATUS line: what in the record is not a real extract or a
    #: transcription (R07 scopes it to Parts A-C; Part D holds builder-written gists).
    status_scope: str = NOTHING_SYNTHESISED
    artifacts: list[Artifact] = field(default_factory=list)
    asset_rows: list[dict[str, Any]] = field(default_factory=list)
    control_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def text_name(self) -> str:
        return f"{self.doc_id}.txt"

    def header(self, owner_line: str, clock_lines: list[str]) -> None:
        doc = self.text
        doc.frame(
            "Header: title, originator, record type, STATUS label, clock basis, value legend",
            f"DOCUMENT {self.doc_id} — {self.title}",
            *_wrapped(f"Owner/originator: {owner_line}"),
            *_wrapped(f"Record type: {self.record_type}"),
            *_wrapped(f"{STATUS_REAL_AND_TABLES_BASE} {self.status_scope}"),
            *clock_lines,
            *_wrapped(VALUE_LEGEND),
        )

    def add_artifact(self, artifact: Artifact) -> None:
        require(
            all(a.name != artifact.name for a in self.artifacts),
            f"duplicate {artifact.name}",
        )
        self.artifacts.append(artifact)


def _wrapped(text: str) -> list[str]:
    from real_common import wrap

    return wrap(text)
