"""Registry of the real public sources used by R09, R11 and R12 of the full-investigation bundle.

Builder-only. ``rel`` is relative to ``GB_REAL_DATA_DIR``; ``sha256`` is the hash of that file as
held in ``.context/real_data`` (verified on 2026-10-20 by the real-data verification pass). The
builder accepts either that exact file or the mirror copy recorded in
``builder/full_investigation/raw/RAW_MANIFEST.json``. ``mirror`` says how the mirror was made:

* ``copy`` - byte-identical copy;
* ``slice`` - the same file format with only the rows the builder uses (``slice_rule``);
* ``extract`` - a different format holding only what the builder reads, at ``mirror_rel``
  (``extract_rule``); used for the Network Rail glossary workbook and explanation PDF, which the
  builder cannot otherwise read without a third-party library;
* ``none`` - not openly licensed, or used only to check quotations: never copied.

Licence texts are those quoted in ``.context/real_data/REAL_DATA.md`` and the consequences
catalogue (``.context/real_data/consequences/catalogue.json``).
"""

from __future__ import annotations

from typing import Any

ELEXON_LICENCE = (
    "Elexon BMRS open data licence: 'Elexon Limited hereby grants You a worldwide, royalty-free, "
    "perpetual, non-exclusive licence to Use the BMRS Data subject to the conditions below.' "
    "Required attribution: 'Contains BMRS data (c) Elexon Limited copyright and database right "
    "[year].' Excludes 'third party rights that Elexon is not authorised to licence'; REMIT "
    "message content is written by the market participant. (https://www.elexon.co.uk/bsc/data/"
    "balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/, checked 2026-10-20)"
)
ELEXON_LICENCE_SHORT = "Elexon BMRS open data licence (attribution required)"
ELEXON_ATTRIBUTION = (
    "Contains BMRS data (c) Elexon Limited copyright and database right 2026."
)
OGL = "Open Government Licence v3.0"
NR_LICENCE = (
    "Open Government Licence. Network Rail 'Our information and data' page: 'The information "
    "supplied to you through these pages and our Freedom of Information (FOI) and Environmental "
    "Information Regulation (EIR) responses is done so under the Open Government Licence.' "
    "(checked 2026-10-20)"
)
NR_ATTRIBUTION = (
    "Contains public sector information licensed under the Open Government Licence v3.0 "
    "(Network Rail)."
)
NR_LANDING = (
    "https://www.networkrail.co.uk/who-we-are/transparency-and-ethics/transparency/"
    "our-information-and-data/"
)
ORR_LICENCE = (
    "Open Government Licence v3.0 - orr.gov.uk footer: 'All content is available under the "
    "Open Government Licence v3.0, except where otherwise stated' (the data-portal page itself "
    "carries no licence text; checked 2026-10-20)"
)
ORR_ATTRIBUTION = (
    "Contains public sector information licensed under the Open Government Licence v3.0 "
    "(Office of Rail and Road)."
)
GOVUK_LICENCE = (
    "Open Government Licence v3.0 - GOV.UK: 'All content is available under the Open "
    "Government Licence v3.0, except where otherwise stated' (checked 2026-10-20)"
)
OFGEM_LICENCE = (
    "Ofgem copyright page (https://www.ofgem.gov.uk/copyright, checked 2026-10-20): 'Material "
    "featured on this website is subject to Crown copyright protection unless otherwise "
    "indicated. You may use Crown copyright information (not including logos) free of charge in "
    "any format or medium, under the terms of the Open Government Licence.' Third-party material "
    "excluded."
)
NOT_OPEN_POSTS = (
    "Post content (c) the account holders under the platform's terms; Internet Archive Wayback "
    "captures used for research access. Not an open licence: post text is neither reproduced nor "
    "closely paraphrased; only times, identifiers and short gists written for this record."
)
NOT_OPEN_WEB = (
    "Website terms of the publisher; no open licence stated. Text is neither reproduced nor "
    "closely paraphrased; only titles, dates, displayed times and short gists written for this "
    "record."
)

