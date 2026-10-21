"""Registry of the real public datasets used by R02, R04, R06 and R07.

Builder-only. ``rel`` is relative to ``GB_REAL_DATA_DIR``; ``sha256`` is the hash of that file as
held in ``.context/real_data`` (verified on 2026-10-20 by the real-data verification pass). The
builder accepts either that exact file or the mirror copy recorded in
``builder/system_response/raw/RAW_MANIFEST.json`` (``mirror`` says how the mirror was made).
Licence texts are summarised from the licence pages quoted in ``.context/real_data/REAL_DATA.md``.
"""

from __future__ import annotations

from typing import Any

ELEXON_LICENCE = (
    "Elexon BMRS open data licence: 'Elexon Limited hereby grants You a worldwide, royalty-free, "
    "perpetual, non-exclusive licence to Use the BMRS Data subject to the conditions below.' "
    "Required attribution: 'Contains BMRS data (c) Elexon Limited copyright and database right "
    "[year].' (https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/"
    "copyright-licence-bmrs-data/, checked 2026-10-20)"
)
ELEXON_LICENCE_SHORT = "Elexon BMRS open data licence (attribution required)"
ELEXON_ATTRIBUTION = (
    "Contains BMRS data (c) Elexon Limited copyright and database right 2026."
)
NESO_LICENCE = (
    "NESO Open Data Licence v1.0: 'The Licensor grants you a worldwide, royalty-free, perpetual, "
    "non-exclusive licence to use the Information subject to the conditions below'; attribution "
    "'Supported by National Energy SO Open Data'; licensed 'as is' "
    "(https://www.neso.energy/data-portal/neso-open-licence, checked 2026-10-20)"
)
NESO_LICENCE_SHORT = "NESO Open Data Licence v1.0 (attribution required)"
NESO_ATTRIBUTION = "Supported by National Energy SO Open Data."
IEM_LICENCE = (
    "Iowa Environmental Mesonet: 'The materials found on this website are in the public domain "
    "and may be used freely by anyone for any lawful purpose.' "
    "(https://mesonet.agron.iastate.edu/disclaimer.php, checked 2026-10-20)"
)
IEM_LICENCE_SHORT = (
    "public domain (Iowa Environmental Mesonet); attribution appreciated"
)
METOFFICE_LICENCE = (
    "Met Office website material is Crown copyright, licensed under the Open Government Licence "
    "v3.0 unless stated otherwise (https://www.metoffice.gov.uk/policies/legal, checked "
    "2026-10-20); page read from an Internet Archive capture."
)
METOFFICE_LICENCE_SHORT = "Open Government Licence v3.0 (Crown copyright, Met Office)"
METOFFICE_ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."

BOALF_SPS = tuple(range(32, 39))
B1610_UNITS = ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1")
MEL_UNITS = ("T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3", "T_LBAR-1", "T_LBAR-1G")


def _elexon(
    rel: str,
    sha256: str,
    dataset_id: str,
    title: str,
    url: str,
    retrieved: str,
    **extra: Any,
) -> dict[str, Any]:
    entry = {
        "rel": rel,
        "sha256": sha256,
        "dataset_id": dataset_id,
        "publisher": "Elexon Limited (BMRS / Insights API)",
        "title": title,
        "url": url,
        "retrieved_utc": retrieved,
        "licence": ELEXON_LICENCE_SHORT,
        "licence_text": ELEXON_LICENCE,
        "attribution": ELEXON_ATTRIBUTION,
        "mirror": "copy",
    }
    entry.update(extra)
    return entry


API = "https://data.elexon.co.uk/bmrs/api/v1"

