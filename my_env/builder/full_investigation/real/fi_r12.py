"""R12 — essential-service public statements, 9-10 August 2019.

Builder-only. Public statements by essential-service operators found by the real-data pass:

* the East Suffolk and North Essex NHS Foundation Trust (Ipswich Hospital) press release of
  10 August 2019 (not openly licensed: the record gives its publication details and a short
  gist written for this record, never its text; no personal names);
* two Newcastle International Airport posts of 9 August 2019 whose text is not recoverable from
  the archived captures (only their identifiers and decoded times are known).

No water company or refinery statement was found; the 12 September 2019 Stanlow refinery
article is a different event and is not licensed for reuse, so it is excluded (private
provenance). Nothing is synthesised.
"""

from __future__ import annotations

import csv
import io

from fi_docbuild import LABEL_REAL, Artifact, FiDocBuild
from fi_real_common import (
    BUILDER,
    FiInputs,
    TextDoc,
    csv_bytes,
    data_ref,
    gist_ref,
    post_time,
    quote_ref,
    raw_quote_ref,
    require,
    tagged,
    utc_z,
    wrap,
)

DOC_ID = "R12"
TITLE = "Essential-service public statements, 9-10 August 2019"
F_STATEMENTS = "R12_essential_service_public_statements.csv"

ESNEFT_GIST = (
    "statement attributed to the trust's managing director, the day after the event: the "
    "national power cut caused a small electrical problem at Ipswich Hospital; its emergency "
    "generators all operated, but one circuit breaker serving outpatients failed to, so the "
    "X-ray department and outpatients briefly lost supply; business continuity arrangements were "
    "invoked and the problem was soon resolved; no other part of the hospital was affected."
)
ESNEFT_TITLE = "Major power cut across parts of England and Wales"
ESNEFT_PUBLISHED = "2019-08-10T10:09:37+00:00"
ESNEFT_MODIFIED = "2024-10-15T08:22:50+00:00"
ESNEFT_PAGE_DATE = "10/08/2019"

AIRPORT_POSTS = (1159869406102425601, 1159871147980328960)
AIRPORT_CAPTURES = {
    1159869406102425601: "https://web.archive.org/web/20190810033039/https://twitter.com/"
    "NCLairport/status/1159869406102425601?ref_src=twsrc%5Etfw",
    1159871147980328960: "https://web.archive.org/web/20220728215944/https://twitter.com/"
    "NCLairport/status/1159871147980328960?ref_src=twsrc%5Etfw",
}


def p(label: str, text: str) -> list[str]:
    return wrap(text, first=f"{label:<4}", indent="    ")


def cont(text: str) -> list[str]:
    return wrap(text, first="    ", indent="    ")


def _esneft_statement(inputs: FiInputs) -> str | None:
    """The statement paragraph of the press release (for the gist check only)."""
    text = inputs.source_text("esneft_statement")
    if text is None:
        return None
    start = text.find("Yesterday evening")
    end = text.find("reassured throughout the evening")
    require(0 <= start < end, "ESNEFT statement paragraph not found")
    return text[start : end + len("reassured throughout the evening")]


def _check_airport_posts(inputs: FiInputs) -> None:
    raw = inputs.optional_real_bytes("comms_posts_index")
    if raw is None:
        return
    rows = {r["tweet_id"]: r for r in csv.DictReader(io.StringIO(raw.decode("utf-8")))}
    for post_id in AIRPORT_POSTS:
        row = rows.get(str(post_id))
        require(row is not None, f"airport post {post_id} not in the index")
        require(
            row["wayback_capture"] == AIRPORT_CAPTURES[post_id], "capture URL changed"
        )
        require(not row["best_text"].strip(), f"post {post_id} has text after all")
        require(
            row["created_utc_snowflake"]
            == utc_z(post_time(post_id)).replace("Z", "+00:00"),
            f"post {post_id}: decoded time differs",
        )


