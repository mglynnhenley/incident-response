"""Full-investigation reconstruction track: data-return additions and the GTR control row.

No builder inputs: the registry additions must merge with the frozen system-response registry
under the runtime parser (no duplicate pair, evidence IDs resolvable), every refusal must be a
defined ``not_held`` with a recorded basis, and the GTR-FLEET-CONTROL row must restate its S08
lines with an index time recomputed from the printed minute.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from environment.incident.returns import DataReturnRegistry

ENV_ROOT = Path(__file__).resolve().parents[1]
INCIDENT = ENV_ROOT / "src" / "environment" / "incident"
FI = INCIDENT / "bundles" / "full_investigation"
SR_MANIFEST = json.loads(
    (INCIDENT / "bundles" / "system_response" / "manifest.json").read_text("utf-8")
)
ROWS = ENV_ROOT / "builder" / "full_investigation" / "rows"
ADDITIONS = json.loads((ROWS / "data_returns.json").read_text("utf-8"))
PROVENANCE = json.loads(
    (INCIDENT / "private" / "full_investigation" / "provenance_recon.json").read_text(
        "utf-8"
    )
)
NEW_DOCS = {"R10", "S08", "S10", "S11"}


def merged() -> DataReturnRegistry:
    doc_ids = {d["doc_id"] for d in SR_MANIFEST["documents"]} | NEW_DOCS
    return DataReturnRegistry.parse(SR_MANIFEST["data_returns"] + ADDITIONS, doc_ids)


def test_additions_merge_with_the_system_response_registry() -> None:
    registry = merged()
    assert len(registry) == len(SR_MANIFEST["data_returns"]) + len(ADDITIONS)
    gtr = registry.lookup("GTR", "fleet_incident_records")
    assert gtr is not None and gtr.status == "available" and gtr.evidence_id == "S08"
    eso = registry.lookup("eso", "Generator_Compliance_Process_Records")
    assert eso is not None and eso.evidence_id == "S10"


def test_requested_refusals_are_not_held_with_a_basis() -> None:
    wanted = {
        ("NETWORK_RAIL", "train_running_records"),
        ("NEWCASTLE_AIRPORT", "airport_power_and_incident_logs"),
        ("WATER_COMPANY", "pumping_station_and_treatment_works_logs"),
        ("REFINERY_OPERATOR", "site_trip_and_shutdown_logs"),
        ("ESO", "grid_code_compliance_test_records"),
        ("ORSTED", "grid_code_compliance_test_records"),
        ("RWE", "grid_code_compliance_test_records"),
        ("GTR", "onboard_tcms_event_logs"),
    }
    registry = merged()
    bases = {
        (b["party"], b["data_type"]): b["basis"]
        for b in PROVENANCE["data_returns"]["not_held_basis"]
    }
    for party, data_type in wanted:
        entry = registry.lookup(party, data_type)
        assert entry is not None and entry.status == "not_held", (party, data_type)
        assert entry.message.startswith("Not held in this evidence pack")
        assert (party, data_type) in bases
    assert all(e["status"] != "refused" for e in ADDITIONS)
    assert all(e["status"] == "available" or e["message"] for e in ADDITIONS)


def test_compliance_test_record_answers_describe_each_stations_appendix() -> None:
    """Appendix G records different things for the two stations: Hornsea One's tests with test,
    results and approval dates plus outstanding tests; Little Barford's compliance activities
    with one date each. RWE's answer must not describe Hornsea's layout."""
    registry = merged()
    messages = {
        party: registry.lookup(party, "grid_code_compliance_test_records").message
        for party in ("ESO", "ORSTED", "RWE")
    }
    rwe, orsted, eso = messages["RWE"], messages["ORSTED"], messages["ESO"]
    assert len(set(messages.values())) == 3
    assert "Little Barford's compliance activities and their dates (2012-2013)" in rwe
    for hornsea_only in ("outstanding tests", "results", "approval", "Hornsea"):
        assert hornsea_only not in rwe, hornsea_only
    assert "Hornsea One" in orsted and "outstanding tests" in orsted
    assert "Little Barford" not in orsted
    assert "Hornsea One" in eso and "Little Barford" in eso
    bases = {
        (b["party"], b["data_type"]): b["basis"]
        for b in PROVENANCE["data_returns"]["not_held_basis"]
    }

    def pages(party: str) -> set[int]:
        return {
            ref["pdf_page"]
            for ref in bases[(party, "grid_code_compliance_test_records")]
            if ref.get("source_id") == "APP"
        }

    assert pages("RWE") == {54, 91}
    assert pages("ORSTED") == {52, 53, 91}
    assert pages("ESO") == {52, 53, 54, 91}


def test_refusal_messages_do_not_claim_records_do_not_exist() -> None:
    for entry in ADDITIONS:
        message = entry.get("message", "").casefold()
        assert "does not exist" not in message and "never existed" not in message
        assert "£" not in message


def test_gtr_row_restates_s08_and_indexes_the_printed_minute() -> None:
    (line,) = (ROWS / "recon_s08.jsonl").read_text("utf-8").splitlines()
    row = json.loads(line)
    assert row["room_id"] == "GTR-FLEET-CONTROL" and row["kind"] == "control"
    assert row["recorded_time"] == "1653" and row["index_uncertainty_s"] == 60.0
    local = datetime(2019, 8, 9, 16, 53, tzinfo=UTC)
    assert row["index_time_utc"] == (local - timedelta(hours=1)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    )
    s08 = (FI / "S08" / "S08.txt").read_text("utf-8").split("\n")
    a, b = (int(x) for x in row["provenance"]["doc_lines"][1:].split("-L"))
    assert row["text"] == " ".join(" ".join(s08[a - 1 : b]).split())
    assert row["text"].startswith("G01 ") and "1653 [reported]" in row["text"]
    assert row["provenance"]["sources"]
    fragment = PROVENANCE["row_fragments"]["recon_s08.jsonl"]
    assert fragment["rows"] == 1 and "S08-G01" in fragment["provenance"]


def test_row_ids_do_not_collide_with_system_response_logs() -> None:
    sr_ids = set()
    logs = INCIDENT / "bundles" / "system_response" / "logs"
    for path in logs.rglob("*.jsonl"):
        for line in path.read_text("utf-8").splitlines():
            row = json.loads(line)
            sr_ids.add(row.get("entry_id") or row.get("event_id"))
    for line in (ROWS / "recon_s08.jsonl").read_text("utf-8").splitlines():
        assert json.loads(line)["entry_id"] not in sr_ids