SOURCES: dict[str, dict[str, Any]] = {
    "elexon_fuelinst": _elexon(
        "elexon/raw/FUELINST_20190809_1400_1900Z.json",
        "25aaa5e8f48a8a676d32c09e172dd62014b8ad1898b95f47d057ed90f7492d69",
        "elexon_FUELINST",
        "Instantaneous generation outturn by fuel type (FUELINST), 5-minute MW",
        f"{API}/datasets/FUELINST?publishDateTimeFrom=2019-08-09T14%3A00%3A00Z"
        "&publishDateTimeTo=2019-08-09T19%3A00%3A00Z&format=json",
        "2026-10-20T06:40:34Z",
    ),
    "elexon_fuelhh": _elexon(
        "elexon/raw/FUELHH_20190809.json",
        "3974b5d1191ba321801f8df2e0f8581bc8fbf4ae6f1a2e8c1e83935b4ab4041d",
        "elexon_FUELHH",
        "Half-hourly generation outturn by fuel type (FUELHH)",
        f"{API}/datasets/FUELHH?settlementDateFrom=2019-08-09&settlementDateTo=2019-08-09"
        "&format=json",
        "2026-10-20T06:40:36Z",
    ),
    "elexon_indo_itsdo": _elexon(
        "elexon/raw/demand_outturn_INDO_ITSDO_20190809.json",
        "cbd9555f6c0c9d03e8bd1a7c5305283cfda51c1e0c2f9013e7546112e3e131b0",
        "elexon_INDO_ITSDO",
        "Initial National Demand Outturn (INDO) and Initial Transmission System Demand "
        "Outturn (ITSDO)",
        f"{API}/demand/outturn?settlementDateFrom=2019-08-09&settlementDateTo=2019-08-09"
        "&format=json",
        "2026-10-20T06:41:03Z",
    ),
    "elexon_lolpdrm": _elexon(
        "elexon/raw/LOLPDRM_2019-08-09.json",
        "9a6ab29cab3543a43239d59b12a5d177e937803b0151a4dd60da1cfd163be043",
        "elexon_LOLPDRM_MID",
        "Loss of load probability and de-rated margin forecast (LOLPDRM)",
        f"{API}/forecast/system/loss-of-load?from=2019-08-08T23%3A00%3A00Z"
        "&to=2019-08-09T23%3A00%3A00Z&format=json",
        "2026-10-20T06:43:01Z",
    ),
    "elexon_ref_bmunits": _elexon(
        "elexon/raw/ref_bmunits_all.json.gz",
        "9ebb42fcd3496c2bd5963ee867ef3885bff9d1e3c2299dc0262b962eb999fabc",
        "elexon_ref_bmunits",
        "BM Unit reference list (all BM units; current registration data)",
        f"{API}/reference/bmunits/all",
        "2026-10-20T06:40:26Z",
        body_sha256="65b690aeed0cf844ff4b321926ed665dd3810e5f101b6e5f50da009b15a7d4dc",
        mirror="slice",
        slice_rule="JSON list filtered to elexonBmUnit in T_HOWAO-1, T_HOWAO-2, T_HOWAO-3, "
        "T_LBAR-1, T_LBAR-1G (original order and fields kept); gzip level 9, mtime 0",
    ),
    "elexon_qas": _elexon(
        "verifier_additions/raw/elexon_QAS_2019-08-09_SP1-50.json",
        "a97f69eaad2c4ee0d8660a096b35acca3ff9de7e5d2492d0a1d462a66b8c1a18",
        "elexon_QAS_balancing_services_volume",
        "Balancing Services Volume (QAS) per BM unit per settlement period, 9 August 2019",
        f"{API}/datasets/QAS?from=2019-08-09&to=2019-08-09&settlementPeriodFrom=1"
        "&settlementPeriodTo=50&format=json",
        "2026-10-20T07:40:26Z",
    ),
    "elexon_disebsp": _elexon(
        "elexon/raw/DISEBSP_system_prices_2019-08-09.json",
        "b7f15bd6773c35455beb57b3182fb83573988d805b3717f0f584c93289b82587",
        "elexon_DISEBSP_NIV",
        "Settlement system prices and net imbalance volume (DISEBSP), 9 August 2019",
        f"{API}/balancing/settlement/system-prices/2019-08-09?format=json",
        "2026-10-20T06:42:20Z",
    ),
    "elexon_dci": _elexon(
        "elexon/raw/DCI_201908.json",
        "6551ef66f2ca42205a7b1195524ed61ad76d077c5571131a9ff5fa3ac681ebf2",
        "elexon_DCI",
        "Demand control instructions (DCI), August 2019",
        f"{API}/system/demand-control-instructions?from=2019-08-01T00%3A00%3A00Z"
        "&to=2019-08-31T00%3A00%3A00Z&format=json",
        "2026-10-20T06:49:14Z",
    ),
    "elexon_demand_summary": _elexon(
        "elexon/raw/demand_outturn_summary_20190809.json",
        "578e4756b5b6b2479f7b042eb2d22a040c5f3d37d730ecb0f70e7f41021573cc",
        "elexon_demand_outturn_summary_5min",
        "System demand summary (FUELINST), 5-minute resolution",
        f"{API}/demand/outturn/summary?resolution=minute&from=2019-08-09T14%3A00%3A00Z"
        "&to=2019-08-09T19%3A00%3A00Z&format=json",
        "2026-10-20T06:40:39Z",
    ),
    "elexon_api_docs": _elexon(
        "verification/elexon_swagger_v1.json",
        "7710bb452e47e448dad8b978a0313d9bf127a6faa0c2b623891ff281f807101a",
        "elexon_api_openapi_document",
        "Elexon Insights API OpenAPI document (title 'Insights.Api', version 1.0; server "
        f"{API}); endpoint descriptions",
        "not recorded in the real-data manifest (OpenAPI document of the server above)",
        "2026-10-20 (file written by the real-data verification pass; time not recorded)",
        mirror="none",
        licence="Elexon API documentation; publisher's terms (no separate open licence stated "
        "for the document; used only to check quotations)",
        licence_text="The BMRS open data licence covers BMRS data; no licence statement for the "
        "OpenAPI document itself was recorded, so it is not mirrored.",
        attribution="",
    ),
    "neso_historic_demand": {
        "rel": "neso/datasets/neso_historic_demand_2019/demanddata_2019.csv",
        "sha256": "0084d546dcdba0af21b7414f1a1b0ab308a9de8460884aa8e550fd0e858b38da",
        "dataset_id": "neso_historic_demand_2019",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "Historic Demand Data 2019 (demanddata_2019.csv)",
        "url": "https://api.neso.energy/dataset/8f2fe0af-871c-488d-8bad-960426f24601/resource/"
        "dd9de980-d724-415a-b344-d8ae11321432/download/demanddata_2019.csv",
        "retrieved_utc": "2026-10-20T06:33:21Z",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "slice",
        "slice_rule": "header line plus the lines whose SETTLEMENT_DATE is 08-AUG-2019, "
        "09-AUG-2019 or 10-AUG-2019, copied byte for byte (CRLF kept)",
    },
    "neso_inertia": {
        "rel": "neso/datasets/neso_system_inertia_2019_2020/inertia.csv",
        "sha256": "e87f9dba11e7feb9ae9c7af64a18c9a909ffde1006b6d3b1224999d2b8704c45",
        "dataset_id": "neso_system_inertia_2019_2020",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "GB System Inertia 2019-2020 (inertia.csv)",
        "url": "https://api.neso.energy/dataset/8f3cd0ce-6636-469e-b582-55eadfeaa1d9/resource/"
        "2f2dbaa1-3047-4e48-85f2-ec24e669678f/download/inertia.csv",
        "retrieved_utc": "2026-10-20T06:34:38Z",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "slice",
        "slice_rule": "header line plus the lines whose Settlement Date is 2019-08-08, "
        "2019-08-09 or 2019-08-10, copied byte for byte (CRLF kept)",
    },
    "neso_demand_faq_docx": {
        "rel": "neso/datasets/neso_historic_demand_2019/doc_faq-neso.docx",
        "sha256": "39ecfdf2774712a5317c7c5de995bee26ac653cc44bd008a82dcf234e0b4935a",
        "dataset_id": "neso_historic_demand_2019",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "Historic Demand Data: Frequently Asked Questions (faq-neso.docx)",
        "url": "https://api.neso.energy/dataset/8f2fe0af-871c-488d-8bad-960426f24601/resource/"
        "243ca76a-eefe-419d-a4b5-397073deb100/download/faq-neso.docx",
        "retrieved_utc": "2026-10-20T06:41:46Z",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "none",
    },
    "neso_embedded_definition_docx": {
        "rel": "neso/datasets/neso_embedded_wind_solar_forecast_archive_2019/"
        "doc_definition-of-embedded.docx",
        "sha256": "e8d4b974d5e3b32415eb66d2306108e56e44c4eb2521fcaadcbc5c647a37bdf7",
        "dataset_id": "neso_embedded_wind_solar_forecast_archive_2019",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "Definition of embedded (definition-of-embedded.docx)",
        "url": "https://api.neso.energy/dataset/91c0c70e-0ef5-4116-b6fa-7ad084b5e0e8/resource/"
        "3808c680-b5c0-4eab-aac4-7abb6345e65b/download/definition-of-embedded.docx",
        "retrieved_utc": "2026-10-20T06:41:51Z",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "none",
    },
    "neso_demand_resource": {
        "rel": "neso/datasets/neso_historic_demand_2019/resource_show.json",
        "sha256": "d599f6d4563c80f697020b36ff134e36def4edd59324bc4ebab0b3fda282e21c",
        "dataset_id": "neso_historic_demand_2019",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "Portal resource record (resource_show) of Historic Demand Data 2019",
        "url": "https://api.neso.energy/api/3/action/resource_show?id="
        "dd9de980-d724-415a-b344-d8ae11321432",
        "retrieved_utc": "2026-10-20 (fetched with the dataset; exact time not recorded)",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "copy",
    },
    "neso_inertia_resource": {
        "rel": "neso/datasets/neso_system_inertia_2019_2020/resource_show.json",
        "sha256": "4dbac9efa1b5debdf8f3dc9171d7e47f28f84d5d32367b916476462774dd4a5b",
        "dataset_id": "neso_system_inertia_2019_2020",
        "publisher": "National Energy System Operator (NESO) open data portal",
        "title": "Portal resource record (resource_show) of GB System Inertia - 2019-2020",
        "url": "https://api.neso.energy/api/3/action/resource_show?id="
        "2f2dbaa1-3047-4e48-85f2-ec24e669678f",
        "retrieved_utc": "2026-10-20 (fetched with the dataset; exact time not recorded)",
        "licence": NESO_LICENCE_SHORT,
        "licence_text": NESO_LICENCE,
        "attribution": NESO_ATTRIBUTION,
        "mirror": "copy",
    },
    "consequences_comms_timeline": {
        "rel": "consequences/derived/comms_timeline_uk_local.csv",
        "sha256": "0cebef87387a5112e65a6f81e7ce6c35a457feb49ea0c892bdce1a032a7de8f4",
        "dataset_id": "comms_timeline_uk_local",
        "publisher": "Derived by the real-data pass from archived public posts (Internet Archive "
        "captures), GOV.UK and Ofgem pages",
        "title": "Communications timeline 9-10 August 2019 (UK local time)",
        "url": "derived file; each row names its archived source URL",
        "retrieved_utc": "2026-10-20",
        "licence": "derived; inherits source licences per row (post text: account holders' "
        "copyright under platform terms, not an open licence)",
        "licence_text": "Tweet content (c) account holders under X/Twitter terms; Wayback captures "
        "for research access - not an open licence (real-data manifest record "
        "archived_official_tweets_9_10_aug_2019)",
        "attribution": "",
        "mirror": "none",
    },
    "iem_metar": {
        "rel": "research_pmu_lightning/IEM_METAR_SE_England_airports_20190809_1200-2000UTC.csv",
        "sha256": "18d92b7e4d1a593a39d8cb9e82a7ad6b486e4b576e1934812d9eceb7eca51ef0",
        "dataset_id": "iem_metar_se_england_20190809",
        "publisher": "Iowa Environmental Mesonet, Iowa State University (ASOS/METAR archive); "
        "reports originate from UK aerodromes",
        "title": "METAR reports for south-east England aerodromes, 2019-08-09 12:00-20:00 UTC",
        "url": "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=EGGW"
        "&station=EGSC&station=EGSS&station=EGTC&station=EGUY&station=EGLL&station=EGLC"
        "&station=EGWU&station=EGVN&data=metar&data=wxcodes&data=tmpc&data=sknt&data=gust"
        "&data=p01m&year1=2019&month1=8&day1=9&hour1=12&minute1=0&year2=2019&month2=8&day2=9"
        "&hour2=20&minute2=0&tz=Etc%2FUTC&format=onlycomma&latlon=yes&elev=no&missing=M"
        "&trace=T&direct=no&report_type=3&report_type=4",
        "retrieved_utc": "2026-10-20T06:45:09Z",
        "licence": IEM_LICENCE_SHORT,
        "licence_text": IEM_LICENCE,
        "attribution": "Data from the Iowa Environmental Mesonet, Iowa State University.",
        "mirror": "copy",
    },
    "metoffice_warnings_text": {
        "rel": "research_pmu_lightning/"
        "MetOffice_uk-warnings_wayback_20190809T160223Z_extracted_text.txt",
        "sha256": "276a18a17066ed36537573209f29c6b88f0be800edcc82e820042ddfa47ea22c",
        "dataset_id": "metoffice_uk_warnings_wayback_20190809",
        "publisher": "Met Office (UK weather warnings page), archived by the Internet Archive",
        "title": "Text extracted from the Met Office UK weather warnings page, Internet Archive "
        "capture 2019-08-09T16:02:23Z",
        "url": "https://web.archive.org/web/20190809160223id_/https://www.metoffice.gov.uk/"
        "weather/warnings-and-advice/uk-warnings",
        "retrieved_utc": "2026-10-20T06:48:15Z",
        "licence": METOFFICE_LICENCE_SHORT,
        "licence_text": METOFFICE_LICENCE,
        "attribution": METOFFICE_ATTRIBUTION,
        "mirror": "copy",
        "derived_from": {
            "rel": "research_pmu_lightning/MetOffice_uk-warnings_wayback_20190809T160223Z.html",
            "sha256": "9db9d96804f0e858261019d816219134edc82f3b71f33640fe094c164577e703",
            "note": "page HTML as captured; the text file is the real-data pass's text "
            "extraction of this HTML",
        },
    },
}

