"""Data-return registry additions for the full investigation (``rows/data_returns.json``).

The file holds only the entries this increment adds; the integration step appends them to the
system-response registry (17 entries, unchanged). ``request_data_return(party, data_type)``
resolves a pair: ``available`` entries name the evidence ID that is materialised; ``not_held``
entries are defined refusals fixed before any run. As in increment A, no entry is ``refused``:
no published source records a party refusing a request (Grid Code compliance test records
included: ESO Appendix G publishes only Hornsea One's test, results and approval dates with its
outstanding tests and Little Barford's dated compliance activities, and ESO's answer 45 says ride
through is demonstrated by simulation studies rather than tests). Messages say only that an
item is not held in this evidence pack and was not obtained, plus what the recorded basis
states; they never claim that a record does not exist.
"""

from __future__ import annotations

from typing import Any

from fi_recon_common import raw_src, real_src, src

PARTIES = {
    "GTR": "Govia Thameslink Railway (train operator of the Class 700/717 fleet)",
    "NETWORK_RAIL": "Network Rail (railway infrastructure operator)",
    "UKPN": "UK Power Networks (Eastern, London and South Eastern licence areas)",
    "ESO": "National Grid ESO (runs the Grid Code compliance process)",
    "ORSTED": "Ørsted (Hornsea One operator)",
    "RWE": "RWE Generation (Little Barford operator)",
    "NEWCASTLE_AIRPORT": "Newcastle International Airport",
    "HOSPITAL_TRUST": "East Suffolk and North Essex NHS Foundation Trust (Ipswich Hospital)",
    "WATER_COMPANY": "Water companies (not named in the published reports)",
    "REFINERY_OPERATOR": "Oil refinery operator (not named in the published reports)",
}

_RIDE_THROUGH = (
    " The ESO states that fault ride-through is demonstrated by the asset owner's simulation "
    "studies, not by direct tests."
)
#: Not-held answers for Grid Code compliance test records, one per party: the published
#: appendix records different things for the two stations (Hornsea One: tests with their
#: test, results-sent and approval dates, and the outstanding tests; Little Barford: only
#: its compliance activities with one date each, 2012-2013).
COMPLIANCE_MESSAGES = {
    "ORSTED": "Not held in this evidence pack: Hornsea One's Grid Code compliance test reports "
    "and simulation studies themselves were not obtained; the ESO's published compliance "
    "appendix lists only Hornsea One's completed tests with their test, results and approval "
    "dates, and its outstanding tests." + _RIDE_THROUGH,
    "RWE": "Not held in this evidence pack: no Little Barford compliance test report or "
    "simulation study was obtained; the ESO's published compliance appendix lists only Little "
    "Barford's compliance activities and their dates (2012-2013)." + _RIDE_THROUGH,
    "ESO": "Not held in this evidence pack: the Grid Code compliance test reports and simulation "
    "studies themselves were not obtained; the ESO's published compliance appendix lists, for "
    "Hornsea One, completed tests with their test, results and approval dates and the "
    "outstanding tests and, for Little Barford, only its compliance activities and their dates "
    "(2012-2013)." + _RIDE_THROUGH,
}

ENTRIES: list[dict[str, Any]] = [
    {
        "party": "GTR",
        "data_type": "fleet_incident_records",
        "status": "available",
        "evidence_id": "S08",
        "message": "Rail fleet and service records: GTR's technical review of the Class 700/717 "
        "shutdowns with the rail accounts published by ORR, the ESO, Ofgem and the E3C, each "
        "restated separately.",
    },
    {
        "party": "GTR",
        "data_type": "onboard_tcms_event_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no train-level TCMS or on-board event log was "
        "found in the published sources or obtained; GTR's technical review (in the rail fleet "
        "records) is the available account.",
    },
    {
        "party": "NETWORK_RAIL",
        "data_type": "train_running_records",
        "status": "not_held",
        "message": "Not held in this evidence pack: train-level running records for 9 August 2019 "
        "(Darwin Historic Service Performance) were not obtained; the service redirected the "
        "request to a login.",
    },
    {
        "party": "UKPN",
        "data_type": "reconnection_switching_records",
        "status": "not_held",
        "message": "Not held in this evidence pack: no UK Power Networks switching or "
        "operational-system record of the Eastern and South Eastern reconnections was obtained "
        "(its open data portal refused access). Ofgem's report states only that the "
        "reconnections were caused by the configuration of the DNOs' operational systems.",
    },
    {
        "party": "ESO",
        "data_type": "generator_compliance_process_records",
        "status": "available",
        "evidence_id": "S10",
        "message": "Compliance-process records for Hornsea One and Little Barford (dates, tests "
        "and outstanding items as published) with the ESO's answers and the regulator's and "
        "E3C's statements, attributed.",
    },
    {
        "party": "ESO",
        "data_type": "grid_code_compliance_test_records",
        "status": "not_held",
        "message": COMPLIANCE_MESSAGES["ESO"],
    },
    {
        "party": "ORSTED",
        "data_type": "grid_code_compliance_test_records",
        "status": "not_held",
        "message": COMPLIANCE_MESSAGES["ORSTED"],
    },
    {
        "party": "RWE",
        "data_type": "grid_code_compliance_test_records",
        "status": "not_held",
        "message": COMPLIANCE_MESSAGES["RWE"],
    },
    {
        "party": "NEWCASTLE_AIRPORT",
        "data_type": "airport_power_and_incident_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no airport incident or power log was "
        "obtained; the text of the airport's own public messages of the day could not be "
        "recovered, and historical flight data were not accessible.",
    },
    {
        "party": "HOSPITAL_TRUST",
        "data_type": "site_electrical_records",
        "status": "not_held",
        "message": "Not held in this evidence pack: no hospital switching, protection or "
        "generator record was obtained; the trust's public statement of 10 August 2019 gives no "
        "times.",
    },
    {
        "party": "WATER_COMPANY",
        "data_type": "pumping_station_and_treatment_works_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no water company statement or site log was "
        "located; the published reports give anonymised figures only.",
    },
    {
        "party": "REFINERY_OPERATOR",
        "data_type": "site_trip_and_shutdown_logs",
        "status": "not_held",
        "message": "Not held in this evidence pack: no refinery site log was obtained; the "
        "published reports do not name the refinery.",
    },
]


