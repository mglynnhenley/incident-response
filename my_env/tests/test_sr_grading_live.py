"""Regression on real model output: the five live MVP submissions (bundle 1.1.0) cite
only R01, R03, S01, S03 and S04, which the system-response bundle also holds, so the
system-response grader must grade them and reach the same automated results as the
MVP grader on the criteria it reuses (frequency landmarks and duration, the
initiating-fault time and clearance, the ST1C mechanism)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sr_grading_support import catalogue, key, row

from environment.incident import grading as mvp
from environment.incident import sr_grading
from environment.incident.catalogue import Catalogue
from environment.incident.paths import DEFAULT_BUNDLE_DIR

LIVE = Path(__file__).resolve().parent / "fixtures" / "live"
SUBMISSIONS = sorted(LIVE.glob("gb2019-v2-*.submission.json"))
PAIRS = {
    "T03.01": "D3.1",
    "T03.02": "D3.2",
    "T03.03": "D3.3",
    "T04.01": "D3.4",
    "T04.03": "D3.5",
    "T07.01": "D4.2",
    "T01.02": "D1.2",
    "T01.03b": "D1.3",
}


@pytest.fixture(scope="module")
def mvp_key():
    return mvp.load_key()


@pytest.fixture(scope="module")
def mvp_catalogue():
    return Catalogue.load(DEFAULT_BUNDLE_DIR)


def test_live_fixtures_present():
    assert len(SUBMISSIONS) == 4


@pytest.mark.parametrize(
    "path", SUBMISSIONS, ids=[p.name.split(".")[0] for p in SUBMISSIONS]
)
def test_live_submission_parity_with_the_mvp_grader(path, mvp_key, mvp_catalogue):
    sub = json.loads(path.read_text(encoding="utf-8"))
    report = sr_grading.grade_submission(sub, catalogue(), key())
    reference = mvp.grade_submission(sub, mvp_catalogue, mvp_key)
    by_mvp = {r["criterion_id"]: r for r in reference["criteria"]}
    assert len(report["criteria"]) == len(key()["criteria"])
    for cid, mid in PAIRS.items():
        ours, theirs = row(report, cid), by_mvp[mid]
        assert ours["content"]["auto_proposal"] == theirs["content"]["auto_proposal"], (
            cid,
            path.name,
        )
        assert ours["content"]["source"] == theirs["content"]["source"], (
            cid,
            path.name,
        )
        assert ours["content"]["value"] == theirs["content"]["value"], (cid, path.name)
    # nothing in these submissions is on a wrong accounting basis or a severe flag
    assert report["flags"]["accounting_traps"] == []
    assert report["severe_flags"] == []
    assert report["status"] == "provisional"


def test_live_submissions_pass_the_judge_track_hooks(mvp_key):
    """The judge track resolves cited spans with resolve_text; every live citation
    resolves on the system-response bundle (S01 line numbers moved by one, so some
    spans point at the neighbouring line, which the reviewer sees)."""
    for path in SUBMISSIONS:
        sub = json.loads(path.read_text(encoding="utf-8"))
        for f in sub["findings"]:
            for c in f["citations"]:
                text = sr_grading.resolve_text(
                    catalogue(), c["evidence_id"], c["locator"]
                )
                assert text.strip(), (path.name, c)