for _unit in B1610_UNITS:
    SOURCES[f"elexon_b1610_{_unit}"] = _elexon(
        f"elexon/raw/B1610_stream_{_unit}_2019-08-09.json",
        {
            "T_HOWAO-1": "044a6133a678efc7619a1d01b60cc7320c14a0489ca3ee374f5a3849823c10b2",
            "T_HOWAO-2": "ffbcd6a754133875a3badd89a4c8d9440b4aceab1e3ae95e2c30b0c628c3b28c",
            "T_HOWAO-3": "076a1d7073b9062a55766e1a9565b90cb7a4f1bc13ab8bfe5fc0a2e03c339414",
            "T_LBAR-1": "5c7dd74e693949453a9f28ae11b4062ac8857ed6b7744978dd6eacb5311c8da7",
        }[_unit],
        "elexon_B1610",
        f"Actual generation output per generation unit (B1610) stream, {_unit}",
        f"{API}/datasets/B1610/stream?from=2019-08-08T23%3A00%3A00Z&to=2019-08-09T23%3A00%3A00Z"
        f"&bmUnit={_unit}",
        {
            "T_HOWAO-1": "2026-10-20T06:49:37Z",
            "T_HOWAO-2": "2026-10-20T06:49:41Z",
            "T_HOWAO-3": "2026-10-20T06:49:42Z",
            "T_LBAR-1": "2026-10-20T06:49:43Z",
        }[_unit],
    )

