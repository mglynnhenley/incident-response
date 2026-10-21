"""Content-addressed cache of judge responses.

One file per request, ``<cache_dir>/<cache_key>.json``. The cache key is the sha256 of
the canonical JSON of its key material: the submission, bundle and key hashes (and key
version), the rubric version and sha256, the judge model, the prompt template sha256,
the request settings, the unit and the sha256 of the exact messages. An entry is used
only when its stored key material matches, so a changed input is always a miss. Only
responses that passed validation are stored; the raw text is kept and re-checked on
every read, so re-runs cost nothing and reproduce the same output.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = ["CACHE_SCHEMA", "JudgeCache", "cache_key"]

CACHE_SCHEMA = "gb2019-sr-judge-cache/1"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def cache_key(material: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(material).encode("utf-8")).hexdigest()


class JudgeCache:
    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str, material: Mapping[str, Any]) -> dict[str, Any] | None:
        path = self.path(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(entry, dict)
            or entry.get("cache_schema") != CACHE_SCHEMA
            or entry.get("cache_key") != key
            or _canonical(entry.get("key_material")) != _canonical(material)
            or not isinstance(entry.get("attempts"), list)
            or not entry["attempts"]
        ):
            return None
        return entry

    def put(
        self, key: str, material: Mapping[str, Any], entry: Mapping[str, Any]
    ) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        data = {
            **entry,
            "cache_schema": CACHE_SCHEMA,
            "cache_key": key,
            "key_material": dict(material),
        }
        text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        fd, tmp = tempfile.mkstemp(dir=self.directory, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, self.path(key))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return self.path(key)
