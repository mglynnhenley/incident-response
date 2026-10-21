"""The data-return registry (manifest v2 ``data_returns``), fixed before the run.

Each entry is ``{party, data_type, status, evidence_id?, message?}``:

* ``available``: ``evidence_id`` names a bundle document, which ``request_data_return``
  materialises and returns exactly like ``request_document``; ``message`` is optional;
* ``not_held`` / ``refused``: no ``evidence_id``; ``message`` (required) is the defined
  answer, returned as a ``NOT_HELD`` / ``REFUSED`` error.

Requests are matched on the normalised (case-folded, whitespace-collapsed) party and
data type; only the ``(party, data_type)`` pairs are public, never the status.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from environment.incident.catalogue import CatalogueError
from environment.incident.matching import normalise_key
from environment.incident.schema_v2 import (
    EVIDENCE_ID_RE,
    check_keys,
    optional_str,
    require_id,
    require_str,
)

__all__ = ["DATA_RETURN_STATUSES", "DataReturn", "DataReturnRegistry"]

DATA_RETURN_STATUSES = ("available", "not_held", "refused")


@dataclass(frozen=True)
class DataReturn:
    party: str
    data_type: str
    status: str
    evidence_id: str | None
    message: str | None

    @property
    def key(self) -> tuple[str, str]:
        return (normalise_key(self.party), normalise_key(self.data_type))

    def summary(self) -> dict[str, str]:
        return {"party": self.party, "data_type": self.data_type}


class DataReturnRegistry:
    def __init__(self, entries: Sequence[DataReturn]) -> None:
        self.entries = tuple(
            sorted(entries, key=lambda e: (e.key, e.party, e.data_type))
        )
        self._by_key = {entry.key: entry for entry in self.entries}

    @classmethod
    def parse(
        cls, raw: Any, document_ids: set[str], where: str = "data_returns"
    ) -> DataReturnRegistry:
        if not isinstance(raw, list):
            raise CatalogueError(f"{where}: must be a list")
        entries: list[DataReturn] = []
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(raw):
            at = f"{where}[{index}]"
            obj = check_keys(
                item, at, ("party", "data_type", "status"), ("evidence_id", "message")
            )
            status = obj.get("status")
            if status not in DATA_RETURN_STATUSES:
                raise CatalogueError(
                    f"{at}: status {status!r} is not one of "
                    f"{', '.join(DATA_RETURN_STATUSES)}"
                )
            evidence_id = None
            if status == "available":
                evidence_id = require_id(obj, "evidence_id", at, EVIDENCE_ID_RE)
                if evidence_id not in document_ids:
                    raise CatalogueError(
                        f"{at}: evidence_id {evidence_id!r} is not a bundle document"
                    )
                message = optional_str(obj, "message", at)
            else:
                if obj.get("evidence_id") is not None:
                    raise CatalogueError(
                        f"{at}: a {status} data return must not name an evidence_id"
                    )
                message = require_str(obj, "message", at)
            entry = DataReturn(
                party=require_str(obj, "party", at),
                data_type=require_str(obj, "data_type", at),
                status=status,
                evidence_id=evidence_id,
                message=message,
            )
            if entry.key in seen:
                raise CatalogueError(
                    f"{at}: duplicate data return for party {entry.party!r} and "
                    f"data_type {entry.data_type!r}"
                )
            seen.add(entry.key)
            entries.append(entry)
        return cls(entries)

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def lookup(self, party: str, data_type: str) -> DataReturn | None:
        return self._by_key.get((normalise_key(party), normalise_key(data_type)))

    def parties(self) -> list[str]:
        return sorted({entry.party for entry in self.entries})

    def data_types_for(self, party: str) -> list[str]:
        wanted = normalise_key(party)
        return [e.data_type for e in self.entries if normalise_key(e.party) == wanted]

    def evidence_ids(self) -> set[str]:
        return {e.evidence_id for e in self.entries if e.evidence_id is not None}

    def summaries(self) -> list[dict[str, str]]:
        return [entry.summary() for entry in self.entries]

    @staticmethod
    def pairs_text(entries: Sequence[Mapping[str, str]]) -> str:
        return "; ".join(f"{e['party']} / {e['data_type']}" for e in entries)