for _unit in MEL_UNITS:
    SOURCES[f"elexon_physical_{_unit}"] = _elexon(
        f"elexon/raw/PHYSICAL_{_unit}_2019-08-09.json",
        {
            "T_HOWAO-1": "f9a82958bd87dc86968a3a48d9cd0e7a1ec117641bc423980302b395296818be",
            "T_HOWAO-2": "4d88ab4e3b557fb5feb22101d4f4f40956ace6db40ccdf2d402d4f2ea77cbe4c",
            "T_HOWAO-3": "6d9d9b6ce81538bd9dac9ae875064422c48a77e6879e0d60c3b96773d4accfc3",
            "T_LBAR-1": "8409618a392d05e8530c814c88ccf916a1003d4d7324a25c5bf34ba613c53cb8",
            "T_LBAR-1G": "2671fc8210d52df4dd0cb7079f468c949c1d9dc9654f541857ca0208e8dfe7b5",
        }[_unit],
        "elexon_PHYSICAL_MELS_MILS",
        f"Physical data per BM unit (PN, QPN, MILS, MELS), {_unit}",
        f"{API}/balancing/physical?bmUnit={_unit}&from=2019-08-08T23%3A00%3A00Z"
        "&to=2019-08-09T23%3A00%3A00Z&format=json",
        {
            "T_HOWAO-1": "2026-10-20T06:41:34Z",
            "T_HOWAO-2": "2026-10-20T06:41:41Z",
            "T_HOWAO-3": "2026-10-20T06:41:48Z",
            "T_LBAR-1": "2026-10-20T06:41:53Z",
            "T_LBAR-1G": "2026-10-20T06:42:02Z",
        }[_unit],
    )

