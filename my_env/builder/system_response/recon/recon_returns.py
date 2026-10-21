"""Data-return registry fragment (``rows/data_returns.json``), fixed before any run.

``request_data_return(party, data_type)`` resolves a pair from this registry: ``available``
entries name the evidence ID that is materialised; ``not_held`` entries are defined refusals.
Messages state only what the evidence pack can support; they invent no behaviour of the
parties (no entry is ``refused``, because no published source records a party refusing).
The real-data track may contribute further entries (e.g. Elexon datasets) at integration.
"""

from __future__ import annotations

from typing import Any

PARTIES = {
    "ESO": "National Grid ESO (system operator; Electricity National Control Centre)",
    "NGET": "National Grid Electricity Transmission (transmission owner)",
    "ORSTED": "Ørsted (Hornsea One operator)",
    "RWE": "RWE Generation (Little Barford operator)",
    "DNO": "Distribution Network Operators (all licence areas, collectively)",
    "METEOGROUP": "MeteoGroup (lightning detection data provider cited by ESO and NGET)",
    "ELEXON": "Elexon (Balancing and Settlement Code data publisher)",
}

ENTRIES: list[dict[str, Any]] = [
    {
        "party": "DNO",
        "data_type": "lfdd_disconnection_and_restoration_returns",
        "status": "available",
        "evidence_id": "S05",
        "message": "Per-area LFDD returns (MW, customers, final restoration time) as tabulated by "
        "ESO and the E3C, with DNO-reported relay observations; fields the published tables "
        "leave blank stay blank.",
    },
    {
        "party": "DNO",
        "data_type": "embedded_generation_loss_returns",
        "status": "available",
        "evidence_id": "S06",
        "message": "The combined DNO embedded-generation return to ESO, its stated limits, and the "
        "published loss estimates listed by source, each in its source's own words.",
    },
    {
        "party": "DNO",
        "data_type": "real_time_distributed_generation_telemetry",
        "status": "not_held",
        "message": "Not held in this evidence pack: no real-time output telemetry for "
        "distributed generators was obtained. Ofgem states that most DNOs only record generation "
        "volumes half-hourly and that DNOs do not monitor distributed generator output in real "
        "time.",
    },
    {
        "party": "DNO",
        "data_type": "feeder_level_lfdd_relay_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no published feeder- or relay-level LFDD "
        "log was obtained; only the per-area returns tabulated by ESO and the E3C are available.",
    },
    {
        "party": "ESO",
        "data_type": "operational_call_record",
        "status": "available",
        "evidence_id": "R08",
        "message": "Transcription of ESO's published diagram of operational calls between its "
        "control room, NGET, DNO and Scottish control rooms.",
    },
    {
        "party": "ESO",
        "data_type": "control_room_log",
        "status": "available",
        "evidence_id": "S07",
        "message": "Reconstructed control-room log from ESO's published timelines and "
        "communication tables, including ESO's earlier (28 August 2019) account.",
    },
    {
        "party": "ESO",
        "data_type": "engineering_analysis",
        "status": "available",
        "evidence_id": "S12",
        "message": "Published loss accounting, frequency simulation, response and inertia "
        "assumptions, and differences between ESO's earlier and final accounts.",
    },
    {
        "party": "ESO",
        "data_type": "pmu_wams_traces",
        "status": "not_held",
        "message": "Not held in this evidence pack: no phasor measurement (PMU/WAMS) recording "
        "of the event was obtained; the recordings are not published.",
    },
    {
        "party": "NGET",
        "data_type": "protection_and_fault_records",
        "status": "available",
        "evidence_id": "R03",
        "message": "Reconstructed fault, protection, switching and power quality records for "
        "the Eaton Socon - Wymondley Main circuit.",
    },
    {
        "party": "NGET",
        "data_type": "pmu_wams_traces",
        "status": "not_held",
        "message": "Not held in this evidence pack: no phasor measurement (PMU/WAMS) recording "
        "of the event was obtained; the recordings are not published.",
    },
    {
        "party": "METEOGROUP",
        "data_type": "lightning_stroke_records",
        "status": "not_held",
        "message": "Not held in this evidence pack: stroke-level lightning records (time, "
        "location, peak current) are commercial data and were not obtained; only the figures "
        "reported by ESO and NGET are available.",
    },
    {
        "party": "ORSTED",
        "data_type": "event_log",
        "status": "available",
        "evidence_id": "S01",
        "message": "Reconstructed Hornsea One event log with attributed post-event annotations.",
    },
    {
        "party": "ORSTED",
        "data_type": "turbine_controller_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no turbine-controller or internal "
        "control-system log was found in the published sources; the operator's published report "
        "is the available account.",
    },
    {
        "party": "RWE",
        "data_type": "sequence_of_events",
        "status": "available",
        "evidence_id": "S03",
        "message": "Reconstructed Little Barford sequence-of-events extract (offsets from datum T) "
        "with attributed annotations.",
    },
    {
        "party": "RWE",
        "data_type": "shift_account",
        "status": "available",
        "evidence_id": "S04",
        "message": "Reconstructed Little Barford shift account with attributed operator and "
        "regulator statements.",
    },
    {
        "party": "RWE",
        "data_type": "plant_instrumentation_and_control_records",
        "status": "not_held",
        "message": "Not held in this evidence pack: no station instrumentation or control-system "
        "record was found in the published sources; the operator's preliminary findings are the "
        "available account.",
    },
    {
        "party": "ELEXON",
        "data_type": "physical_notifications_event_window",
        "status": "not_held",
        "message": "Not held in this evidence pack: Physical Notification data for 9 August 2019 "
        "after settlement period 4 are missing from the publisher's current dataset (its "
        "ingestion status resumes on 11 August 2019).",
    },
]