def build(inputs: FiInputs) -> FiDocBuild:
    doc = TextDoc(DOC_ID)
    build = FiDocBuild(
        doc_id=DOC_ID,
        title=TITLE,
        owner="East Suffolk and North Essex NHS Foundation Trust (Ipswich Hospital); Newcastle "
        "International Airport (public posts)",
        category="essential_service_records",
        record_type="public statements by essential-service operators: publication details "
        "and a short summary written for this record (statement text not reproduced), and the "
        "identifiers and decoded times of posts whose text is not recoverable",
        construction="",
        text=doc,
        label=LABEL_REAL,
        status_scope="Part A is not a transcription: it gives the statement's publication "
        "details and a short summary written for this record; the statement text is not "
        "reproduced. Nothing in this record is synthesised.",
        party_aliases=["hospital", "airport", "essential services", "NHS trust"],
    )
    build.header(
        "East Suffolk and North Essex NHS Foundation Trust (press release page); Newcastle "
        "International Airport (public social-media posts located in Internet Archive "
        "captures)",
        wrap(
            "Clock reference: the trust's page displays a date only; the page's embedded "
            "metadata gives publication and modification times in UTC (+00:00). Post times "
            "in Part B are UTC, decoded from the post identifiers."
        ),
    )

    # ---- Part A ------------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part A heading",
        "PART A — HOSPITAL TRUST STATEMENT (publication details real; summary written for this "
        "record)",
    )
    statement = _esneft_statement(inputs)
    seg = doc.segment(
        "A1 ESNEFT press release: publication details and gist",
        "reported",
        "paraphrase",
        [
            quote_ref(
                inputs,
                "esneft_statement",
                "page title",
                ESNEFT_TITLE,
            ),
            quote_ref(
                inputs, "esneft_statement", "displayed page date", ESNEFT_PAGE_DATE
            ),
            raw_quote_ref(
                inputs,
                "esneft_statement",
                "schema.org metadata",
                f'"datePublished":"{ESNEFT_PUBLISHED}"',
            ),
            raw_quote_ref(
                inputs,
                "esneft_statement",
                "schema.org metadata",
                f'"dateModified":"{ESNEFT_MODIFIED}"',
            ),
            gist_ref(
                inputs,
                "esneft_statement",
                ESNEFT_GIST,
                original=statement,
                note="statement paragraph of the press release; the speaker's name is omitted",
            ),
        ],
        "Publication details copied; statement summarised in builder wording (no run of more "
        "than three consecutive words shared with the statement); personal name omitted.",
    )
    doc.add(
        seg,
        *p(
            "A1",
            "East Suffolk and North Essex NHS Foundation Trust (the trust that runs Ipswich "
            f"Hospital), press release '{ESNEFT_TITLE}'. Page date displayed: "
            f"{ESNEFT_PAGE_DATE}. Page metadata: published {ESNEFT_PUBLISHED}, modified "
            f"{ESNEFT_MODIFIED} (the page was edited after publication; the record does not "
            "show what changed). Source: https://www.esneft.nhs.uk/major-power-cut-across-parts-"
            "of-england-and-wales/ ; retrieved 2026-10-20. The page text is the trust's "
            "copyright (no open licence stated); it is not reproduced.",
        ),
        *tagged(f"Summary written for this record — {ESNEFT_GIST}", "reported"),
    )

    # ---- Part B ------------------------------------------------------------------------------
    doc.blank()
    doc.frame(
        "Part B heading",
        "PART B — AIRPORT POSTS WITHOUT RECOVERABLE TEXT (identifiers and decoded times)",
    )
    _check_airport_posts(inputs)
    times = [utc_z(post_time(pid).replace(microsecond=0)) for pid in AIRPORT_POSTS]
    seg = doc.segment(
        "B1 Newcastle International Airport posts: decoded times, text not recoverable",
        "reported",
        "script",
        [
            data_ref(
                "comms_posts_index",
                "rows of the two airport posts (identifier, capture, empty text, note)",
            ),
            *(
                {
                    "kind": "public_post",
                    "source_id": "comms_posts_index",
                    "post_id": str(pid),
                    "decoded_utc": utc_z(post_time(pid), ms=True),
                    "archive_url": AIRPORT_CAPTURES[pid],
                    "quote": None,
                    "note": "script-only page capture; the real-data pass recorded the text as "
                    "not recoverable (embed request failed)",
                }
                for pid in AIRPORT_POSTS
            ),
        ],
        "Times decoded from the post identifiers: milliseconds since the Unix epoch = "
        "(identifier >> 22) + 1288834974657; truncated to the second.",
    )
    doc.add(
        seg,
        *p(
            "B1",
            "Newcastle International Airport: two public posts of 9 August 2019 located in "
            "Internet Archive captures. Times decoded from the post identifiers (milliseconds "
            "since 1970-01-01T00:00:00Z = (identifier >> 22) + 1288834974657), to the second:",
        ),
        *(
            f"    {when} | post {n} of 2 | identifier {pid} | content not known [reported]"
            for n, (when, pid) in enumerate(zip(times, AIRPORT_POSTS, strict=True), 1)
        ),
        *cont(
            "The archived captures hold no recoverable text for either post (script-only "
            "page captures), so what they said is not known."
        ),
    )

    doc.blank()
    doc.frame(
        "Part C: what the record does not contain",
        "PART C — NOTES",
        *p(
            "C1",
            "This record holds no statement by a water company or a refinery operator, no "
            "airport operations log and no hospital engineering record.",
        ),
    )

    build.construction = (
        "Part A gives the ESNEFT press release's title, displayed date and metadata times "
        "(each checked in the archived page) and a gist written for this record (the text is "
        "not openly licensed; the gist shares no run of more than three consecutive words with "
        "the statement; the speaker's name is omitted). Part B gives the identifiers and decoded "
        "times of two airport posts whose text is not recoverable. Nothing is synthesised."
    )
    build.add_artifact(
        Artifact(
            name=F_STATEMENTS,
            media_type="text/csv",
            description="Essential-service public statements (Parts A-B): time as published or "
            "decoded (UTC) and its basis, the post identifier of decoded posts, organisation, "
            "channel and a summary written for this record (no statement text).",
            data=csv_bytes(
                [
                    "time_utc",
                    "time_basis",
                    "post_identifier",
                    "organisation",
                    "channel",
                    "summary_written_for_this_record",
                ],
                [
                    [
                        ESNEFT_PUBLISHED.replace("+00:00", "Z"),
                        "page metadata datePublished (page displays the date only)",
                        "",
                        "East Suffolk and North Essex NHS Foundation Trust (Ipswich Hospital)",
                        "press release web page",
                        ESNEFT_GIST,
                    ],
                    *(
                        [
                            when,
                            "decoded from the post identifier",
                            str(pid),
                            "Newcastle International Airport",
                            "public social-media post",
                            "content not known (text not recoverable from the archived capture)",
                        ]
                        for when, pid in zip(times, AIRPORT_POSTS, strict=True)
                    ),
                ],
            ),
            provenance={
                "extraction_method": "paraphrase",
                "builder": BUILDER,
                "inputs": [
                    {"source_id": "esneft_statement"},
                    {
                        "source_id": "comms_posts_index",
                        "post_ids": [str(x) for x in AIRPORT_POSTS],
                    },
                ],
                "transformation": "publication details copied; gist written for this record; "
                "post times decoded from identifiers",
            },
        )
    )
    return build