_BOALF_SHA = {
    32: "313e28775a956f863bd27e8b7f6ec17ebaa27e5583d7066bbfe19cd0b273ec9f",
    33: "96aa5db5445bc957df9d1742925f7625125a4bc32087c6842c08f8b50e0da01c",
    34: "261c3c9a6438f0efc698d6edf5dcaacaff7c17649e5045c2d44cdba55072cc93",
    35: "57c713b1dc8b8fc1c3bdf5ec1532e2551ea8b25933e6c312c9ae16673cd4d6d2",
    36: "c0149de56dd97d6038b03fb1457df9213cc2957864bab48b12aadbc03fee690c",
    37: "67ae03025af218fedc11dc1a5f8a5e754fc7bb4a39b5413f45b244ce67bed2bf",
    38: "e49b70915da6237770653d90fb83ffcef1cd8faab5e6b5a5961c3a733f32ebba",
}
_BOALF_RETRIEVED = {
    32: "2026-10-20T06:41:20Z",
    33: "2026-10-20T06:41:22Z",
    34: "2026-10-20T06:41:25Z",
    35: "2026-10-20T06:41:27Z",
    36: "2026-10-20T06:41:27Z",
    37: "2026-10-20T06:41:30Z",
    38: "2026-10-20T06:41:31Z",
}
for _sp in BOALF_SPS:
    SOURCES[f"elexon_boalf_sp{_sp}"] = _elexon(
        f"elexon/raw/BOALF_all_2019-08-09_SP{_sp}.json",
        _BOALF_SHA[_sp],
        "elexon_BOALF",
        f"Market-wide bid-offer acceptances (BOALF), settlement date 2019-08-09, period {_sp}",
        f"{API}/balancing/acceptances/all?settlementDate=2019-08-09&settlementPeriod={_sp}"
        "&format=json",
        _BOALF_RETRIEVED[_sp],
    )


def public_source(key: str) -> dict[str, Any]:
    """Source metadata written to private provenance (no local absolute paths)."""
    spec = SOURCES[key]
    keep = (
        "dataset_id",
        "publisher",
        "title",
        "url",
        "retrieved_utc",
        "licence",
        "licence_text",
        "attribution",
        "rel",
        "sha256",
        "body_sha256",
        "mirror",
        "slice_rule",
        "derived_from",
    )
    out = {k: spec[k] for k in keep if k in spec}
    out["kind"] = "dataset"
    out["file"] = out.pop("rel")
    out["root"] = "GB_REAL_DATA_DIR"
    return out