API = "https://data.elexon.co.uk/bmrs/api/v1"
WAYBACK = "https://web.archive.org/web"


def _remit_url(ids: list[int]) -> str:
    return f"{API}/remit?" + "&".join(f"messageId={i}" for i in ids) + "&format=json"


REMIT_IDS_1 = [
    273052, 273766, 273818, 274030, 274528, 274996, 275043, 275065, 275326, 275457, 275546,
    276129, 276553, 276740, 276753, 276792, 276823, 277291, 277570, 277837, 277912, 278234,
    278395, 278557, 278596, 278786, 329255, 366818,
]  # fmt: skip
REMIT_IDS_2 = [
    273712, 273765, 274535, 275521, 275526, 276167, 276953, 278099, 278222, 278262, 280952,
    290135, 292390, 299372, 301896, 304647, 306011, 322975, 323522,
]  # fmt: skip

NESO_STATEMENTS_DIR = "neso/datasets/neso_news_statements_aug2019/raw_text"
NESO_WEB_LICENCE = (
    "NESO website Terms and Conditions (not an open licence): 'NESO owns the intellectual "
    "property rights in the content published on the Website ... you may make a print copy of "
    "such parts of the Website ... as you may reasonably require for your own personal use'. Text "
    "is neither reproduced nor closely paraphrased; only page titles, dates and short gists "
    "written for this record."
)


def _neso(slug: str, sha256: str, retrieved: str, title: str) -> dict[str, Any]:
    return {
        "rel": f"{NESO_STATEMENTS_DIR}/{slug}.txt",
        "sha256": sha256,
        "dataset_id": "neso_news_statements_aug2019",
        "publisher": "National Grid ESO (pages now hosted on neso.energy/news)",
        "title": title,
        "url": f"https://www.neso.energy/news/{slug}",
        "retrieved_utc": retrieved,
        "licence": "NESO website terms (not an open licence)",
        "licence_text": NESO_WEB_LICENCE,
        "attribution": "",
        "mirror": "none",
        "format": "plain-text extract of the HTML page written by the real-data pass "
        "(header lines SOURCE_URL, HTTP, HTML_SHA256, HTML_BYTES, RETRIEVED_UTC, META)",
    }