def registry() -> list[dict[str, Any]]:
    return sorted(ENTRIES, key=lambda e: (e["party"], e["data_type"]))


APP_G = "Appendix G – Compliance Testing for Hornsea and Little Barford"
APP_M45 = (
    "Appendix M – ESO E3C Questions and Answers (data available to the ESO on 28 August 2019), "
    "answer 45"
)
HORNSEA_COMPLIANCE_BASIS = [
    src("APP", 52, APP_G, "Completed Grid Code Compliance Test Dates"),
    src(
        "APP",
        53,
        APP_G,
        "20% Capacity Voltage Tests Date of Test Results sent to NG ESO Approval by ESO",
    ),
    src("APP", 53, APP_G, "List of Outstanding Tests"),
]
LITTLE_BARFORD_COMPLIANCE_BASIS = [
    src("APP", 54, APP_G, "Little Barford Compliance Testing"),
    src(
        "APP",
        54,
        APP_G,
        "the compliance process applied to the replacement of gas turbines and associated "
        "control systems",
    ),
    src("APP", 54, APP_G, "ESO issued LON for Gas Turbine replacement 06/01/2012"),
    src("APP", 54, APP_G, "ESO Issued FON 26/04/2013"),
]
RIDE_THROUGH_BASIS = [
    src(
        "APP",
        91,
        APP_M45,
        "There are no direct tests for generator ride-through for fault and large frequency "
        "changes.",
    ),
    src(
        "APP",
        91,
        APP_M45,
        "Simulation studies are performed by the asset owner to demonstrate generator "
        "ride-through capability",
    ),
]

# Basis of each not_held message (private provenance; verified by verify_fi_recon.py).
NOT_HELD_BASIS: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("GTR", "onboard_tcms_event_logs"): [],
    ("NETWORK_RAIL", "train_running_records"): [
        real_src("historic_train_running_apis", "status", "blocked"),
        real_src(
            "historic_train_running_apis",
            "event_visible",
            "Not retrieved. Re-tested: HSP HTTP 302 -> /login.",
        ),
        real_src(
            "historic_train_running_apis",
            "publisher",
            "Darwin Historic Service Performance (HSP)",
        ),
    ],
    ("UKPN", "reconnection_switching_records"): [
        real_src(
            "ukpn_open_data_portal_interruptions_and_transformer_flows",
            "status",
            "blocked",
        ),
        real_src(
            "ukpn_open_data_portal_interruptions_and_transformer_flows",
            "event_visible",
            "HTTP 403 'ForbiddenAccess'",
        ),
        src(
            "OFG",
            35,
            "Section 3, DNOs, 3.43",
            "These instances were caused by the configuration of the DNOs’ operational "
            "systems.",
        ),
    ],
    ("ESO", "grid_code_compliance_test_records"): [
        *HORNSEA_COMPLIANCE_BASIS,
        *LITTLE_BARFORD_COMPLIANCE_BASIS,
        *RIDE_THROUGH_BASIS,
    ],
    ("ORSTED", "grid_code_compliance_test_records"): [
        *HORNSEA_COMPLIANCE_BASIS,
        *RIDE_THROUGH_BASIS,
    ],
    ("RWE", "grid_code_compliance_test_records"): [
        *LITTLE_BARFORD_COMPLIANCE_BASIS,
        *RIDE_THROUGH_BASIS,
    ],
    ("NEWCASTLE_AIRPORT", "airport_power_and_incident_logs"): [
        real_src("newcastle_airport_statement", "status", "not_found"),
        real_src("newcastle_airport_statement", "event_visible", "text unrecoverable"),
        real_src("opensky_newcastle_airport_flights", "status", "blocked"),
        real_src(
            "opensky_newcastle_airport_flights",
            "event_visible",
            "You cannot access historical flights",
        ),
    ],
    ("HOSPITAL_TRUST", "site_electrical_records"): [
        real_src("esneft_ipswich_hospital_statement", "event_visible", "No times."),
        real_src(
            "esneft_ipswich_hospital_statement",
            "clock_basis",
            "datePublished 2019-08-10T10:09:37+00:00",
        ),
        raw_src("RAW-ESNEFT", "which runs Ipswich Hospital", "statement"),
    ],
    ("WATER_COMPANY", "pumping_station_and_treatment_works_logs"): [
        real_src("water_company_statements_9aug2019", "status", "not_found"),
        real_src(
            "water_company_statements_9aug2019",
            "event_visible",
            "None. Only anonymised E3C figures",
        ),
    ],
    ("REFINERY_OPERATOR", "site_trip_and_shutdown_logs"): [
        real_src(
            "stanlow_12sep2019_power_cut_article",
            "event_visible",
            "E3C/Ofgem do not name the 9 Aug refinery.",
        ),
    ],
}
NOT_HELD_NOTE = (
    "Every not_held message says only that the item is not held in this evidence pack and was "
    "not obtained, plus what its recorded basis states; it never claims that a record does not "
    "exist. An empty basis records that the item is absent from the published sources and from "
    "the real-data search (no source lists it). No entry is 'refused': no published source "
    "records a refusal."
)