def registry() -> list[dict[str, Any]]:
    return sorted(ENTRIES, key=lambda e: (e["party"], e["data_type"]))


def _real(dataset_id: str, field: str, quote: str) -> dict[str, Any]:
    return {
        "source_id": "REAL-DATA-MANIFEST",
        "dataset_id": dataset_id,
        "field": field,
        "quote": quote,
    }


def _pdf(source_id: str, pdf_page: int, section: str, quote: str) -> dict[str, Any]:
    from recon_common import src

    return src(source_id, pdf_page, section, quote)


# Basis of each not_held message (private provenance; verified by verify_recon.py).
NOT_HELD_BASIS: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("DNO", "real_time_distributed_generation_telemetry"): [
        _pdf(
            "OFG",
            36,
            "Ofgem section 3, DNOs, 3.45",
            "Most of the DNOs only record information on generation volumes on their networks on a "
            "half-hourly basis",
        ),
        _pdf(
            "OFG",
            18,
            "Ofgem section 2, footnote 19",
            "as they also do not monitor output from distributed generators in real-time.",
        ),
    ],
    # Only the NGED/NPg portals were checked and found to hold nothing; the UKPN, ENWL and
    # SPEN portals were blocked (HTTP 403), so the message claims only that nothing was
    # obtained, not that nothing exists.
    ("DNO", "feeder_level_lfdd_relay_logs"): [
        _real(
            "nged_npg_dno_portals_historic_outages",
            "event_visible",
            "No historic outage or LFDD dataset.",
        ),
        _real(
            "ukpn_open_data_portal_interruptions_and_transformer_flows",
            "status",
            "blocked",
        ),
        _real("enwl_unplanned_outages_and_spen_faults_flows", "status", "blocked"),
    ],
    ("ESO", "pmu_wams_traces"): [
        _real("gb_transmission_pmu_wams_9aug2019", "event_visible", "Not available"),
        _real("gb_transmission_pmu_wams_9aug2019", "status", "blocked"),
        _real("gb_transmission_pmu_wams_9aug2019", "licence", "Not published"),
    ],
    ("NGET", "pmu_wams_traces"): [
        _real("gb_transmission_pmu_wams_9aug2019", "event_visible", "Not available"),
        _real("gb_transmission_pmu_wams_9aug2019", "status", "blocked"),
        _real("gb_transmission_pmu_wams_9aug2019", "licence", "Not published"),
    ],
    ("METEOGROUP", "lightning_stroke_records"): [
        _real(
            "meteogroup_lightning_cited_by_eso",
            "event_visible",
            "Not available; only the one-line citation.",
        ),
        _real("meteogroup_lightning_cited_by_eso", "licence", "Commercial"),
    ],
    ("ORSTED", "turbine_controller_logs"): [],
    ("RWE", "plant_instrumentation_and_control_records"): [],
    ("ELEXON", "physical_notifications_event_window"): [
        _real(
            "elexon_PN",
            "event_visible",
            "Ingestion status lists 2019-08-09 SP1-4 then resumes at 2019-08-11 SP5.",
        ),
        _real("elexon_PN", "status", "not_found"),
    ],
}
NOT_HELD_NOTE = (
    "Every not_held message says only that the item is not held in this evidence pack and was "
    "not obtained, plus what its recorded basis states; it never claims that a record does not "
    "exist. Entries with an empty basis record that the item is absent from the published "
    "sources and from the real-data search (no source lists it)."
)