SOURCES: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------ Elexon REMIT (open)
    "elexon_remit_details_1": {
        "rel": "elexon/raw/REMIT_revision_details_selected.json",
        "sha256": "4f6393bea04457742009ec0358b09e898dcb3958c0529d5e396dd65b13dbdbcb",
        "dataset_id": "elexon_REMIT",
        "publisher": "Elexon Limited (Insights REMIT platform); messages written by the market "
        "participants (Orsted DONG013, RWE INNOGY01, Drax)",
        "title": "REMIT messages retrieved by message ID (batch 1 of 2)",
        "url": _remit_url(REMIT_IDS_1),
        "retrieved_utc": "2026-10-20T06:46:31Z",
        "licence": ELEXON_LICENCE_SHORT,
        "licence_text": ELEXON_LICENCE,
        "attribution": ELEXON_ATTRIBUTION,
        "mirror": "copy",
    },
    "elexon_remit_details_2": {
        "rel": "elexon/raw/REMIT_revision_details_selected_part2.json",
        "sha256": "ec6abbe7a4111b410a38167ab496b61027d5f2c1c6696c3fc7bd8e759f1418b0",
        "dataset_id": "elexon_REMIT",
        "publisher": "Elexon Limited (Insights REMIT platform); messages written by the market "
        "participants (Orsted DONG013, RWE INNOGY01)",
        "title": "REMIT messages retrieved by message ID (batch 2 of 2)",
        "url": _remit_url(REMIT_IDS_2),
        "retrieved_utc": "2026-10-20T06:50:06Z",
        "licence": ELEXON_LICENCE_SHORT,
        "licence_text": ELEXON_LICENCE,
        "attribution": ELEXON_ATTRIBUTION,
        "mirror": "copy",
    },
    # ------------------------------------------------------------------ Network Rail (OGL)
    "nr_delays_p05": {
        "rel": "consequences/raw/rail/networkrail_all_delays_201920_P05_slice_2019-08-09.csv.gz",
        "sha256": "e21711596a6195647fcf8fe6ce9f1b91557bfa7ac60a83d4bc9645de6b973e79",
        "dataset_id": "nr_historic_delay_attribution_201920_P05",
        "publisher": "Network Rail Infrastructure Ltd",
        "title": "All delays 2019-20 P5 (historic attributed delays, PSS extract; zip entry "
        "dated 2020-03-26), sliced by the real-data pass to rows whose origin_departure_date "
        "is 09-Aug-19 or whose incident_start_datetime falls on 09/08/2019 (24,734 rows, all "
        "40 columns)",
        "url": "https://www.networkrail.co.uk/wp-content/uploads/2020/04/All-delays-2019-20-P5.zip",
        "landing_page": NR_LANDING,
        "original_file_sha256": "901a546d5203b7509209015b9ed960c6cbae11aba39b293e12ff91d8ae70c159",
        "retrieved_utc": "2026-10-20T06:33:27Z",
        "licence": OGL,
        "licence_text": NR_LICENCE,
        "attribution": NR_ATTRIBUTION,
        "mirror": "slice",
        "slice_rule": "header plus the rows of the incidents selected for R11 (incident_reason "
        "XK, or resp_manager METR, with incident_start_datetime on 09/08/2019), lines copied "
        "unchanged in original order; gzip level 9, mtime 0",
    },
    "nr_glossary": {
        "rel": "consequences/raw/rail/networkrail_Historic-Delay-Attribution-Glossary_2021-08.xlsx",
        "sha256": "083eb7df58120c3f9ba9e28de9f0944f598a17d05c2efd5055a07ce8de6dcb6e",
        "dataset_id": "nr_historic_delay_attribution_201920_P05",
        "publisher": "Network Rail Infrastructure Ltd",
        "title": "Historic Delay Attribution Glossary (workbook, August 2021 edition; sheets "
        "Stanox Codes, Period Dates, Incident Reason, Responsible Manager, Performance Event "
        "Code, Operator Name)",
        "url": "not recorded by the real-data pass; published by Network Rail with the historic "
        f"delay files (landing page {NR_LANDING})",
        "landing_page": NR_LANDING,
        "retrieved_utc": "2026-10-20 (time not recorded)",
        "licence": OGL,
        "licence_text": NR_LICENCE,
        "attribution": NR_ATTRIBUTION,
        "mirror": "extract",
        "mirror_rel": "consequences/raw/rail/"
        "networkrail_Historic-Delay-Attribution-Glossary_2021-08.extract.json",
        "extract_rule": "JSON {sheet name: [row objects keyed by the sheet's header cells]} "
        "holding only the rows R11 uses: the Performance Event Code sheet in full, the period "
        "end-date rows of 2019/20, and the Incident Reason, Responsible Manager, Operator Name "
        "and Stanox Codes rows whose code occurs in the selected Network Rail rows; cell text "
        "unchanged",
    },
    "nr_explanation": {
        "rel": "consequences/raw/rail/networkrail_Explanation-of-historic-attributed-delays_2021-05.pdf",
        "sha256": "d698e994cf67c6a41fdcb21ab7ec51ea11756f1a1040d876e0df73febd159f02",
        "dataset_id": "nr_historic_delay_attribution_201920_P05",
        "publisher": "Network Rail Infrastructure Ltd",
        "title": "Explanation document: Historic attributed delays (2 pages, May 2021)",
        "url": "not recorded by the real-data pass; published by Network Rail with the historic "
        f"delay files (landing page {NR_LANDING})",
        "landing_page": NR_LANDING,
        "retrieved_utc": "2026-10-20 (time not recorded)",
        "licence": OGL,
        "licence_text": NR_LICENCE,
        "attribution": NR_ATTRIBUTION,
        "mirror": "extract",
        "mirror_rel": "consequences/raw/rail/"
        "networkrail_Explanation-of-historic-attributed-delays_2021-05.pdf.txt",
        "extract_rule": "page text extracted with PyMuPDF 1.26.5 (fitz, page.get_text()), "
        "each page preceded by a '=== page <n> ===' line; used only to verify the quotations in R11 (the "
        "builder environment has no PDF reader, so quotations are always checked against this "
        "extract, whose sha256 the raw mirror manifest records)",
    },
    # ------------------------------------------------------------------ ORR (OGL)
    "orr_3124": {
        "rel": "consequences/raw/rail/orr_3124_2019-20_P03-P07_slice.csv",
        "sha256": "f540e31992ad2c3fcdb6d5c3c3485f8694374d3b3d5ffbcd5c98f38a053d6c02",
        "dataset_id": "orr_passenger_performance_periodic_tables",
        "publisher": "Office of Rail and Road data portal (source: Network Rail)",
        "title": "Table 3124 - Trains planned and cancellations by operator (periodic), "
        "periods 03-07 of 2019-20 and period 05 of 2020-21",
        "url": "https://dataportal.orr.gov.uk/statistics/performance/passenger-rail-performance/"
        "table-3124-trains-planned-and-cancellations-by-operator-periodic/",
        "retrieved_utc": "2026-10-20T06:36:02Z",
        "licence": OGL,
        "licence_text": ORR_LICENCE,
        "attribution": ORR_ATTRIBUTION,
        "mirror": "copy",
        "format": "CSV written by the real-data pass from the table embedded in the "
        "data-portal page HTML",
    },
    "orr_3157a": {
        "rel": "consequences/raw/rail/orr_3157a_2019-20_P03-P07_slice.csv",
        "sha256": "eb05d72e595175bf691e2e02fbf0bda2f7cbf10552f4da539aee7ba47e985c16",
        "dataset_id": "orr_passenger_performance_periodic_tables",
        "publisher": "Office of Rail and Road data portal (source: Network Rail)",
        "title": "Table 3157a - Days of severe disruption, Great Britain (periodic), periods "
        "04-07 of 2019-20 and period 05 of 2020-21",
        "url": "https://dataportal.orr.gov.uk/statistics/performance/passenger-rail-performance/"
        "table-3157a-days-of-severe-disruption-great-britain-periodic/",
        "retrieved_utc": "2026-10-20T06:36:02Z",
        "licence": OGL,
        "licence_text": ORR_LICENCE,
        "attribution": ORR_ATTRIBUTION,
        "mirror": "copy",
    },
    "orr_3157b": {
        "rel": "consequences/raw/rail/orr_3157b_2019-20_P03-P07_slice.csv",
        "sha256": "b23ecca0ef3c74ceb210e5c5c5c504b97949c06b673ff479c37af5968d93dfbb",
        "dataset_id": "orr_passenger_performance_periodic_tables",
        "publisher": "Office of Rail and Road data portal (source: Network Rail)",
        "title": "Table 3157b - Days of severe disruption by sub-operator (periodic), periods "
        "03-07 of 2019-20 and period 05 of 2020-21",
        "url": "https://dataportal.orr.gov.uk/statistics/performance/passenger-rail-performance/"
        "table-3157b-days-of-severe-disruption-by-sub-operator-periodic/",
        "retrieved_utc": "2026-10-20T06:36:02Z",
        "licence": OGL,
        "licence_text": ORR_LICENCE,
        "attribution": ORR_ATTRIBUTION,
        "mirror": "copy",
    },
    # ------------------------------------------------------------------ GOV.UK and Ofgem (OGL)
    "govuk_beis_20190814": {
        "rel": "consequences/raw/comms/"
        "govuk_content_business-secretary-sets-out-scope-of-investigation-into-power-cuts.json",
        "sha256": "f62b358c1f6aac26a24cf95264131db8b8716a34b74277f61fe842d7b7463503",
        "dataset_id": "govuk_content_api_beis_e3c",
        "publisher": "Department for Business, Energy and Industrial Strategy (BEIS) via the "
        "GOV.UK Content API",
        "title": "Business Secretary sets out scope of investigation into power cuts (press "
        "release, first published 2019-08-14T11:15:35+01:00)",
        "url": "https://www.gov.uk/api/content/government/news/"
        "business-secretary-sets-out-scope-of-investigation-into-power-cuts",
        "retrieved_utc": "2026-10-20T06:37:42Z",
        "licence": OGL,
        "licence_text": GOVUK_LICENCE,
        "attribution": "Contains public sector information licensed under the Open "
        "Government Licence v3.0.",
        "mirror": "none",
        "format": "GOV.UK Content API JSON; quotations are checked in details.body with HTML "
        "tags removed",
    },
    "govuk_review_collection": {
        "rel": "consequences/raw/comms/govuk_content_great-britain-power-system-disruption-review.json",
        "sha256": "2d22d443449aade265716312479135d5e3bc441933d4796213429294b14cef0e",
        "dataset_id": "govuk_content_api_beis_e3c",
        "publisher": "BEIS / Energy Emergencies Executive Committee via the GOV.UK Content API",
        "title": "Great Britain power system disruption review (publication page; first "
        "published 2019-08-14T11:15:00+01:00, updated 2019-10-04 and 2020-01-03)",
        "url": "https://www.gov.uk/api/content/government/publications/"
        "great-britain-power-system-disruption-review",
        "retrieved_utc": "2026-10-20T06:37:42Z",
        "licence": OGL,
        "licence_text": GOVUK_LICENCE,
        "attribution": "Contains public sector information licensed under the Open "
        "Government Licence v3.0.",
        "mirror": "none",
        "format": "GOV.UK Content API JSON; quotations are checked in details.body with HTML "
        "tags removed",
    },
    "ofgem_pr_20190812": {
        "rel": "consequences/raw/docs/ofgem_pr_2019-08-12_timeline.html",
        "sha256": "418eb57db591f4738a6b5063a099da8bd7e5842ceb1d37eea612a34d905a2e48",
        "dataset_id": "ofgem_press_releases",
        "publisher": "Ofgem",
        "title": "Ofgem sets timeline for National Grid ESO report following UK power failures "
        "(press release, 12 August 2019)",
        "url": "https://www.ofgem.gov.uk/press-release/"
        "ofgem-sets-timeline-national-grid-eso-report-following-uk-power-failures",
        "retrieved_utc": "2026-10-20T06:55:14Z",
        "licence": OGL,
        "licence_text": OFGEM_LICENCE,
        "attribution": "Contains public sector information licensed under the Open "
        "Government Licence v3.0 (Ofgem).",
        "mirror": "none",
        "format": "HTML page; quotations are checked in the page text with tags removed",
    },
    "ofgem_pr_20190820": {
        "rel": "consequences/raw/docs/ofgem_pr_2019-08-20_launches_investigation.html",
        "sha256": "9e6f10313228c640d28c7742e1a93c6f4f17474ef7aff87e4019279403503818",
        "dataset_id": "ofgem_press_releases",
        "publisher": "Ofgem",
        "title": "Ofgem launches investigation into power cuts (press release, 20 August 2019)",
        "url": "https://www.ofgem.gov.uk/press-release/ofgem-launches-investigation-power-cuts",
        "retrieved_utc": "2026-10-20T06:55:14Z",
        "licence": OGL,
        "licence_text": OFGEM_LICENCE,
        "attribution": "Contains public sector information licensed under the Open "
        "Government Licence v3.0 (Ofgem).",
        "mirror": "none",
        "format": "HTML page; quotations are checked in the page text with tags removed",
    },
    # ------------------------------------------------------------------ not openly licensed
    "comms_timeline": {
        "rel": "consequences/derived/comms_timeline_uk_local.csv",
        "sha256": "0cebef87387a5112e65a6f81e7ce6c35a457feb49ea0c892bdce1a032a7de8f4",
        "dataset_id": "comms_timeline_uk_local",
        "publisher": "Derived by the real-data pass from archived posts, Wayback pages, GOV.UK "
        "and Ofgem (members of the public anonymised)",
        "title": "Merged communications timeline, 9 August 2019 - 3 January 2020 (UK local "
        "time; precision per row)",
        "url": "see source_url per row",
        "retrieved_utc": "2026-10-20 (derived file written by the real-data pass)",
        "licence": "derived; inherits the licences of its rows (posts not openly licensed)",
        "licence_text": NOT_OPEN_POSTS,
        "attribution": "",
        "mirror": "none",
    },
    "comms_posts_embedded": {
        "rel": "consequences/derived/comms_tweets_embedded_in_captures.csv",
        "sha256": "6173505dfe7df6dd1eff2489a8388d5805aaa4369eb86a08b6884d6bd448241a",
        "dataset_id": "archived_official_tweets_9_10_aug_2019",
        "publisher": "Derived by the real-data pass from Internet Archive Wayback captures "
        "(members of the public anonymised as public_user_NN, their post IDs redacted)",
        "title": "Posts embedded in archived captures (account, post ID, created time, text, "
        "capture file)",
        "url": f"{WAYBACK}/ (captures listed per row in found_in)",
        "retrieved_utc": "2026-10-20T06:46:49Z to 07:10Z",
        "licence": "not an open licence (post content (c) the account holders)",
        "licence_text": NOT_OPEN_POSTS,
        "attribution": "",
        "mirror": "none",
    },
    "comms_posts_index": {
        "rel": "consequences/derived/comms_archived_tweets_index.csv",
        "sha256": "328827f5f1f41fdb0b9dbb374dfd049d483ad8983532bcf323bcf2fd9a24b728",
        "dataset_id": "archived_official_tweets_9_10_aug_2019",
        "publisher": "Derived by the real-data pass from Internet Archive Wayback captures and "
        "publish.twitter.com oEmbed responses",
        "title": "Index of archived organisational posts (account, post ID, decoded time, "
        "capture, best available text, notes)",
        "url": f"{WAYBACK}/ (capture per row in wayback_capture)",
        "retrieved_utc": "2026-10-20T06:46:49Z to 07:10Z",
        "licence": "not an open licence (post content (c) the account holders)",
        "licence_text": NOT_OPEN_POSTS,
        "attribution": "",
        "mirror": "none",
    },
    "nre_incident_228430": {
        "rel": "consequences/raw/comms/wayback_20190809175638_nre_228430.html",
        "sha256": "a7a21796bc771b86255104a53594552ff9144cfd2cb827b4eb6779246fb1cd22",
        "dataset_id": "thameslink_nre_disruption_pages_wayback",
        "publisher": "National Rail Enquiries (Rail Delivery Group), via the Internet Archive",
        "title": "National Rail Enquiries service disruption page 228430 (capture "
        "2019-08-09T17:56:38Z)",
        "url": f"{WAYBACK}/20190809175638/https://www.nationalrail.co.uk/service_disruptions/"
        "228430.aspx",
        "retrieved_utc": "2026-10-20T06:57:50Z",
        "licence": "Rail Delivery Group website terms (not an open licence)",
        "licence_text": NOT_OPEN_WEB,
        "attribution": "",
        "mirror": "none",
    },
    "nre_today_20190810": {
        "rel": "consequences/raw/comms/wayback_20190810190551_nre_today.html",
        "sha256": "91e50247c48a31a416dec794b46722407d17dbdc33f6a18ddac2d1bfd36bb1a5",
        "dataset_id": "thameslink_nre_disruption_pages_wayback",
        "publisher": "National Rail Enquiries (Rail Delivery Group), via the Internet Archive",
        "title": "National Rail Enquiries 'today' service disruption page (capture "
        "2019-08-10T19:05:51Z)",
        "url": f"{WAYBACK}/20190810190551/https://www.nationalrail.co.uk/service_disruptions/"
        "today.aspx",
        "retrieved_utc": "2026-10-20T06:57:50Z",
        "licence": "Rail Delivery Group website terms (not an open licence)",
        "licence_text": NOT_OPEN_WEB,
        "attribution": "",
        "mirror": "none",
    },
    "esneft_statement": {
        "rel": "consequences/raw/docs/esneft_p8309.html",
        "sha256": "02701761f49099fd6f1fc124c61773d7bfc3204d6591f5ce51df1fc13fdccf0d",
        "dataset_id": "esneft_ipswich_hospital_statement",
        "publisher": "East Suffolk and North Essex NHS Foundation Trust",
        "title": "Major power cut across parts of England and Wales (press release page; "
        "schema.org datePublished 2019-08-10T10:09:37+00:00, dateModified "
        "2024-10-15T08:22:50+00:00)",
        "url": "https://www.esneft.nhs.uk/major-power-cut-across-parts-of-england-and-wales/",
        "retrieved_utc": "2026-10-20T06:50:54Z",
        "licence": "(c) ESNEFT website; no open licence stated",
        "licence_text": NOT_OPEN_WEB,
        "attribution": "",
        "mirror": "none",
    },
    "neso_statement_0908_1830": _neso(
        "power-cut-statement-9-august-630pm",
        "1374f750248c8eb6b2818d045f224bb656aa64bc20904c51dfa04dade3b5b704",
        "2026-10-20T06:45:39Z",
        "Power Cut Statement - 9 August, 6.30pm",
    ),
    "neso_statement_0908_2000": _neso(
        "power-cut-statement-9-august-8pm",
        "77748af33fd4e7a876c9dfb23d765f0a9bed117a00245816c57c9af41bdec080",
        "2026-10-20T06:45:41Z",
        "Power Cut Statement - 9 August, 8pm",
    ),
    "neso_statement_1008_0830": _neso(
        "power-cut-statement-10-august-830am",
        "94e9e1787074eeebb0a07d1684031c497c9c5e58235a93fcd671aaa68f3db154",
        "2026-10-20T06:45:43Z",
        "Power Cut Statement - 10 August, 8.30am",
    ),
    "neso_statement_1008_1930": _neso(
        "power-cut-statement-10-august-730pm",
        "652d74022f78b397fdcc612b5377841e98e035ecd43e26ce7abcb637880f4b4e",
        "2026-10-20T06:45:44Z",
        "Power Cut Statement - 10 August, 7.30pm",
    ),
    "neso_statement_1308": _neso(
        "power-cut-statement-frequency-13-august",
        "398b1b6e1e2c2c4b4ccfd7ca2467f7b67c2903dd46832a501bed3be75fe35cb3",
        "2026-10-20T06:45:46Z",
        "Power Cut Statement on Frequency - 13 August",
    ),
    "neso_statement_1608": _neso(
        "national-grid-eso-confirms-submission-interim-technical-report-power-outages-9th-"
        "august-ofgem",
        "23c48c087b56154a8c0d3010cb885a58bcd9c0f1c4c9f9bfc74bc86be4b359ae",
        "2026-10-20T06:45:49Z",
        "National Grid ESO confirms submission of interim technical report into the power "
        "outages of 9th August, to Ofgem",
    ),
    "neso_statement_1908": _neso(
        "interim-technical-report-power-outages-friday-9-august",
        "12e3d36c713dc050b83d4269d957a1c43820712f985ca0a9e7552c24d117dffb",
        "2026-10-20T06:45:48Z",
        "Interim technical report into the power outages of Friday 9 August",
    ),
}


def public_source(key: str) -> dict[str, Any]:
    """The provenance record of a source (``rel`` becomes ``file``; GB_REAL_DATA_DIR root)."""
    spec = SOURCES[key]
    out = {"kind": "dataset", "root": "GB_REAL_DATA_DIR", "file": spec["rel"]}
    for field in (
        "sha256",
        "dataset_id",
        "publisher",
        "title",
        "url",
        "landing_page",
        "original_file_sha256",
        "retrieved_utc",
        "licence",
        "licence_text",
        "attribution",
        "mirror",
        "mirror_rel",
        "slice_rule",
        "extract_rule",
        "format",
    ):
        if spec.get(field):
            out[field] = spec[field]
    return out
