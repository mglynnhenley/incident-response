"""Provenance segment specs for S08, S10, S11 and the R10 Sections F-K.

Each spec is an ordered list of segments; ``start`` is the unique line prefix where a segment
begins (``fi_recon_common.resolve_segments``). Every non-framing segment cites verbatim quotes
that ``verify_fi_recon.py`` finds on the stated PDF page (after the MVP normalisation), and every
number on a sourced line must occur in the segment's quotes or source section labels, unless it
is listed in ``allow_numbers`` with the reason in ``transformation``.

R10 lines 1-133 keep increment A's segments (``builder/system_response/recon/recon_doc_specs.py``
``R10_SPEC``) unchanged; the segments below cover only the appended Sections F-K.
"""

from __future__ import annotations

from typing import Any

from fi_recon_common import allow, frame, raw_src, real_src, seg, src

HEADER = "Header: title, originator, record type, STATUS label"
LEGEND = "Value-status legend and layout note"

# --------------------------------------------------------------------------- section labels

ESO_TITLE = "Title page"
ESO_EXEC = "Executive Summary (clock basis: local time)"
ESO_EXEC_CONS = "Executive Summary – Immediate Consequences"
ESO_24 = "2.4 Generator Roles and Responsibilities"
ESO_52 = "5.2 Critical Infrastructure – Rail"
ESO_53 = "5.3 Other Priority Loads Affected"
ESO_7 = "section 7, Report Findings"
APP_D_GL = (
    "Appendix D – Hornsea Technical Report submitted by Ørsted, Glossary of Terms"
)
APP_F = "Appendix F – Govia Thameslink Railway (GTR) technical report"
APP_G = "Appendix G – Compliance Testing for Hornsea and Little Barford"
APP_M = "Appendix M – ESO E3C Questions and Answers (data available to the ESO on 28 August 2019)"
OFG_TITLE = "Title page"
OFG_EXEC = "Executive Summary"
OFG_2 = "Section 2, Consequences of the event"
OFG_212 = "Section 2, Our assessment of the event, 2.12"
OFG_ESO = "Section 3, The ESO, key findings"
OFG_NGET = "Section 3, NGET, 3.17-3.18"
OFG_H = "Section 3, Hornsea 1"
OFG_L = "Section 3, Little Barford"
OFG_DG = "Section 3, Distributed generation"
OFG_DNO = "Section 3, DNOs"
E3C_TITLE = "Title page"
E3C_1 = "chapter 1, Loss of generation"
E3C_3 = "chapter 3, Low Frequency Demand Disconnection scheme"
E3C_4 = "chapter 4, Impact on essential services"
E3CI_EXEC = "Executive Summary"
E3CI_ES = "Impact on Essential Services"
ORR_TITLE = "Title page"
ORR_1 = "1.0 Introduction"
ORR_21 = "2.1 Impact on the quality of power supplied to the railway"
ORR_22 = "2.2 Effect on GTR's Class 700 and Class 717 fleet"
ORR_23 = "2.3 Effects on timetable"
ORR_T1 = "2.3, Table 1 – Affected routes, cancellations and delays"
ORR_24 = "2.4 Possible impact on railway substation and signal power supply"
ORR_25 = "2.5 Possible impact on compensation"
ORR_3 = "3.0 Review of Investigations"
ORR_31 = "3.1 Permanent versus temporary lock-out"
ORR_32 = "3.2 Implementation of Permanent Lock-out"
ORR_33 = "3.3 Implications of permanent lock-out"
ORR_34 = "3.4 Applicable standards"
ORR_4 = "4.0 Conclusion"

ESO_DATE = src(
    "ESO",
    1,
    ESO_TITLE,
    "Technical Report on the events of 9 August 2019 6 September 2019",
)
OFG_DATE = src("OFG", 1, OFG_TITLE, "Publication date: 3 January 2020")
E3C_DATE = src(
    "E3C",
    1,
    E3C_TITLE,
    "Energy Emergencies Executive Committee (E3C): Final report January 2020",
)
ORR_DATE = src(
    "ORR",
    1,
    ORR_TITLE,
    "Report following railway power disruption on 9th August 2019 3rd January 2020",
)
GTR_DATE = src(
    "APP",
    48,
    APP_F + ", title block",
    "Power Surge Disruption on 9th August 2019: Technical Review. Date 3rd September 2019",
)
CLOCK_ESO = src("ESO", 3, ESO_EXEC, "At 4:52pm on 09 August 2019")
BST_NOTE = (
    "The sources print local clock times without a zone; read as BST because ESO dates the "
    "event at 4:52pm. The offset +01:00 is the BST definition, not a value taken from the "
    "sources."
)


def rep(
    start: str,
    content: str,
    sources: list[dict[str, Any]],
    method: str = "paraphrase",
    numbers: tuple[str, ...] = (),
    transformation: str | None = None,
) -> dict[str, Any]:
    segment = seg(start, content, "reported", method, sources, transformation)
    if numbers:
        allow(segment, *numbers)
    return segment


def gtr(start: str, item: str, content: str, page: int, *quotes: str) -> dict[str, Any]:
    return rep(
        start, content, [src("APP", page, f"{APP_F}, {item}", q) for q in quotes]
    )


# --------------------------------------------------------------------------- S08

S08_SPEC: dict[str, Any] = {
    "construction": (
        "Hand-authored (builder/full_investigation/recon/text/S08.src.txt, laid out by "
        "fi_text.py). Four parts, each restating one published rail account in its own terms "
        "and in the source's own order: GTR's technical review (ESO Appendix F), the rail "
        "passages of the ESO technical report, the ORR rail report, and the rail figures in the "
        "Ofgem and E3C reports. Counts differ between and within sources (e.g. ORR 1.0: 31 "
        "stranded, 29 locked out, 22 technician / 7 driver resets, 30 evacuated; ORR 4.0: 23 "
        "evacuated, 30 stranded on upgraded software; GTR: circa 60 units, 27 or 28 recovered "
        "by battery reset, circa 30 / 30 not recoverable, 17 + 24 technicians, 16 seconds below "
        "49 Hz; ESO: approximately 60, half restarted, 30 technician, 23 evacuations); they are "
        "kept and attributed, never reconciled, and no compiler's note points them out "
        "(decision 31). The Network Rail delay-attribution data and ORR periodic tables are "
        "real-data evidence supplied by the real-data track, not this record."
    ),
    "segments": [
        frame("DOCUMENT S08", HEADER),
        rep(
            "Clock reference:",
            "Clock basis: GTR's 1653 and ORR's 'around 4:52pm' as printed; read as BST",
            [
                src(
                    "APP",
                    48,
                    f"{APP_F}, Event Summary, item 1",
                    "From information supplied by the National Grid at 1653 on Friday the 9th "
                    "of August",
                ),
                src("ORR", 3, ORR_1, "On Friday 9th August 2019 around 4:52pm"),
                CLOCK_ESO,
            ],
            numbers=("01:00",),
            transformation=BST_NOTE,
        ),
        frame("Value-status legend:", LEGEND),
        rep(
            "PART 1",
            "Part heading: GTR technical review title, date, and how it reached the ESO",
            [
                GTR_DATE,
                src(
                    "APP",
                    47,
                    APP_F,
                    "This Appendix contains the independent technical report provided to the "
                    "ESO by GTR into the impact of the frequency disturbance on their trains",
                ),
            ],
        ),
        gtr(
            "G01  ",
            "Event Summary, item 1",
            "GTR event summary 1: frequency information supplied by National Grid",
            48,
            "From information supplied by the National Grid at 1653 on Friday the 9th of August "
            "the frequency of the OLE AC voltage supply dropped below 49Hz for 16 seconds. It "
            "dropped below 48.89Hz to a minimum of 48.8 Hz for milliseconds.",
        ),
        gtr(
            "G02  ",
            "Event Summary, item 2",
            "GTR event summary 2: no OLE supply interruption",
            48,
            "There was no identified OLE AC Voltage supply interruption.",
        ),
        gtr(
            "G03  ",
            "Event Summary, item 3",
            "GTR event summary 3: protective shutdown of Class 700/717 4QC; other classes "
            "unaffected",
            48,
            "All Desiro City class 700 and 717 units operating on AC Voltage suffered a "
            "Protective Shutdown where the converter, known as the 4QC (4 Quadrant Controller) "
            "shut down.",
            "None of the other AC trains in the GTR fleet suffered any power related issues "
            "from this event e.g. Class 387, Class 365, Class 313.",
        ),
        gtr(
            "G04  ",
            "Event Summary, item 4",
            "GTR event summary 4: circa 60 units",
            48,
            "In Passenger Service this involved circa 60 units, consisting of Class 700 "
            "FLU/RLUs and Class 717, suffering a 4QC lock out.",
        ),
        gtr(
            "G05  ",
            "Event Summary, item 5",
            "GTR event summary 5: train state on battery power",
            48,
            "The effect of the 4QC shutting down on the train is that the train switches to "
            "battery power which causes a loss of HVAC (fan only fresh air supply), stand by "
            "reduced lighting (emergency lighting is activated when battery voltage drops), no "
            "at seat power, no PIS displays (audio only from the cab), and no traction power. "
            "The GSM-R radio remains active.",
        ),
        gtr(
            "G06  ",
            "Event Summary, item 6",
            "GTR event summary 6: Battery Reset as first response, about 10 minutes",
            48,
            "Following failed attempts to repower the trains, the established first response "
            "for a train failing with these symptoms is for the Driver to perform a reboot of the "
            "train known as a Battery Reset. This takes approximately 10 minutes.",
        ),
        gtr(
            "G07  ",
            "Event Summary, item 7",
            "GTR event summary 7: Fleet Control diagnosis and GSM-R broadcast",
            48,
            "Fleet Control diagnosed the issue quickly and a global GSM-R call was broadcast to "
            "instruct drivers to carry out the Battery Reset process.",
        ),
        gtr(
            "G08  ",
            "Event Summary, item 8",
            "GTR event summary 8: 27 units recovered",
            48,
            "After this 27 of the affected units were recovered.",
        ),
        gtr(
            "G09  ",
            "Event Summary, item 9",
            "GTR event summary 9: circa 30 units needed a technician",
            48,
            "The remaining circa 30 units required the Protective Shutdown to be unlocked by the "
            "intervention of a Technician with a laptop attending each unit.",
        ),
        gtr(
            "G10  ",
            "Event Summary, item 10",
            "GTR event summary 10: 17 technicians plus 24 mobilised",
            48,
            "There were 17 Technicians available at the time of the event. These 17 were "
            "immediately sent to stranded units with laptops and a further 24 technicians were "
            "mobilized within the next hour. The trains affected were widely spread "
            "geographically and some were not easily accessible.",
        ),
        gtr(
            "G11  ",
            "Event Summary, item 11",
            "GTR event summary 11: 23 train evacuations",
            48,
            "Therefore, this process took some time and resulted in 23 train evacuations and "
            "severe levels of service disruption.",
        ),
        gtr(
            "G12  ",
            "Cause, item 1",
            "GTR cause 1: software-enabled train needs frequency-excursion protection",
            49,
            "The Desiro City from Siemens Mobility is the latest generation software enabled "
            "commuter train, so requiring protection against power supply frequency excursions "
            "for safety reasons and to protect low power electronics.",
        ),
        gtr(
            "G13  ",
            "Cause, item 2",
            "GTR cause 2: Siemens specification down to 48.5 Hz for short periods",
            49,
            "Siemens Technical Specification for the train states that the train will continue "
            "to operate with supply frequency drops down to 48.5Hz for short periods of time.",
        ),
        gtr(
            "G14  ",
            "Cause, item 3",
            "GTR cause 3: NR/GN/ELP/27010 identifies 48.5 Hz in extreme conditions",
            49,
            "The NR Electrification System Compatibility document, NR/GN/ELP/27010 (“Guidance "
            "for compatibility between electric trains and electrification systems”), a "
            "Manufacturing and Supply Agreement compliance requirement, identifies that the "
            "supply frequency can fall to 48.5Hz in extreme conditions.",
        ),
        gtr(
            "G15  ",
            "Cause, item 4",
            "GTR cause 4: NoBo design submission",
            49,
            "A review of the Class 700 NoBo design submission (Siemens document A6Z00036309602 "
            "item 4.2.8.2.2) shows that compliance with both NR/GN/ELP 27010 and EN 50163",
        ),
        gtr(
            "G16  ",
            "Cause, item 5",
            "GTR cause 5: EN 50163 Clause 4.2 Note 2 and the 49 Hz design value",
            49,
            "Siemens advised that the supply frequency response of the train was designed to "
            "comply with the EN 50163 Clause 4.2 Note 2. This note permits train drives to "
            "disconnected at 49Hz. Use of this supply frequency value in the train design led to "
            "the train protectively shutting down its drives when the supply frequency response "
            "fell below 49Hz.",
        ),
        gtr(
            "G17  ",
            "Cause, item 6",
            "GTR cause 6: no Permanent Lockout intended; 30 trains not recoverable",
            49,
            "Importantly Siemens have also clarified that there should not have been a Permanent "
            "Lockout on the train following a protective shutdown caused by a supply voltage "
            "frequency drop. All trains should have been recoverable via Battery Reset whereas "
            "30 trains were not recoverable. This was not the intended behaviour of the train.",
        ),
        gtr(
            "G18  ",
            "Cause, item 7",
            "GTR cause 7: not design intent; risk not known before",
            49,
            "Therefore, the affected Class 700 and 717 sets did not react according to their "
            "design intent in these circumstances. The risk of this happening was not known "
            "prior to the power event on Friday 9 August.",
        ),
        gtr(
            "G19  ",
            "Cause, item 8",
            "GTR cause 8: TCMS 3.27 removed battery-reset recovery from Permanent Lockout",
            49,
            "Separately as a part of the new TCMS (Train Control Management System) software "
            "version 3.27, the ability for the driver to recover from a Permanent Lockout by "
            "using the Battery Reset process was removed.",
        ),
        gtr(
            "G20  ",
            "Cause, item 9",
            "GTR cause 9: software levels of technician-recovered vs driver-recovered units",
            49,
            "On the 9th of August all the units which required a Technician to recover power were "
            "at software level 3.27 or above. The 28 units recovered by the driver performing a "
            "Battery Reset were at the previous TCMS software level of 3.25 or below.",
        ),
        gtr(
            "G21  ",
            "Conclusion, item 1",
            "GTR conclusion 1",
            50,
            "All the Class 700 and Class 717 trains operating on AC suffered a Protective "
            "Shutdown of the 4QC controller because of a drop in the supply frequency below 49Hz "
            "for 16 seconds.",
        ),
        gtr(
            "G22  ",
            "Conclusion, items 2 to 4",
            "GTR conclusions 2-4",
            50,
            "This was not how the train system had been specified to operate. This event should "
            "not have caused a Permanent Lockout fault on the trains.",
            "The effects of this were exacerbated as the fleet was undergoing a software change, "
            "contained in this was a change in functionality removing the Battery Reset remedy "
            "for Permanent Lockout events.",
            "This meant that the driver could not recover failed trains which were operating on "
            "the new software, instead a Technician was required to attend.",
        ),
        gtr(
            "G23  ",
            "Planned Mitigation, item 1",
            "GTR planned mitigation 1: patch to recover above 49.5 Hz",
            50,
            "Siemens are developing a software patch to allow units which protectively shutdown "
            "below 49Hz supply frequency to recover themselves without the need of a reboot or "
            "laptop when the frequency rises above 49.5Hz.",
        ),
        gtr(
            "G24  ",
            "Planned Mitigation, item 2",
            "GTR planned mitigation 2: no reversion; excursion risk considered extremely unlikely",
            50,
            "It is not proposed by Siemens or GTR to revert units to previous software versions "
            "as there are concerns this could severely impact unit availability. Based on "
            "discussions with the National Grid Head of Networks, the risk of frequency "
            "excursion dropping below 49Hz before the patch is fully introduced are considered "
            "extremely unlikely.",
        ),
        gtr(
            "G25  ",
            "Planned Mitigation, item 3",
            "GTR planned mitigation 3: operation down to 48.5 Hz to be investigated",
            50,
            "In addition to this Siemens will investigate how the train could be made to operate "
            "for a short time with supply frequency falling to 48.5Hz.",
        ),
        rep(
            "PART 2",
            "Part heading: ESO report date and the sections restated",
            [ESO_DATE],
            transformation="Section numbers 5.2 and 7 are the ESO report's own; see the "
            "segments' section labels.",
            numbers=("5.2", "7"),
        ),
        rep(
            "E01  ",
            "ESO 5.2: Class 700/717 shutdowns north of Farringdon and Kings Cross",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "Class 700 and 717 trains shut down north of Farringdon and Kings Cross "
                    "stations due to their internal protection systems being triggered. The "
                    "Network Rail overhead line power supply operated continually. The shutdown "
                    "of these trains had a knock-on impact by delaying all other trains behind "
                    "them requiring the temporarily closure of London St Pancras and Kings Cross "
                    "stations which led to Friday rush hour overcrowding.",
                )
            ],
        ),
        rep(
            "E02  ",
            "ESO 5.2: summary of GTR's report (approximately 60, half, 30)",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The report sets out that all Desiro City Class 700 and Class 717 trains that "
                    "were operating on AC power suffered a protective shutdown when the frequency "
                    "deviation fell below 49Hz. Of the approximately 60 Class 700 and Class 717 "
                    "trains that shutdown, half were restarted by the driver on site performing a "
                    "reboot of the train, which takes c10mins. The remaining 30 trains required a "
                    "technician to attend each train with a laptop to reset the trains.",
                )
            ],
            numbers=("10",),
            transformation="ESO prints 'c10mins'; written as 'c. 10 minutes'.",
        ),
        rep(
            "E03  ",
            "ESO 5.2: GTR statement on specification and 48.5 Hz",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "GTR have stated this was not how the train system had been specified to "
                    "operate and the event should not have caused a permanent lockout fault on "
                    "the trains. The technical specification for the trains states that the "
                    "trains will continue to operate with supply frequency drops down to 48.5Hz "
                    "for short periods of time. All other GTR classes of train were unaffected.",
                )
            ],
        ),
        rep(
            "E04  ",
            "ESO 5.2: software change and Siemens patch",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The effects were exacerbated as the fleet was undergoing a software change "
                    "which meant the train drivers could not recover trains which were operating "
                    "on the new software. The train manufacturer, Siemens, are developing a patch "
                    "which will allow the drivers to recover the trains themselves without the "
                    "need for a reboot or technician to attend site. In addition Siemens will "
                    "investigate how the train could be made to operate for a short time with a "
                    "supply frequency of 48.5Hz.",
                )
            ],
        ),
        rep(
            "E05  ",
            "ESO 5.2: evacuations, cancellations, delays and station closures",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The impact to the rail network was that there were 23 train evacuations and "
                    "thousands of passengers had their journeys delayed with 371 trains "
                    "cancelled, 220 part cancelled, and 873 trains delayed. London St Pancras and "
                    "King’s Cross stations had to close for several hours due to overcrowding "
                    "and London Euston went exit only for a period of time.",
                )
            ],
        ),
        rep(
            "E06  ",
            "ESO executive summary: approximately 60 trains, half needed a technician",
            [
                src(
                    "ESO",
                    4,
                    ESO_EXEC_CONS,
                    "A major contributor to the disruption relates to a particular class of "
                    "train operating in the South-East area – approximately 60 trains "
                    "unexpectedly shut down when the frequency dropped below 49Hz, half of which "
                    "required a visit from a technician to restart.",
                )
            ],
        ),
        rep(
            "E07  ",
            "ESO section 7: approximately 30 trains could not be restarted",
            [
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "The disruption to rail services extended through Friday evening and into "
                    "Saturday morning due to the fact that approximately 30 trains stopped "
                    "operating and could not be restarted following the original frequency drop "
                    "to 49Hz. Restarting them required a technician with a laptop to attend each "
                    "train which took some time.",
                )
            ],
        ),
        rep("PART 3", "Part heading: ORR report title and date", [ORR_DATE]),
        rep(
            "O01  ",
            "ORR 1.0: event time and frequency as ORR states them",
            [
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "On Friday 9th August 2019 around 4:52pm, a number of electricity generators "
                    "tripped off the power grid at approximately the same time.",
                ),
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "The loss of generation caused the frequency of the power supply to the rail "
                    "network to drop from its nominal value of 50.0Hz to below 49.0Hz for "
                    "approximately 33 seconds, falling to a low of 48.8Hz.",
                ),
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "The majority of rolling stock operated without any issues.",
                ),
            ],
        ),
        rep(
            "O02  ",
            "ORR 1.0: 31 stranded, 29 locked out, 22/7, two Class 387, 30 evacuated",
            [
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "However, 31 trains were stranded as a result of the temporary drop in "
                    "frequency. On the Class 700 and Class 717 rolling stock, protection systems "
                    "operated within 200ms of the frequency falling to 49.0Hz causing a lock-out "
                    "of 29 trains. 22 trains were permanently locked-out and could not be reset "
                    "without a technician attending on site while 7 trains were restored through "
                    "driver-reset. Two Class 387 trains were also trapped as a result of the "
                    "lock-out experienced by the Class 700 and Class 717 trains. Passengers had to "
                    "be evacuated from 30 trains to a place of safety (detrained). There were "
                    "substantial knock-on delays following recovery of the vehicles.",
                )
            ],
        ),
        rep(
            "O03  ",
            "ORR 2.1: frequency description and Figure 1 caption",
            [
                src(
                    "ORR",
                    4,
                    ORR_21,
                    "The supplied power frequency dropped from a nominal 50.0Hz to a low level of "
                    "48.8Hz after 16 seconds. The frequency remained below 49.0Hz for "
                    "approximately 33 seconds and was restored back to its nominal value of 50Hz "
                    "3 minutes and 36 seconds later.",
                ),
                src(
                    "ORR",
                    4,
                    ORR_21,
                    "Figure 1 – Annotated Frequency Trace of Event [extracted from National "
                    "Grid Technical Report on the events of 9 August 2019 published 06/08/2019]",
                ),
            ],
        ),
        rep(
            "O04  ",
            "ORR 2.1: Class 700/717 shut down within 200 ms below 49.0 Hz",
            [
                src(
                    "ORR",
                    4,
                    ORR_21,
                    "The majority of the rolling stock on the network at the time operated "
                    "without notable issues, but a fleet of Class 700 and Class 717 trains "
                    "operated by Govia Thameslink Railway (GTR) shut down within 200ms of the "
                    "frequency dropping below 49.0Hz.",
                )
            ],
        ),
        rep(
            "O05  ",
            "ORR 2.2: 29 trains locked out; Fleet Control advice",
            [
                src(
                    "ORR",
                    5,
                    ORR_22,
                    "Within 200ms of the power supply frequency dropping below 49.0Hz, 29 trains "
                    "comprising Class 700 and Class 717, operated by Govia Thameslink Railway, "
                    "shut down and were locked-out by on-board safety systems. Initial attempts "
                    "made by drivers to bring the trains back into operation proved abortive and "
                    "required the intervention of Fleet Control to advise drivers on the next "
                    "action.",
                )
            ],
        ),
        rep(
            "O06  ",
            "ORR 2.2: quotation of GTR's review; 4QC isolation and battery supply",
            [
                src(
                    "ORR",
                    5,
                    ORR_22,
                    "According to a technical review carried out by GTR, ‘all Desiro City "
                    "Class 700 and 717 units operating on AC Voltage suffered a Protective "
                    "Shutdown where the converter, known as the 4QC (Four Quadrant Chopper) shut "
                    "down.’ When the 4QC shuts down, the train is isolated from the traction "
                    "power supply. Available power is restricted to the limited on-board battery "
                    "supply, which only supplies certain key on-board systems and does not "
                    "provide power for traction.",
                )
            ],
        ),
        rep(
            "O07  ",
            "ORR 2.2: GSM-R call; 7 recovered, 22 needed a technician",
            [
                src(
                    "ORR",
                    5,
                    ORR_22,
                    "Following the diagnosis of the shutdown by Fleet Control, a GSM-R (Global "
                    "System for Mobile Communications – Railway) call was broadcast to "
                    "instruct drivers of affected trains to carry out the Battery Reset Process. "
                    "The process led to the recovery of 7 of the affected units. 22 trains could "
                    "not be reset and required the attendance of a technician to recover them.",
                )
            ],
        ),
        rep(
            "O08  ",
            "ORR 2.2: 18 technicians sent immediately",
            [
                src(
                    "ORR",
                    5,
                    ORR_22,
                    "At the time of the event, the technicians available were too few compared to "
                    "the number of stranded trains. 18 Technicians with laptops were sent to "
                    "restore the trains immediately, and within the next hour more technicians "
                    "were mobilised.",
                )
            ],
        ),
        rep(
            "O09  ",
            "ORR 2.3: recovery, 30 trains detrained, full service within 24 hours",
            [
                src(
                    "ORR",
                    5,
                    ORR_23,
                    "The geographical locations of some of the trains meant they were not easily "
                    "accessible, making the entire train recovery process time-consuming. "
                    "Passengers were safely detrained at stations and on track from 30 stranded "
                    "trains. There were significant train delays, cancellations and "
                    "part-cancellations of train journeys. However, full service was restored "
                    "within 24 hours.",
                )
            ],
        ),
        rep(
            "O10  ",
            "ORR Table 1: routes, cancellations, part-cancellations, delay minutes",
            [
                src(
                    "ORR",
                    5,
                    ORR_T1,
                    "Routes Cancelled Part- Cancelled Delay Minutes Sussex 38 22 2051",
                ),
                src(
                    "ORR",
                    6,
                    ORR_T1,
                    "Wessex 0 2 716 Kent 36 43 1727 Western 0 0 658 LNE-York 86 44 5569 LNE-EM "
                    "197 79 2780 LNW-N 14 24 428 Wales 0 6 499 TOTAL 371 220 14428 Table 1 "
                    "– Affected routes, cancellations and delays Source: Network Rail’s "
                    "National Daily Report 09/08/2019",
                ),
            ],
            method="transcription",
        ),
        rep(
            "O11  ",
            "ORR 2.5: compensation claims in period 5",
            [
                src(
                    "ORR",
                    8,
                    ORR_25,
                    "There was an increase in delay compensation claims received by train "
                    "operators in period 5 (21st July to 18th Aug) to the highest level since May "
                    "2018 timetable disruption with a particular peak for GTR. Although this "
                    "cannot be directly attributable to the power disruption, it is likely to "
                    "have been a factor. There was no corresponding peak in complaints during "
                    "this time and this remained on trend.",
                )
            ],
        ),
        rep(
            "O12  ",
            "ORR 3.0: engagement and parties' roles",
            [
                src(
                    "ORR",
                    8,
                    ORR_3,
                    "ORR engaged with Network Rail, GTR and Siemens, to understand the extent of "
                    "the impact of the power disruption and why it significantly affected the "
                    "railway services despite not losing traction power. Network Rail owns and "
                    "manages the railway infrastructure. GTR is a train operating company "
                    "operating the affected trains and carrying out some of the maintenance. "
                    "Siemens as the train manufacturer designed the software on the affected "
                    "trains and also maintains some of the trains.",
                )
            ],
        ),
        rep(
            "O13  ",
            "ORR 3.1: permanent vs temporary lock-out definitions",
            [
                src(
                    "ORR",
                    8,
                    ORR_31,
                    "This report refers to a “lock-out” as a situation where a "
                    "component’s operation has been stopped by a software-based protection "
                    "system.",
                ),
                src(
                    "ORR",
                    8,
                    ORR_31,
                    "Permanent lock-outs are in place to protect against on-board risks with high "
                    "severity such as fire and electrocution, which could occur when damaged "
                    "components get reenergised. A permanent lock-out requires a technician with "
                    "a laptop to physically connect to the train and reset the lock-out.",
                ),
                src(
                    "ORR",
                    8,
                    ORR_31,
                    "Temporary lock-outs are in place to protect against risks with low severity "
                    "following a short-lived system fault or mal-operation. In such cases the "
                    "train either resets itself as soon as the fault is cleared, or the train "
                    "driver resets the software system using a Battery Reset Process.",
                ),
            ],
        ),
        rep(
            "O14  ",
            "ORR 3.1: programmed minimum 49.0 Hz; drive disconnected within 200 ms",
            [
                src(
                    "ORR",
                    8,
                    ORR_31,
                    "All Class 700 and 717 trains had been programmed by Siemens to operate from "
                    "a power supply of a nominal 50.0Hz, with a minimum frequency of 49.0Hz. When "
                    "the software detected that the frequency",
                ),
                src(
                    "ORR",
                    9,
                    ORR_31,
                    "had dropped below this level, it operated as designed, disconnecting the "
                    "traction drive within 200ms.",
                ),
            ],
        ),
        rep(
            "O15  ",
            "ORR 3.1: software 3.25.x temporary vs 3.27.x permanent lock-out",
            [
                src(
                    "ORR",
                    9,
                    ORR_31,
                    "Individual trains within the fleets had different software levels installed, "
                    "as a software change was being implemented progressively across the fleets. "
                    "On detecting the frequency drop, the units with software version 3.25.x went "
                    "into a temporary lock-out while the units with version 3.27.x went into "
                    "permanent lock-out. The drivers were able to reset units with a temporary "
                    "lock-out by carrying out a battery reset, while the units with a permanent "
                    "lockout required a technician to attend to perform a reset.",
                )
            ],
        ),
        rep(
            "O16  ",
            "ORR 3.2: why 3.27.x introduced a permanent lock-out",
            [
                src(
                    "ORR",
                    9,
                    ORR_32,
                    "The two software versions reacted differently as the later version 3.27.x "
                    "software was intended to address what had been identified as a safety risk "
                    "linked to the earlier software version 3.25.x.",
                ),
                src(
                    "ORR",
                    9,
                    ORR_32,
                    "Siemens identified that there could be circumstances where the Train Control "
                    "Management System (TCMS) locked out a train system in response to a serious "
                    "fault or out-of-specification condition that could lead to a safety "
                    "incident, only for the driver to perform a battery reset. This cleared the "
                    "lockout and allowed power to be restored to the fault which could make the "
                    "incident worse.",
                ),
                src(
                    "ORR",
                    9,
                    ORR_32,
                    "Siemens decided to implement a “permanent lock-out” in software "
                    "version 3.27.x that could not be cleared by a battery reset. Such a "
                    "permanent lock-out would require a technician to attend the train and "
                    "perform an analysis of the causes of the lock-out before clearing it.",
                ),
                src(
                    "ORR",
                    9,
                    ORR_32,
                    "Among the conditions selected was the detection of a low power supply "
                    "frequency.",
                ),
            ],
        ),
        rep(
            "O17  ",
            "ORR 3.3: purpose of the lock-out; implications not given weight",
            [
                src(
                    "ORR",
                    9,
                    ORR_33,
                    "The imposition of a lock-out when the supply frequency is outside of "
                    "specified limits is understood to be a protection against the generation by "
                    "the 4QC of electromagnetic interference in a range that can affect "
                    "signalling circuits. Such protection is only required when the power supply "
                    "is not in the specified frequency range, and therefore the lock-out could be "
                    "permitted to automatically reset when the supply frequency",
                ),
                src("ORR", 10, ORR_33, "returns to its nominal value."),
                src(
                    "ORR",
                    10,
                    ORR_33,
                    "the service-disrupting implications of imposing a lock-out requiring a "
                    "driver or – as in this case – a technician to reset appear not to "
                    "have been given weight when developing the protection parameters for the "
                    "on-train software.",
                ),
            ],
        ),
        rep(
            "O18  ",
            "ORR 3.3: collective response per design but not explicit intention",
            [
                src(
                    "ORR",
                    10,
                    ORR_33,
                    "Variations in the power supply frequency, however, affect many trains at the "
                    "same time and result in the same response from all trains that have the same "
                    "software. It appears therefore that the collective response of the Class 700 "
                    "and 717 trains to the out-of-specification supply frequency was in accordance "
                    "with the software design, but was not an explicit intention. Siemens accepts "
                    "that the temporary reduction in frequency should not have been considered a "
                    "situation that requires a permanent lock-out.",
                )
            ],
        ),
        rep(
            "O19  ",
            "ORR 3.4: Siemens interim email on original design and hysteresis",
            [
                src("ORR", 10, ORR_34, "In an interim email to ORR, Siemens stated"),
                src(
                    "ORR",
                    10,
                    ORR_34,
                    "The original design of the class 700 is for the 4QCs to stop pulsing when the "
                    "line frequency is out of range and automatically restart when the frequency "
                    "come back in range. This does not require driver action. With the hysteresis "
                    "implemented, the 4QCs lock when line frequency drops below 49Hz and they "
                    "restart when the frequency rises above 49.5Hz.",
                ),
            ],
        ),
        rep(
            "O20  ",
            "ORR 4.0: 23 evacuated; delays attributed to permanent lock-out",
            [
                src("ORR", 11, ORR_4, "23 trains were evacuated without incident."),
                src(
                    "ORR",
                    11,
                    ORR_4,
                    "The significant delays encountered by most passengers could be attributed to "
                    "the permanent lock-out of some of the Class 700 and Class 717 trains. "
                    "Findings so far revealed that TCMS software classed the reduction in "
                    "frequency as a scenario which required a permanent lock-out.",
                ),
            ],
        ),
        rep(
            "O21  ",
            "ORR 4.0: 30 trains on upgraded software stranded",
            [
                src(
                    "ORR",
                    11,
                    ORR_4,
                    "The permanent lock-out resulted in 30 trains running the upgraded software "
                    "to be effectively stranded on the network and therefore requiring a "
                    "technician reset. This resulted in significant delays for the entire network "
                    "and significant knock on effects that lasted beyond the initial incident. "
                    "However, full service was restored within 24hours.",
                )
            ],
        ),
        rep(
            "O22  ",
            "ORR 4.0: no non-compliance established with the Interoperability Regulations",
            [
                src(
                    "ORR",
                    11,
                    ORR_4,
                    "So far, ORR has not been able to establish any non-compliance with The "
                    "Railways (Interoperability) Regulations 2011, as amended, that could warrant "
                    "an enforcement action. The findings are lessons learned that will be fed "
                    "back for awareness and improvement.",
                )
            ],
        ),
        frame("PART 4", "Part heading"),
        rep(
            "X01  ",
            "Ofgem 2.6: 29 trains, two Class 387, 30 evacuated",
            [
                OFG_DATE,
                src(
                    "OFG",
                    19,
                    OFG_2 + ", 2.6",
                    "In the transport sector, 29 Govia Thameslink Railway (GTR) Class 700 and 717 "
                    "trains shut down and became stranded when the system frequency fell below "
                    "49Hz due to their own on-board automatic frequency protection systems. Two "
                    "Class 387",
                ),
                src(
                    "OFG",
                    20,
                    OFG_2 + ", 2.6",
                    "trains were also trapped by the stranded units, and altogether passengers "
                    "had to be safely evacuated from 30 trains.",
                ),
            ],
        ),
        rep(
            "X02  ",
            "Ofgem 2.7: 22 permanently locked out; software update",
            [
                src(
                    "OFG",
                    20,
                    OFG_2 + ", 2.7",
                    "Some of these protection settings were reset by the driver but 22 "
                    "permanently locked out and had to be reset by a technician, which was the "
                    "main cause of disruption to rail lines into St Pancras International and "
                    "King’s Cross. A software update is being introduced to these trains so "
                    "that they can be automatically reset if the frequency drops below 49Hz in the "
                    "future.",
                )
            ],
        ),
        rep(
            "X03  ",
            "Ofgem 2.9 and executive summary: cancellations; more than 500 services disrupted",
            [
                src(
                    "OFG",
                    20,
                    OFG_2 + ", 2.9",
                    "As a result, there was significant disruption to the rail network, with 371 "
                    "services cancelled and 220 part cancelled.",
                ),
                src(
                    "OFG",
                    5,
                    OFG_EXEC,
                    "The rail services were particularly affected with more than 500 services "
                    "disrupted.",
                ),
            ],
        ),
        rep(
            "X04  ",
            "E3C interim: 60 trains, around half restarted, 371 cancelled, 873 delayed",
            [
                src(
                    "E3C-I",
                    12,
                    E3CI_ES + ", Rail",
                    "The Department for Transport confirmed that rail commuters experienced "
                    "significant disruption due to a safety mechanism built-in to all operational "
                    "Class 700 and Class 717 Desiro City trains. This detected the drop in "
                    "frequency on the electricity system which triggered 60 trains to shut down",
                ),
                src(
                    "E3C-I",
                    12,
                    E3CI_ES + ", Rail",
                    "While around half of the affected trains were restarted by their drivers, "
                    "the rest required engineers to be dispatched, blocking tracks and causing "
                    "huge disruption on lines into St Pancras International and King’s "
                    "Cross. 371 services were cancelled and 873 delayed,",
                ),
                src(
                    "E3C-I",
                    12,
                    E3CI_ES + ", Rail",
                    "This led to St Pancras International, King’s Cross and Euston stations "
                    "having to limit passenger numbers entering the stations at various times.",
                ),
            ],
        ),
        rep(
            "X05  ",
            "E3C interim: trains out of position; delays into 11 August",
            [
                src(
                    "E3C-I",
                    12,
                    E3CI_ES + ", Rail",
                    "a number of trains did not end up in their correct location at the end of the "
                    "day, which led to some early morning services on Saturday 10 th August being "
                    "disrupted.",
                ),
                src(
                    "E3C-I",
                    4,
                    E3CI_EXEC,
                    "This is especially true for rail services which experienced major delays "
                    "that extended into Sunday 11th August.",
                ),
                src(
                    "E3C-I",
                    12,
                    E3CI_ES + ", Rail",
                    "The Class 700 and 717 trains, have been introduced over the last three years",
                ),
            ],
        ),
        rep(
            "X06  ",
            "E3C final section 4: rail disruption figures",
            [
                E3C_DATE,
                src(
                    "E3C",
                    18,
                    E3C_4,
                    "The rail sector reported disruptions because Thameslink class 700 and 717 "
                    "trains systems were overprotective to frequency drops on the electricity "
                    "network and shut down. A number of trains required manual engineer "
                    "intervention to restart trains and the complexity of the restart process "
                    "caused significant disruptions translating to 371 cancelled services, 220 "
                    "part cancelled services and 873 delayed services.",
                ),
            ],
        ),
    ],
}


# --------------------------------------------------------------------------- S10


def app_g(page: int, quote: str, part: str = "") -> dict[str, Any]:
    return src("APP", page, APP_G + (f", {part}" if part else ""), quote)


def ofg(page: int, section: str, quote: str) -> dict[str, Any]:
    return src("OFG", page, section, quote)


S10_SPEC: dict[str, Any] = {
    "construction": (
        "Hand-authored (builder/full_investigation/recon/text/S10.src.txt, laid out by "
        "fi_text.py). Part 1 transcribes ESO Appendix G's Hornsea One compliance record (meeting "
        "and data-submission dates, energisation/synchronisation table, completed-test tables, "
        "outstanding tests and FON prerequisites, all as printed, including '17.012019') and "
        "adds Ofgem 3.19 and the E3C's description of the interim export status. Part 2 "
        "transcribes the Little Barford compliance milestones and Ofgem 3.25. Part 3 restates "
        "ESO answers 43-45 (data at 28 August 2019). Parts 4-5 restate Ofgem's section 3 and "
        "executive-summary findings on the compliance process and on performance against "
        "requirements (Hornsea FRT and damping, Little Barford, EPN/SPN reconnection, SP "
        "Distribution, NGET, distributed generation), keeping Ofgem's hedges ('do not appear', "
        "'acknowledged', 'preliminary view'). Ofgem section 4 ('Compliance, voluntary action and "
        "enforcement', including 4.4 on parties' differing interpretations and the voluntary "
        "resolution) and the executive summary's enforcement outcomes (voluntary payments) are "
        "excluded (decision 50); see excluded_from_agent_evidence in the provenance file. "
        "Increment A's records already hold the operational content of Ofgem 3.21 and 3.27."
    ),
    "segments": [
        frame("DOCUMENT S10", HEADER),
        frame("Clock reference:", "Clock statement (dates only, as printed)"),
        frame("Value-status legend:", LEGEND),
        rep(
            "PART 1",
            "Part heading: ESO Appendix G title",
            [
                ESO_DATE,
                src(
                    "APP",
                    51,
                    APP_G,
                    "Appendix G - Compliance Testing for Hornsea and Little Barford",
                ),
            ],
        ),
        rep(
            "H01  ",
            "Appendix G: 14 compliance meetings 2017-2019",
            [
                app_g(
                    52,
                    "NG ESO and Orsted had 14 face to face operational notification connections "
                    "compliance meetings between 21/03/2017 and 05/04/2019 to ensure Orsted fully "
                    "understood the Grid Code requirements for a Hornsea Offshore wind farm to "
                    "demonstrate.",
                    "Hornsea Compliance Testing",
                )
            ],
        ),
        rep(
            "H02  ",
            "Appendix G: compliance data submissions and ESO confirmation",
            [
                app_g(
                    52,
                    "Orsted provided Grid Code requirement compliance data to NG ESO from "
                    "04/08/2017 to 21/06/2019 with the first version of the fault ride through "
                    "report submitted on 30/04/2018. Following all the compliance data "
                    "submissions which included all the simulation studies relating to Fault "
                    "Ride Through, Voltage Control, Frequency Control and Reactive Capability "
                    "demonstrating that Hornsea complies with the Grid Code through the design of "
                    "the plant, NG ESO confirmed the compliance data were satisfactory.",
                    "Hornsea Compliance Testing",
                )
            ],
        ),
        rep(
            "H03  ",
            "Appendix G: energisation and synchronisation table",
            [
                app_g(
                    52,
                    "Energisation of assets and synchronisation to the NETS occurred as shown "
                    "below Activity Date Energization of circuit 1 31/10/2018 Energization of "
                    "circuit 2 28/11/2018 Synchronization of Reactive Compensators 06/11/2018 "
                    "Synchronization of Module 1 15/07/2019 Synchronization of Module 2 "
                    "01/02/2019 Synchronization of Module 3 30/04/2019",
                    "Hornsea Compliance Testing",
                )
            ],
            method="transcription",
        ),
        rep(
            "H04  ",
            "Appendix G: 20% capacity voltage tests table",
            [
                app_g(52, "Completed Grid Code Compliance Test Dates"),
                app_g(
                    53,
                    "20% Capacity Voltage Tests Date of Test Results sent to NG ESO Approval by "
                    "ESO Hornsea M1_20% Voltage test on Dynamic Reactive Compensator DRC10 "
                    "15.01.2019 17.012019 17.012019 Hornsea M2_20% Voltage test on Dynamic "
                    "Reactive Compensator DRC20 15.01.2019 17.012019 17.012019 Hornsea M3_20% "
                    "Voltage test on Dynamic Reactive Compensator DRC30 15.01.2019 17.012019 "
                    "17.012019 Hornsea M1/2 20% Voltage test on Dynamic Reactive Compensators "
                    "DRC10/20 together 15.01.2019 17.012019 17.012019",
                ),
            ],
            method="transcription",
        ),
        rep(
            "H05  ",
            "Appendix G: 70% capacity LFSM tests table",
            [
                app_g(
                    53,
                    "70% capacity, Limited Frequency sensitive Mode Tests OC5.A.3.3 Date of Test "
                    "Approval by ESO Hornsea M2 70% Frequency test on High Performance Park Pilot "
                    "(HPPP) 2 25.03.2019 26.03.2019 Hornsea M3 70% Frequency test on High "
                    "Performance Park Pilot (HPPP) 2 07.06.2019 13.06.2019 Hornsea M1 70% "
                    "Frequency test on High Performance Park Pilot (HPPP) 2 09.08.2019 "
                    "23.08.2019",
                )
            ],
            method="transcription",
        ),
        rep(
            "H06  ",
            "Appendix G: preliminary frequency response tests table",
            [
                app_g(
                    53,
                    "Preliminary Frequency Response Tests OC5.A.3.6.4 Date of Test Approval by "
                    "ESO Hornsea M2 Frequency tests on High Performance Park Pilot (HPPP) 2 "
                    "25.03.2019 26.03.2019 Hornsea M3 Frequency tests on High Performance Park "
                    "Pilot (HPPP) 2 07.06.2019 13.06.2019",
                )
            ],
            method="transcription",
        ),
        rep(
            "H07  ",
            "Appendix G: list of outstanding tests",
            [
                app_g(
                    53,
                    "List of Outstanding Tests 70% capacity, Preliminary Frequency Response Tests "
                    "on wind farm M1. 100% capacity, Reactive Capability Testing on the 2 "
                    "Transmission Interface Points CP.7.2.2(a), OC5.A.3.4 100% capacity, Voltage "
                    "Control Testing on the two connections CP.7.2.2(b), OC5.A.3.5 100% capacity, "
                    "Frequency Response Testing on the 3 Offshore Wind Farms CP.7.2.2(c) "
                    "OC5.A.3.6.6.",
                )
            ],
            method="transcription",
        ),
        rep(
            "H08  ",
            "Appendix G: requirements outstanding before FON",
            [
                app_g(
                    53,
                    "Further requirements outstanding prior to issuing Final Operational "
                    "Notification (FON) Updates to documentation as CP.7.3 most significant items "
                    "being: Model verification to demonstrate that the models/parameters reflect "
                    "the test results CP.7.3.1(c), CP.A.3.7 Update planning code data with final "
                    "commissioned status. CP.7.3.1(a) Updated Compliance Statements CP.7.3.1(e)",
                )
            ],
        ),
        rep(
            "H09  ",
            "Ofgem 3.19: declared 800 MW; interim export basis",
            [
                OFG_DATE,
                ofg(
                    28,
                    OFG_H + ", 3.19",
                    "Hornsea 1 is a 1,200MW capacity offshore wind farm",
                ),
                ofg(
                    29,
                    OFG_H + ", 3.19",
                    "On 9 August, two of its modules were fully installed and the third was "
                    "partially installed; it therefore had declared a total 800MW power export "
                    "capability. Hornsea 1 was progressing though the Grid Code compliance process "
                    "and had fulfilled the necessary requirements to export on an interim basis.",
                ),
            ],
        ),
        rep(
            "H10  ",
            "E3C final chapter 1: two units passed, remaining unit up to 20%",
            [
                E3C_DATE,
                src(
                    "E3C",
                    11,
                    E3C_1,
                    "At the time of the incident on 9 August 2019, the windfarm was in the "
                    "process of demonstrating compliance with the Grid Code as required by all "
                    "new generators, before being allowed to export at maximum capacity onto the "
                    "transmission network. Two of the units had passed the compliance tests, with "
                    "the remaining unit permitted to export up to 20% whilst awaiting further "
                    "testing. These limits were granted by the ESO based on the testing and "
                    "studies submitted at the time.",
                ),
            ],
        ),
        frame("PART 2", "Part heading"),
        rep(
            "B01  ",
            "Appendix G: Little Barford connected 1996, before the compliance process",
            [
                app_g(
                    54,
                    "Little Barford connected to the transmission network in 1996 prior to the "
                    "inclusion of the compliance process into the Grid Code however, the "
                    "compliance process applied to the replacement of gas turbines and associated "
                    "control systems.",
                    "Little Barford Compliance Testing",
                )
            ],
        ),
        rep(
            "B02  ",
            "Appendix G: Little Barford compliance milestones table",
            [
                app_g(
                    54,
                    "Activity Date ESO issued LON for Gas Turbine replacement 06/01/2012 "
                    "Automatic Voltage Regulator & Power System Stabilizer Tests on GT1A "
                    "07/01/2013 Automatic Voltage Regulator & Power System Stabilizer Tests on "
                    "GT1B 17/01/2013 Automatic Voltage Regulator & Power System Stabilizer Tests "
                    "on ST10 01/10/2012 Governor Tests 15-19/03/2013 ESO Issued FON 26/04/2013",
                    "Little Barford Compliance Testing",
                )
            ],
            method="transcription",
        ),
        rep(
            "B03  ",
            "Ofgem 3.25: Little Barford station description",
            [
                ofg(
                    30,
                    OFG_L + ", 3.25",
                    "Little Barford is a 740MW combined cycle gas turbine power station, located "
                    "in Bedfordshire. It is owned and operated by RWE Generation. It is connected "
                    "to the national transmission system at the Eaton Socon 400kV substation. The "
                    "station has two gas turbines and one steam turbine which were all operating "
                    "on 9 August. It was commissioned in 1995 and went through a major upgrade in "
                    "2011/12.",
                )
            ],
        ),
        rep(
            "PART 3",
            "Part heading: Appendix M data date",
            [
                src(
                    "APP",
                    70,
                    APP_M,
                    "These answers are all based on the data available to the ESO on 28 August "
                    "2019.",
                )
            ],
        ),
        rep(
            "Q01  ",
            "ESO answer 43: not aware of concerns",
            [
                src(
                    "APP",
                    91,
                    APP_M + ", answer 43",
                    "Were there any areas of concern about compliance testing with generators or "
                    "OFTOs?",
                ),
                src(
                    "APP",
                    91,
                    APP_M + ", answer 43",
                    "We are not aware of concerns regarding the compliance testing process.",
                ),
            ],
        ),
        rep(
            "Q02  ",
            "ESO answer 44: no issues highlighted in the past",
            [
                src(
                    "APP",
                    91,
                    APP_M + ", answer 44",
                    "There have been no issues highlighted in the generation compliance process at "
                    "Hornsea 1 or Little Barford in the past.",
                )
            ],
        ),
        rep(
            "Q03  ",
            "ESO answer 45: no direct ride-through tests; simulation studies",
            [
                src(
                    "APP",
                    91,
                    APP_M + ", answer 45",
                    "There are no direct tests for generator ride-through for fault and large "
                    "frequency changes. This would require application of an intentional fault to "
                    "the transmission system and could compromise the integrity of the system. "
                    "Simulation studies are performed by the asset owner to demonstrate generator "
                    "ride-through capability for fault and large/rapid frequency changes. The ESO "
                    "will not issue an Interim Operational Notice to the generator until it has "
                    "reviewed these studies and determined that they are in line with Grid Code "
                    "requirements.",
                )
            ],
        ),
        frame("PART 4", "Part heading"),
        rep(
            "G01  ",
            "Ofgem 3.13: compliance checks not sufficiently robust",
            [
                ofg(
                    27,
                    OFG_ESO + ", 3.13",
                    "We have not found any evidence to suggest the ESO has failed to meet its "
                    "requirements under the Grid Code in this area. The ESO was not aware of any "
                    "potential compliance issues with Hornsea 1 or Little Barford ahead of the "
                    "event. However, the processes the ESO used to check their respective "
                    "compliance with the Grid Code do not appear to be sufficiently robust. The "
                    "ESO relied significantly on self-certification by Hornsea 1 for the "
                    "generator’s commissioning process as demonstration of the generator’s "
                    "compliance with the Grid Code, despite the complexity of the connection. "
                    "Following Little Barford’s major refurbishment in 2011/12, the ESO relied "
                    "on the RWE’s confirmation that the modifications had not impacted the "
                    "generator’s compliance with the Grid Code requirements for generators to "
                    "remain stable following network faults. No independent compliance testing or "
                    "verification was carried out.",
                )
            ],
        ),
        rep(
            "G02  ",
            "Ofgem 3.14: limits of ESO understanding of Hornsea 1 control system",
            [
                ofg(
                    27,
                    OFG_ESO + ", 3.14",
                    "In addition, we have found limitations in the ESO’s understanding of "
                    "Hornsea 1’s control system and the interaction between its onshore and "
                    "offshore arrangements. This limited understanding impaired the ESO’s view "
                    "of Hornsea 1’s performance after it was impacted by the fault.",
                )
            ],
        ),
        rep(
            "G03  ",
            "Ofgem 3.15: reconnection before root cause analysis",
            [
                ofg(
                    28,
                    OFG_ESO + ", 3.15",
                    "Lastly, the ESO allowed both Hornsea 1 and Little Barford to reconnect to the "
                    "transmission system without taking adequate steps to determine the root cause "
                    "of each failure. In the case of Hornsea 1, this meant the wind farm was "
                    "reconnected to the system and returned to service following confirmation "
                    "from the generator that the faulted equipment had been removed from service "
                    "but before the full root cause analysis had been completed.",
                ),
                ofg(
                    28,
                    OFG_ESO + ", 3.15",
                    "when Hornsea 1 was still going through Grid Code compliance processes for "
                    "commissioning generators",
                ),
            ],
        ),
        rep(
            "G04  ",
            "Ofgem 3.16: procedures may need clarifying and strengthening",
            [
                ofg(
                    28,
                    OFG_ESO + ", 3.16",
                    "The Grid Code procedures which the ESO is required to follow for checking "
                    "generators’ compliance with the code may need to be clarified and "
                    "strengthened.",
                ),
                ofg(
                    28,
                    OFG_ESO + ", 3.16",
                    "We would expect the ESO to review the adequacy of the procedures it carries "
                    "out and flag potential compliance concerns to Ofgem.",
                ),
            ],
        ),
        rep(
            "G05  ",
            "Ofgem executive summary: licensees and the ESO",
            [
                ofg(
                    6,
                    OFG_EXEC,
                    "Some licensees do not appear to have met their licence and code requirements "
                    "and the event highlights the importance of robust industry compliance "
                    "processes.",
                ),
                ofg(
                    6,
                    OFG_EXEC,
                    "We have not identified any failures by the ESO to meet its requirements "
                    "which contributed to the outage.",
                ),
            ],
        ),
        frame("PART 5", "Part heading"),
        rep(
            "P01  ",
            "Ofgem 3.20: Hornsea modules deloaded from around 737 MW; 62 MW remained",
            [
                ofg(
                    29,
                    OFG_H + ", 3.20",
                    "Hornsea 1’s two fully operational modules deloaded from around 737MW to "
                    "zero generation automatically after the lightning strike, whilst its "
                    "remaining module continued to generate at 62MW. This occurred after the "
                    "network fault on the Eaton Socon-Wymondley circuits had been rectified.",
                )
            ],
        ),
        rep(
            "P02  ",
            "Ofgem 3.22: prior modelling not discussed with the ESO; software update dates",
            [
                ofg(
                    29,
                    OFG_H + ", 3.22",
                    "We have also identified from the information Ørsted provided to us that "
                    "modelling it carried out with its equipment manufacturer prior to 9 August "
                    "suggested that there were performance issues with the voltage control system "
                    "with Hornsea 1 operating at its full planned 1,200MW capacity. These issues "
                    "were not discussed with the ESO. The manufacturer proposed a software update "
                    "to mitigate these issues which Ørsted informed us it had planned to carry out "
                    "on 13 August but implemented on 10 August immediately following the event. "
                    "The issue on 9 August occurred when the wind farm reached generation of "
                    "799MW. Prior simulations and discussions had not foreseen such issues would "
                    "occur at this capacity, nor that the windfarm would become unstable and "
                    "de-load, even at full load.",
                )
            ],
        ),
        rep(
            "P03  ",
            "Ofgem 3.23: no direct notification; uncoordinated restart",
            [
                ofg(
                    29,
                    OFG_H + ", 3.23",
                    "Hornsea 1 did not notify the ESO directly when the wind farm deloaded by "
                    "737MW. The wind farm then began its process of starting up two of its modules "
                    "(temporarily) without",
                ),
                ofg(
                    30,
                    OFG_H + ", 3.23",
                    "any coordination with the ESO whilst the ESO was attempting to respond to the "
                    "generation losses it was aware of.",
                ),
            ],
        ),
        rep(
            "P04  ",
            "Ofgem 3.24: FRT 90% within 0.5 s and damping requirements; acknowledgements",
            [
                ofg(
                    30,
                    OFG_H + ", 3.24",
                    "The Grid Code requirements on generators’ responses to network faults, "
                    "known as Fault Ride Through requirements, are fundamental to the security and "
                    "resilience of the power system. The Grid Code requires that generators must "
                    "remain connected and transiently stable following a fault on the transmission "
                    "system, with power output recovering to at least 90% within 0.5 seconds. "
                    "Hornsea 1 has acknowledged that it did not meet this requirement, having "
                    "deloaded following the fault23. In addition, Hornsea 1 has accepted that it "
                    "did not meet the Grid Code requirement to have an overall voltage control "
                    "system which appropriately dampens or limits swings24.",
                ),
                ofg(
                    30,
                    OFG_H + ", footnote 23",
                    "Grid Code Connection Condition CC. 6.3.15.1",
                ),
                ofg(
                    30,
                    OFG_H + ", footnote 24",
                    "Grid Code Connection Condition CC. A.7.2.5.2 Voltage Control (Oscillations)",
                ),
            ],
        ),
        rep(
            "P05  ",
            "Ofgem 3.26: Little Barford did not continue providing power; contributed",
            [
                ofg(
                    30,
                    OFG_L + ", 3.26",
                    "As set out above, Fault Ride Through requirements are fundamental to the "
                    "security and resilience of the power system. However, Little Barford’s "
                    "generators did not continue providing power to the system following the "
                    "lightning strike, and this contributed to the power outage.",
                )
            ],
        ),
        rep(
            "P06  ",
            "Ofgem 3.28-3.29: root causes not established; preliminary view; RWE acknowledgement",
            [
                ofg(
                    31,
                    OFG_L + ", 3.28",
                    "We have established that the steam turbine tripped initially because of a "
                    "discrepancy in the three independent speed sensors on the turbine. This "
                    "discrepancy exceeded the tolerance of the control system, causing the "
                    "generator to automatically shut down. The root cause of the discrepancy in "
                    "the speed sensors has not been established.",
                ),
                ofg(
                    31,
                    OFG_L + ", 3.29",
                    "its safety systems automatically shut down one of the gas turbines due to "
                    "excessive pressure in the steam bypass. The steam system pressure continued "
                    "to rise after this and the plant operators made the decision to manually trip "
                    "the other operational gas turbine due to safety risks. The root cause of "
                    "these high pressure conditions has not been established. Given the sequence "
                    "of events and in absence of an established root cause, it is our preliminary "
                    "view that the steam turbine’s anomalous speed readings and the resulting "
                    "trip were due to the transmission network fault following the lightning "
                    "strike. RWE Generation has acknowledged the role it played in contributing to "
                    "the power outage by not continuing to provide power to the system following "
                    "the fault.",
                ),
            ],
        ),
        rep(
            "P07  ",
            "Ofgem 3.36: DNO overview",
            [
                ofg(
                    33,
                    OFG_DNO + ", 3.36",
                    "We have found that most DNOs would appear to have met the requirements in the "
                    "Grid Code regarding low frequency demand disconnection. However, we found "
                    "some issues with essential services being disconnected, and found areas for "
                    "improvement in the LFDD arrangements. We have also found concerning evidence "
                    "that some DNOs disconnected distributed generation via LFDD that was "
                    "providing either",
                ),
                ofg(
                    34,
                    OFG_DNO + ", 3.36",
                    "frequency response or reserve services. We have found that most DNOs "
                    "reconnected customers as required but found issues with two DNOs which could "
                    "potentially have jeopardised the recovery of the system.",
                ),
            ],
        ),
        rep(
            "P08  ",
            "Ofgem 3.43: EPN and SPN reconnected without instruction",
            [
                ofg(
                    35,
                    OFG_DNO + ", 3.43",
                    "Our findings on the DNOs’ reconnection of demand following Stage 1 of "
                    "LFDD suggest that they generally performed as expected. However, Eastern "
                    "Power Networks plc and South Eastern Power Networks plc (both owned by UK "
                    "Power Networks) reconnected sites without being told to do so by the ESO, "
                    "and acknowledge that they do not appear to have technically met the "
                    "requirements of the Grid Code29. These instances were caused by the "
                    "configuration of the DNOs’ operational systems. The system frequency was "
                    "successfully restored to 50Hz following the LFDD activation on 9 August. "
                    "However, the premature demand",
                ),
                ofg(35, OFG_DNO + ", footnote 29", "Grid Code Operation Code 6.6.4"),
                ofg(
                    36,
                    OFG_DNO + ", 3.43",
                    "reconnection by Eastern Power Networks plc and South Eastern Power Networks "
                    "plc could potentially have jeopardised this outcome.",
                ),
            ],
        ),
        rep(
            "P09  ",
            "Ofgem executive summary: two DNOs reconnected before instructions",
            [
                ofg(
                    5,
                    OFG_EXEC,
                    "Two DNOs (Eastern Power Networks plc and South Eastern Power Networks plc, "
                    "owned by UK Power Networks) reconnected customers in England before the",
                ),
                ofg(
                    6,
                    OFG_EXEC,
                    "required instructions from the ESO and this could have jeopardised recovery "
                    "of the system.",
                ),
            ],
        ),
        rep(
            "P10  ",
            "Ofgem 3.44: SP Distribution 22 MW in Scotland",
            [
                ofg(
                    36,
                    OFG_DNO + ", 3.44",
                    "SP Distribution erroneously disconnected 22MW in Scotland when system "
                    "frequency fell below 48.8Hz and reconnected customers without informing the "
                    "ESO. As SP Distribution is part of the SP Transmission network area, it is "
                    "not required by the Grid Code to disconnect demand until frequency reaches "
                    "48.5Hz. The demand disconnection occurred due to an incorrect setting in the "
                    "DNO’s LFDD equipment. Since SP Distribution was not responding to an "
                    "LFDD event in this case, it does not appear to have contravened the Grid Code "
                    "in its disconnection or prompt reconnection of demand without informing the "
                    "ESO",
                )
            ],
        ),
        rep(
            "P11  ",
            "Ofgem 3.17-3.18: NGET clearance under 75 ms; voltage 390-410 kV",
            [
                ofg(
                    28,
                    OFG_NGET,
                    "Evidence NGET has submitted to us shows its fault clearance times for the two "
                    "circuit breakers were under 75ms, and that the voltage remained within a range "
                    "of 390kV to 410kV following the fault. The evidence suggests that NGET’s "
                    "transmission assets performed as expected based on its Grid Code and SQSS "
                    "requirements.",
                )
            ],
        ),
        rep(
            "P12  ",
            "Ofgem 3.31-3.32: DG over 5 MW de-loaded; settings possibly not changed",
            [
                ofg(
                    32,
                    OFG_DG + ", 3.31",
                    "However, some generators with capacities greater than 5MW were reported to "
                    "have de-loaded during the event and the cause of this is still to be "
                    "determined precisely. These generators’ RoCoF protection settings should "
                    "have been changed following Distribution Code modifications made in 201426.",
                ),
                ofg(
                    33,
                    OFG_DG + ", 3.32",
                    "It is possible that the frequency protection settings on some generators were "
                    "not changed in line with these Distribution Code requirements.",
                ),
            ],
            numbers=("2014",),
            transformation="Ofgem prints '201426' (2014 followed by footnote marker 26).",
        ),
    ],
}


# --------------------------------------------------------------------------- S11


def eso(page: int, section: str, quote: str) -> dict[str, Any]:
    return src("ESO", page, section, quote)


def orr(page: int, section: str, quote: str) -> dict[str, Any]:
    return src("ORR", page, section, quote)


def e3c(page: int, quote: str, section: str = E3C_4) -> dict[str, Any]:
    return src("E3C", page, section, quote)


def e3ci(page: int, part: str, quote: str) -> dict[str, Any]:
    return src("E3C-I", page, f"{E3CI_ES}, {part}", quote)


INDEX_NOTE = (
    "Index entry written for this record (decision 51 practice): the statement or article is not "
    "openly licensed and is neither reproduced nor closely paraphrased; verify_fi_recon.py checks "
    "that no run of four consecutive words is shared with the indexed text and that each fact is "
    "on the saved page."
)

S11_SPEC: dict[str, Any] = {
    "construction": (
        "Hand-authored (builder/full_investigation/recon/text/S11.src.txt, laid out by "
        "fi_text.py). Impacts are grouped by service (rail and transport supplies, hospitals, "
        "airports, water, refinery/chemicals/gas), each item restating one published account in "
        "that source's terms; Part 6 holds attributed post-event statements. No mechanism is "
        "added that the sources do not state: e.g. the E3C interim hospital with incorrect "
        "protection settings is not identified with Ipswich Hospital, the refinery is not named, "
        "and the water and airport sites are not named beyond the sources. Differences are kept "
        "(Newcastle 18 minutes 16:53-17:11 per ESO/NPG vs 17 minutes per the E3C interim vs "
        "'within minutes' per Ofgem; Wirral LFDD per ORR/Ofgem/E3C vs 'no track supplies lost due "
        "to LFDD' per the DNOs in ESO 5.2; traction substations 'quickly reinstated' per ORR vs "
        "'switched to back-up generation' per E3C; Ipswich internal protection per ESO vs the "
        "trust's statement that a breaker failed). Part 7 indexes two non-open web items: the "
        "Ipswich Hospital trust statement (10 August 2019) and a 12 September 2019 trade-press "
        "item about a different refinery event, which the record labels only by its date."
    ),
    "segments": [
        frame("DOCUMENT S11", HEADER),
        rep(
            "Clock reference:",
            "Clock basis: hh:mm as printed, read as BST",
            [CLOCK_ESO],
            numbers=("01:00",),
            transformation=BST_NOTE,
        ),
        frame("Value-status legend:", LEGEND + "; Part 7 note"),
        frame("PART 1", "Part heading"),
        rep(
            "P01  ",
            "ESO 5.2: DNOs say no track supplies lost to LFDD; Network Rail's statement",
            [
                ESO_DATE,
                eso(
                    27,
                    ESO_52,
                    "The DNOs confirmed that no track supplies were lost due to the DNO’s LFDD "
                    "protection operation. Through their investigation, Network Rail have stated "
                    "that their supply disruption was likely to have been caused by supply "
                    "interruption from the DNO networks. Network Rail are to undertake key "
                    "discussions with the DNOs to explore further.",
                ),
            ],
        ),
        rep(
            "P02  ",
            "ESO 5.2: traction power maintained; two DC traction trips; eight signal supplies",
            [
                eso(
                    27,
                    ESO_52,
                    "While the built-in resilience of Network Rail’s electrical power "
                    "infrastructure meant traction power was maintained to the vast majority of "
                    "the railway throughout the incident, there were supply related trips which "
                    "occurred at two DC traction locations which Network Rail are investigating "
                    "further.",
                ),
                eso(
                    27,
                    ESO_52,
                    "Eight signal power supplies in principally rural locations suffered minor "
                    "outages with minimal passenger impact. Network Rail are reviewing resilience "
                    "at these locations with the DNOs.",
                ),
            ],
        ),
        rep(
            "P03  ",
            "ESO 5.2: Victoria Line suspended, restored 17:35; UKPN and LUL statements",
            [
                eso(
                    27,
                    ESO_52,
                    "London Underground have confirmed there were impacts on the London "
                    "Underground Victoria Line, which was suspended as a result of the event and "
                    "service was restored at 17:35hrs. UKPN have confirmed that LFDD did not "
                    "impact the Victoria line. The UKPN control room made contact with LUL who "
                    "confirmed they did not lose power supplies at any stations, but they had an "
                    "internal traction issue.",
                )
            ],
        ),
        rep(
            "P04  ",
            "ORR 1.0/2.4: Wirral line traction outage after LFDD; 428 minutes",
            [
                ORR_DATE,
                orr(
                    3,
                    ORR_1,
                    "There was also loss of traction power on the Wirral line of MerseyRail, but "
                    "in other areas, there was no report of traction power outage.",
                ),
                orr(
                    6,
                    ORR_24,
                    "There was traction power outage on the Wirral line of the MerseyRail after "
                    "rectifiers tripped when domestic supply was lost to LFDD. This resulted in "
                    "428 minutes delay.",
                ),
            ],
        ),
        rep(
            "P05  ",
            "ORR 2.4: Tattenham and Chipstead rectifiers",
            [
                orr(
                    7,
                    ORR_24,
                    "The substations at Tattenham and Chipstead also experienced power quality "
                    "issues, which caused the protective devices for the traction rectifiers to "
                    "operate, temporarily switching the power off. The rectifiers were however "
                    "quickly reinstated. The resilience of the system meant that traction power "
                    "supply was maintained during this time.",
                )
            ],
        ),
        rep(
            "P06  ",
            "ORR 2.4: Chatham and Lewes DNO supply points",
            [
                orr(
                    7,
                    ORR_24,
                    "During the time of the power disruption there was also a loss of two DNO "
                    "supply points at Chatham and Lewes. This is still under investigation and "
                    "may have been caused by LFDD.",
                )
            ],
        ),
        rep(
            "P07  ",
            "ORR 2.4: eight signalling supplies and their locations",
            [
                orr(
                    7,
                    ORR_24,
                    "eight signalling power supplies were lost in rural locations. The affected "
                    "locations were fed by local DNO networks which may have been affected by the "
                    "LFDD implementation. Affected locations were: • Wye, Kent • "
                    "Southease, Sussex • Norwood Fork, London • Trowbridge, Wiltshire "
                    "• Magor, Wales • Bangor, Wales • Croes Newydd, Wales • "
                    "Kirby Thore, Cumbria Investigations are still ongoing to understand, if the "
                    "power disruption led to the loss of signal supplies in the affected eight "
                    "locations.",
                )
            ],
        ),
        rep(
            "P08  ",
            "ORR 4.0: Network Rail electrical system; resilience work",
            [
                orr(
                    11,
                    ORR_4,
                    "Network Rail’s electrical system reacted well although some resilience "
                    "issues were identified. Network Rail have begun work to ensure, where "
                    "necessary, adequate back up supplies are available for non-traction "
                    "essential supplies and are working with the DNO to improve resilience.",
                )
            ],
        ),
        rep(
            "P09  ",
            "Ofgem 2.8: Wirral by SP Energy Networks' LFDD; TfL stations; signalling sites",
            [
                OFG_DATE,
                ofg(
                    20,
                    OFG_2 + ", 2.8",
                    "The traction supplies to the Wirral line on Merseyrail were disconnected as a "
                    "result of SP Energy Networks’ LFDD operations. Three Transport for London "
                    "stations and eight signalling sites at rural locations across England and "
                    "Wales were also thought to have been affected by LFDD operations, although "
                    "traction supplies were unaffected.",
                ),
            ],
        ),
        rep(
            "P10  ",
            "E3C final section 4: Wirral 428 minutes; three TfL stations",
            [
                E3C_DATE,
                e3c(
                    18,
                    "It was also reported that power supplies to the local Wirral Line were "
                    "interrupted by the LFDD scheme causing a 428 minute delay for passengers.",
                ),
                e3c(
                    18,
                    "Three Transport for London stations were also disconnected as a result of "
                    "LFDD operations. Traction supplies to these sites were maintained throughout "
                    "the incident, resulting in minimal impact to passengers.",
                ),
            ],
        ),
        rep(
            "P11  ",
            "E3C final section 4: signalling assets; traction substations on back-up",
            [
                e3c(
                    18,
                    "Eight rail signalling assets were also affected, principally in rural "
                    "locations across England and Wales, with minimal customer impact. 2 assets "
                    "were disconnected as a result of the LFDD scheme with investigations ongoing "
                    "into the cause of disruption for the remaining six assets.",
                ),
                e3c(
                    19,
                    "Two railway traction substations in the South of England were also disrupted "
                    "as a result of the drop in frequency on the electricity network; these assets "
                    "automatically switched to back-up generation with no impacts to customer "
                    "services.",
                ),
            ],
        ),
        frame("PART 2", "Part heading"),
        rep(
            "H01  ",
            "ESO 5.3: Ipswich Hospital internal protection; load halved in 14 seconds",
            [
                eso(
                    28,
                    ESO_53,
                    "Ipswich Hospital internal protection operated coincident with the timeframe "
                    "of the lightning strike. Time stamped data from UKPN shows that the "
                    "hospital’s load reduced by half in a period of 14 seconds.",
                )
            ],
        ),
        rep(
            "H02  ",
            "ESO 5.3: hospital not in UKPN's LFDD protection zone",
            [
                eso(
                    28,
                    ESO_53,
                    "UKPN have confirmed that the hospital was not part of their LFDD protection "
                    "zone and that the LFDD did not affect the substations supplying the hospital.",
                )
            ],
        ),
        rep(
            "H03  ",
            "ESO executive summary: Ipswich hospital",
            [
                eso(
                    4,
                    ESO_EXEC_CONS,
                    "Impacts to other critical facilities including Ipswich hospital (lost power "
                    "due to the operation of their own protection systems)",
                )
            ],
        ),
        rep(
            "H04  ",
            "E3C interim: two hospitals LFDD; another with incorrect protection settings",
            [
                e3ci(
                    12,
                    "Health",
                    "A DNO confirmed to us that two hospitals were affected by LFDD with their "
                    "back-up generation working as designed. Another hospital was affected by the "
                    "fall in frequency/voltage excursion, despite not being disconnected as part of "
                    "LFDD. This was due to incorrect protection settings on the hospital’s own "
                    "network, which resulted in the site switching over to back-up generation and "
                    "one of its 11 generators failing to operate.",
                )
            ],
        ),
        rep(
            "H05  ",
            "E3C final section 4: four hospitals",
            [
                e3c(
                    19,
                    "Four hospitals were impacted by the power outage; two were disconnected by "
                    "the LFDD scheme and a further two hospitals were disconnected by their "
                    "internal safety systems. All hospitals automatically switched to back-up "
                    "power supplies to ensure continued operation.",
                )
            ],
        ),
        rep(
            "H06  ",
            "Ofgem 2.11: hospitals",
            [
                ofg(
                    20,
                    OFG_2 + ", 2.11",
                    "two hospitals were disconnected as part of the LFDD and their back-up "
                    "generators were activated. The E3C has reported that two other hospitals were "
                    "disconnected by their own safety systems but switched to back-up generation.",
                )
            ],
        ),
        frame("PART 3", "Part heading"),
        rep(
            "A01  ",
            "ESO 5.3: Newcastle Airport disconnected by NPG LFDD; ESEC protected sites",
            [
                eso(
                    28,
                    ESO_53,
                    "Newcastle Airport is connected to the NPG Network. NPG have confirmed that "
                    "the airport was disconnected as a result of the LFDD operation. The LFDD "
                    "scheme operated by NPG worked as planned. NPG are nonetheless reviewing all "
                    "LFDD allocations. As far as NPG are aware, no Protected Sites under the terms "
                    "of the Electricity Supply Emergency Code (ESEC) were affected by the "
                    "incident.",
                )
            ],
        ),
        rep(
            "A02  ",
            "ESO 5.3: 18 minutes between 16:53 and 17:11; UPS and standby generation",
            [
                eso(
                    28,
                    ESO_53,
                    "Newcastle International Airport was affected, losing supplies from the "
                    "network for 18 minutes between 16:53 and 17:11. NPG indicated that the "
                    "airport’s Uninterruptable Power Supply (UPS) and standby generator "
                    "resilience arrangements for their essential services operated smoothly.",
                )
            ],
        ),
        rep(
            "A03  ",
            "ESO 5.3: request to be a Protected Site under ESEC",
            [
                eso(
                    28,
                    ESO_53,
                    "On 12 August 2019 Northern Powergrid (Northeast) Limited received a request "
                    "from Newcastle International Airport to be categorised as a Protected Site "
                    "under ESEC and it has now been registered as such.",
                )
            ],
        ),
        rep(
            "A04  ",
            "ESO executive summary: Newcastle airport",
            [
                eso(
                    4,
                    ESO_EXEC_CONS,
                    "Newcastle airport (disconnected by the Low Frequency Demand Disconnection "
                    "scheme)",
                )
            ],
        ),
        rep(
            "A05  ",
            "E3C interim: two airports; 17 minutes; up to 50 minutes for some services",
            [
                e3ci(
                    13,
                    "Airports",
                    "DNOs have confirmed to us that two airports, one in the Midlands and one in "
                    "the north of England, were impacted by the power disruption. One airport was "
                    "impacted as a result of LFDD stage 1 being automatically triggered. The "
                    "airport had its own standby generation for its safety critical systems and "
                    "power was restored via the distribution network after 17 minutes. The second "
                    "airport, unaffected by LFDD, switched to-back up power supplies without issue "
                    "and was restored within a few minutes. A fault with its on site internal "
                    "network meant that power to some services (check-in hall, central security "
                    "search, hold baggage screening, and some telephony and comms systems) was "
                    "delayed for up to 50 minutes.",
                )
            ],
        ),
        rep(
            "A06  ",
            "E3C final section 4: airports; ~50 minutes",
            [
                e3c(
                    19,
                    "Two airports were impacted following the power disruptions. Newcastle airport "
                    "was disconnected from the electricity network following the LFDD and utilised "
                    "back-up generation. The second airport was not impacted by the LFDD but "
                    "switched to back-up power supplies and was restored within a few minutes. A "
                    "fault with the on-site internal network disrupted some services like the "
                    "check-in hall for ~50 minutes.",
                )
            ],
        ),
        rep(
            "A07  ",
            "Ofgem 2.10: airports",
            [
                ofg(
                    20,
                    OFG_2 + ", 2.10",
                    "Newcastle airport was disconnected as part of LFDD. The E3C has reported that "
                    "standby generation was in place and power restored within minutes at "
                    "Newcastle airport. It has also reported that a second airport switched to its "
                    "back-up power supplies without issue although it was not affected by LFDD.",
                )
            ],
        ),
        frame("PART 4", "Part heading"),
        rep(
            "W01  ",
            "E3C interim: approximately 3,000 people; booster pumps; 30 minutes",
            [
                e3ci(
                    12,
                    "Water",
                    "Approximately 3,000 people experienced water supply disruptions due to "
                    "booster water pumping stations failing to automatically switch over to "
                    "back-up power supplies. Some of these customers would have experienced a "
                    "temporary loss of running water",
                ),
                e3ci(
                    13,
                    "Water",
                    "in their homes, but others would have remained unaffected due to water "
                    "storage in the system allowing running water to continue. The majority of "
                    "customers were restored within 30 minutes.",
                ),
            ],
        ),
        rep(
            "W02  ",
            "E3C final section 4: treatment works; 3000 to c.180 customers",
            [
                e3c(
                    19,
                    "The water sector experienced minimal impacts. This included two water "
                    "treatment works being disconnected; one through the LFDD scheme and one as "
                    "result of the company’s internal safety systems. Additionally, one water "
                    "company reporting a reduction in water pressure to 3000 customers due to "
                    "booster water pumping stations failing to automatically switch to back-up "
                    "power. This was reduced to c.180 customers within 30 minutes.",
                )
            ],
        ),
        rep(
            "W03  ",
            "Ofgem 2.11: water pumping stations disconnected by LFDD",
            [
                ofg(
                    20,
                    OFG_2 + ", 2.11",
                    "Some water pumping stations were disconnected as part of the LFDD. The E3C "
                    "has reported that their back-up supplies were not connected automatically "
                    "and, as a result, several thousand customers experienced some disruption to "
                    "their running water supply.",
                )
            ],
        ),
        frame("PART 5", "Part heading"),
        rep(
            "F01  ",
            "E3C interim: oil refinery disconnected by its own system; weeks to restore",
            [
                e3ci(
                    13,
                    "Energy",
                    "An oil refinery has confirmed to us that it was disconnected as a result of "
                    "the site’s system which detected a drop in frequency and disconnected "
                    "the plant to protect on- site equipment. The refinery operations team "
                    "utilised the site’s emergency procedures and automated systems to safely "
                    "shutdown portions of the plant however, due to the complexity of restarting "
                    "large process units it took a few weeks to restore normal operations.",
                )
            ],
        ),
        rep(
            "F02  ",
            "E3C final section 4: refinery and chemicals plant",
            [
                e3c(
                    19,
                    "Wider industry reported the disconnection of an oil refinery and chemicals "
                    "manufacturing plant due to internal safety systems detecting the drop-in "
                    "frequency. To protect the assets, both plants safely shutdown operations; it "
                    "took several weeks for the refinery to resume full operations.",
                )
            ],
        ),
        rep(
            "F03  ",
            "E3C interim: gas networks' response plans",
            [
                e3ci(
                    13,
                    "Energy",
                    "It is worth noting that the gas networks and transmission operator reported "
                    "to us that they implemented their response mitigation plans in a timely way",
                )
            ],
        ),
        frame("PART 6", "Part heading"),
        rep(
            "N01  ",
            "E3C final section 4: no agreed definition of essential service",
            [
                e3c(
                    18,
                    "There is currently no agreed definition of what constitutes an essential "
                    "service in this context. In this report ‘essential service’ has been "
                    "used to cover organisations that rely on electricity in order to provide "
                    "important daily services as well as critical industries, for example "
                    "hospitals, airports, oil refineries and rail services.",
                )
            ],
        ),
        rep(
            "N02  ",
            "E3C final section 4: routes by which services were disrupted",
            [
                e3c(
                    18,
                    "Whilst the 9 August power disruption was relatively short-lived, several "
                    "sectors experienced impacts and did not resume operations for several days. "
                    "Some essential services experienced disruption due to being directly "
                    "disconnected from the electricity network through the LFDD mechanism. "
                    "However, others experienced disruption as a result of their automatic safety "
                    "systems reacting unexpectedly to the frequency and voltage fluctuations "
                    "affecting their electricity network or having insufficient business "
                    "continuity measures in place.",
                )
            ],
        ),
        rep(
            "N03  ",
            "Ofgem 2.5: direct LFDD disconnection vs own safety systems",
            [
                ofg(
                    19,
                    OFG_2 + ", 2.5",
                    "Some essential service providers were directly disconnected as part of Stage "
                    "1 of the LFDD and disrupted as their back-up power supply arrangement were not "
                    "effective. Other services were affected indirectly because the providers’ "
                    "own safety systems were configured to automatically disconnect when system "
                    "frequency fell.",
                )
            ],
        ),
        rep(
            "N04  ",
            "Ofgem 3.41-3.42: LFDD not site-level; back-up failures; DNO approaches differ",
            [
                ofg(
                    35,
                    OFG_DNO + ", 3.41",
                    "On 9 August, several essential service providers (such as hospitals and "
                    "airports) were disconnected as part of LFDD.",
                ),
                ofg(
                    35,
                    OFG_DNO + ", 3.41",
                    "This is because the LFDD equipment does not operate at an individual site "
                    "level and so isolating particular sites is generally unfeasible.",
                ),
                ofg(
                    35,
                    OFG_DNO + ", 3.41",
                    "Disruptions experienced at the sites of essential service providers directly "
                    "impacted by the power outage were generally caused by failures in their "
                    "back-up power arrangements.",
                ),
                ofg(
                    35,
                    OFG_DNO + ", 3.42",
                    "However, we have found that DNOs have significantly different approaches to "
                    "evaluating which areas to disconnect during Stage 1 of the LFDD",
                ),
            ],
        ),
        frame("PART 7", "Part heading"),
        rep(
            "X01  ",
            "Index entry: Ipswich Hospital trust statement of 10 August 2019",
            [
                real_src(
                    "esneft_ipswich_hospital_statement",
                    "publisher",
                    "East Suffolk and North Essex NHS Foundation Trust",
                ),
                real_src(
                    "esneft_ipswich_hospital_statement",
                    "clock_basis",
                    "datePublished 2019-08-10T10:09:37+00:00",
                ),
                real_src(
                    "esneft_ipswich_hospital_statement", "event_visible", "No times."
                ),
                raw_src("RAW-ESNEFT", "which runs Ipswich Hospital", "statement"),
                raw_src(
                    "RAW-ESNEFT",
                    "we experienced a small power issue on site",
                    "statement",
                ),
                raw_src(
                    "RAW-ESNEFT",
                    "The emergency generators at the hospital all worked, but a circuit breaker in "
                    "our outpatients department did not. This briefly cut the electrical supply to "
                    "our outpatients and x-ray department. We activated our business continuity "
                    "plans and this was quickly resolved. All other areas of the hospital were "
                    "unaffected",
                    "statement",
                ),
            ],
            method="index_entry",
            transformation=INDEX_NOTE,
        ),
        rep(
            "X02  ",
            "Index entry: trade-press item dated 12 September 2019 (Stanlow)",
            [
                real_src(
                    "stanlow_12sep2019_power_cut_article",
                    "publisher",
                    "Hydrocarbon Processing (Reuters)",
                ),
                real_src(
                    "stanlow_12sep2019_power_cut_article",
                    "event_visible",
                    "12 Sep 2019 Stanlow supply failure",
                ),
                raw_src(
                    "RAW-STANLOW",
                    "The unplanned shutdown at the plant resulted in visible flaring.",
                    "article",
                ),
                raw_src(
                    "RAW-STANLOW",
                    "the power supply... to Stanlow from the national grid failed",
                    "article",
                ),
            ],
            method="index_entry",
            transformation=INDEX_NOTE,
        ),
    ],
}


# --------------------------------------------------------------------------- R10 Sections F-K

APP_M34 = APP_M + ", answer 34"
APP_M37 = APP_M + ", answer 37"
APP_M45 = APP_M + ", answer 45"

R10_ADDITION_SEGMENTS: list[dict[str, Any]] = [
    rep(
        "Sources added for Sections F to K:",
        "Sources and abbreviations for Sections F-K",
        [ESO_DATE, OFG_DATE, E3C_DATE, ORR_DATE, GTR_DATE],
    ),
    frame("SECTION F", "Section heading"),
    rep(
        "F1   ",
        "Ofgem 3.24: Fault Ride Through, 90% within 0.5 s (CC.6.3.15.1)",
        [
            ofg(
                30,
                OFG_H + ", 3.24",
                "The Grid Code requirements on generators’ responses to network faults, known "
                "as Fault Ride Through requirements, are fundamental to the security and "
                "resilience of the power system. The Grid Code requires that generators must "
                "remain connected and transiently stable following a fault on the transmission "
                "system, with power output recovering to at least 90% within 0.5 seconds.",
            ),
            ofg(
                30,
                OFG_H + ", footnote 23",
                "Grid Code Connection Condition CC. 6.3.15.1",
            ),
        ],
    ),
    rep(
        "F2   ",
        "Ofgem 3.24: voltage control damping (CC.A.7.2.5.2)",
        [
            ofg(
                30,
                OFG_H + ", 3.24",
                "the Grid Code requirement to have an overall voltage control system which "
                "appropriately dampens or limits swings",
            ),
            ofg(
                30,
                OFG_H + ", footnote 24",
                "Grid Code Connection Condition CC. A.7.2.5.2 Voltage Control (Oscillations)",
            ),
        ],
    ),
    rep(
        "F3   ",
        "Ofgem 2.12: transmission-connected generators to remain connected",
        [
            ofg(
                21,
                OFG_212,
                "Transmission-connected generators have a requirement to remain connected and "
                "continue providing power to the system following faults on the transmission "
                "network.",
            )
        ],
    ),
    rep(
        "F4   ",
        "ESO 2.4: CUSC, Grid Code capabilities, OTSDUW",
        [
            eso(
                8,
                ESO_24,
                "Generators that make use of the transmission networks are entitled to do so "
                "because they are signatories to the CUSC and have a connection agreement with "
                "National Grid ESO. The CUSC in turn places an obligation on generators to meet the "
                "requirements of the Grid Code, including any site-specific criteria in their "
                "connection agreement.",
            ),
            eso(
                8,
                ESO_24,
                "The Grid Code sets out a range of capabilities that a generator must have, "
                "including voltage control and frequency control. It is the Grid Code that states "
                "what a generator is expected to do during and after a network fault.",
            ),
            eso(
                8,
                ESO_24,
                "During the period when an offshore network and generation connection is being "
                "developed, the project is treated in the same way as a generator would be (the "
                "precise term is Offshore Transmission System Development User Works – "
                "OTSDUW) and is subject to Grid Code requirements.",
            ),
        ],
    ),
    rep(
        "F5   ",
        "E3C final chapter 1: CUSC and Grid Code capabilities",
        [
            e3c(
                10,
                "Generators that connect to the transmission network are required to comply with "
                "the Connection and Use of System Code7 and the Grid Code8. These documents set "
                "out the range of capabilities that a generator must have, including voltage "
                "control and frequency control, and what a generator is expected to do during and "
                "after a fault on the network.",
                E3C_1,
            )
        ],
    ),
    frame("SECTION G", "Section heading"),
    rep(
        "G1   ",
        "ESO 2.4: compliance process; generators to assure themselves",
        [
            eso(
                8,
                ESO_24,
                "The Grid Code also sets out an extensive process for new generators to "
                "demonstrate that they can meet certain requirements to enable safe connection. "
                "The details are set out in the CP (Compliance Process) section of the code. It is "
                "for the generators to assure themselves of their compliance with the Grid Code "
                "requirements.",
            )
        ],
    ),
    rep(
        "G2   ",
        "Appendix G: responsibilities and stage gates",
        [
            app_g(
                52,
                "Generators are responsible for demonstrating and maintaining compliance with the "
                "Grid Code both when connecting to the system initially and on an ongoing basis.",
                "Overview of the Compliance Testing Process",
            ),
            app_g(
                52,
                "Compliance is demonstrated through a combination of studies, simulations and "
                "testing of the generator. The ESO runs the compliance process and supports the "
                "generator in achieving compliance. For the initial connection of any large[1] or "
                "directly connected generator, the generator proceeds through a number of stage "
                "gates in the process: energisation stage, interim operational stage and final "
                "operation stage. The generator must provide the required compliance evidence at "
                "each stage. The ESO is responsible for assessing this information against the "
                "Grid Code requirements and issues a notice to proceed through the stage gate if "
                "compliance has been met.",
                "Overview of the Compliance Testing Process",
            ),
        ],
    ),
    rep(
        "G3   ",
        "Appendix G: notify changes; ESO not checking ongoing; LON after 84 days",
        [
            app_g(
                52,
                "If the generator makes any changes to its configuration which may impact "
                "compliance, it is responsible for firstly notifying the ESO of the change and "
                "then ensuring that it demonstrates compliance. The ESO is not responsible for "
                "checking compliance on an ongoing basis.",
                "Overview of the Compliance Testing Process",
            ),
            app_g(
                52,
                "If a generator believes it would require more than 84 days to resolve any "
                "compliance issues, the ESO issues a Limited Operational Notice (LON) to the "
                "generator and work with them to achieve full compliance",
                "Overview of the Compliance Testing Process",
            ),
        ],
    ),
    rep(
        "G4   ",
        "Appendix G footnote: large generator thresholds",
        [
            app_g(
                52,
                "The definition of large generator in the Grid Code is: greater that 99.9 MW in "
                "England & Wales; greater than 9.9MW in Scottish Hydro Electricity Transmission; "
                "greater than 29.9MW in Scottish Power region; 9.9 MW offshore",
                "footnote 1",
            )
        ],
    ),
    rep(
        "G5   ",
        "Appendix D glossary: EON, ION (Part A/B), FON",
        [
            src(
                "APP",
                37,
                APP_D_GL,
                "EON – Energisation Operational Notification – first milestone in "
                "commissioning process",
            ),
            src(
                "APP",
                37,
                APP_D_GL,
                "FON – Final Operational Notification – the last milestone in the "
                "commissioning process",
            ),
            src(
                "APP",
                37,
                APP_D_GL,
                "ION (Part A) Interim Operational Notification (for dynamic reactive "
                "compensation on OFTO assets) second milestone in commissioning process",
            ),
            src(
                "APP",
                37,
                APP_D_GL,
                "ION (Part B) Interim Operational Notification (to export active power) "
                "second/third milestone in commissioning process",
            ),
        ],
    ),
    rep(
        "G6   ",
        "ESO answer 45: no direct ride-through tests; studies reviewed before ION",
        [
            src(
                "APP",
                91,
                APP_M45,
                "There are no direct tests for generator ride-through for fault and large "
                "frequency changes. This would require application of an intentional fault to the "
                "transmission system",
            ),
            src(
                "APP",
                91,
                APP_M45,
                "Simulation studies are performed by the asset owner to demonstrate generator "
                "ride-through capability for fault and large/rapid frequency changes. The ESO will "
                "not issue an Interim Operational Notice to the generator until it has reviewed "
                "these studies and determined that they are in line with Grid Code requirements.",
            ),
        ],
    ),
    frame("SECTION H", "Section heading"),
    rep(
        "H1   ",
        "Ofgem 3.43 and footnote 29: reconnection without ESO instruction; OC6.6.4",
        [
            ofg(
                35,
                OFG_DNO + ", 3.43",
                "reconnected sites without being told to do so by the ESO, and acknowledge that "
                "they do not appear to have technically met the requirements of the Grid Code29.",
            ),
            ofg(35, OFG_DNO + ", footnote 29", "Grid Code Operation Code 6.6.4"),
        ],
    ),
    frame("SECTION I", "Section heading"),
    rep(
        "I1   ",
        "ESO answer 34: communication to Ofgem and BEIS; Energy Incident Reporting",
        [
            src(
                "APP",
                88,
                APP_M34,
                "Current ESO procedure outlines that following an event of loss of supply, a clear "
                "communication to Ofgem & BEIS is essential. The communication is recommended to "
                "be initiated as soon as possible, and this procedure is in line with the "
                "‘Energy Incident Reporting’ requirement set by Ofgem dated in December "
                "2017. It is important in all cases that resolution of the incident remains the "
                "primary objective.",
            )
        ],
    ),
    rep(
        "I2   ",
        "ESO answer 37: system warnings by fax; control telephony; contacts document",
        [
            src(
                "APP",
                89,
                APP_M37,
                "Where GB Transmission System Warnings are applicable to System conditions or "
                "Events, which have widespread effect, NGESO will in accordance with the Grid Code "
                "notify Users by fax",
            ),
            src(
                "APP",
                89,
                APP_M37,
                "Control Telephony is used for instructing Demand Control",
            ),
            src(
                "APP",
                89,
                APP_M37,
                "The ENCC Power System Manager (PSM) and duty officer have access to the SO "
                "communications document, which is regularly maintained by the business "
                "continuity team. This document holds up-to- date contact information, that can be "
                "used during such an event, including: BEIS and OFGEM duty officers; TO and DNO "
                "Control Room managers; contacts within generation and supply companies; and "
                "internal media and escalation contacts",
            ),
        ],
    ),
    frame("SECTION J", "Section heading"),
    rep(
        "J1   ",
        "E3C final chapter 3: no Grid Code protection for essential services",
        [
            e3c(
                16,
                "The primary purpose of the LFDD is to stabilise the system. Therefore, the Grid "
                "Code contains no requirement for the DNOs to afford particular groups of "
                "customers, for example essential services, any form of protection. Although DNOs "
                "have some discretion in how they disconnect demand, this is largely dictated by "
                "the architecture of the system.",
                E3C_3,
            )
        ],
    ),
    rep(
        "J2   ",
        "Ofgem 3.41: no obligation to refrain; not site-level; back-up supplies",
        [
            ofg(
                35,
                OFG_DNO + ", 3.41",
                "There is no obligation on DNOs to refrain from disconnecting such providers in "
                "their LFDD requirements",
            ),
            ofg(
                35,
                OFG_DNO + ", 3.41",
                "This is because the LFDD equipment does not operate at an individual site level",
            ),
            ofg(
                35,
                OFG_DNO + ", 3.41",
                "Individual customers operating essential services should therefore maintain and "
                "operate back-up power supplies to deal with the power outages.",
            ),
        ],
    ),
    rep(
        "J3   ",
        "ESO 5.3: ESEC Protected Sites",
        [
            eso(
                28,
                ESO_53,
                "no Protected Sites under the terms of the Electricity Supply Emergency Code "
                "(ESEC) were affected by the incident.",
            ),
            eso(
                28,
                ESO_53,
                "received a request from Newcastle International Airport to be categorised as a "
                "Protected Site under ESEC",
            ),
        ],
    ),
    rep(
        "J4   ",
        "ORR 2.4: LFDD band; duty holder's back-up responsibility",
        [
            orr(
                6,
                ORR_24,
                "48.8 Hz is one of the low frequency demand disconnection (LFDD) bands where the "
                "Distribution Network Operator (DNO) sheds load to stabilise the system and to "
                "protect essential services such as the rail traction supply. However, it is the "
                "duty holder’s responsibility to ensure backup systems are in place to "
                "maintain functionality where loss of power may lead to emergency situations. "
                "Backup systems could include generators, uninterruptable power supplies (UPS) or "
                "specific contracts with DNO.",
            )
        ],
    ),
    frame("SECTION K", "Section heading"),
    rep(
        "K1   ",
        "ORR 1.0/2.1: GL/RT1210 and BS EN 50163:2004 lower limit 47.0 Hz",
        [
            orr(
                3,
                ORR_1,
                "The Railway Group Standard GL/RT1210 AC Energy Subsystem and Interfaces to "
                "Rolling Stock Subsystem and BS EN 50163:2004 Railway applications —Supply "
                "voltages of traction systems, specifies a lower frequency limit of 47.0Hz.",
            ),
            orr(
                4,
                ORR_21,
                "specify that a traction power supply may have a lower frequency limit of 47.0Hz.",
            ),
        ],
    ),
    rep(
        "K2   ",
        "ORR 2.1: advisory note 49.0-51.0 Hz",
        [
            orr(
                5,
                ORR_21,
                "However, an advisory note to the standard defines a narrower range of 49.0Hz to "
                "51.0Hz within which the train is required to operate normally. Outside this "
                "range, it is permitted to reduce performance or to disconnect the vehicle "
                "drives.",
            )
        ],
    ),
    rep(
        "K3   ",
        "ORR 3.4: Interoperability Regulations, Energy TSI, BS EN 50163 Note 2",
        [
            orr(
                10,
                ORR_34,
                "The trains were introduced using the interoperability process imposed by the "
                "Railways (Interoperability) Regulations 2011, which requires compliance with "
                "Technical Specifications for Interoperability (TSI). Standard BS EN 50163:2004 "
                "is mandated by the Energy TSI.",
            ),
            orr(
                10,
                ORR_34,
                "Note 2: In practice, the variation of frequency is more closely controlled in "
                "Europe than stated above. Vehicles will operate only within frequency tolerances "
                "25kV/50Hz range from 49Hz to 51Hz. If the frequency is out of this range, the "
                "vehicles performance may be reduced or the vehicle drives shall be disconnected"
                "” [BS EN 50163:2004+A1:2007 Clause4.2 Note 2]",
            ),
        ],
        numbers=("4.2",),
        transformation="ORR prints 'Clause4.2'; written as 'Clause 4.2'.",
    ),
    rep(
        "K4   ",
        "GTR cause 3: NR/GN/ELP/27010, 48.5 Hz in extreme conditions",
        [
            src(
                "APP",
                49,
                f"{APP_F}, Cause, item 3",
                "The NR Electrification System Compatibility document, NR/GN/ELP/27010 "
                "(“Guidance for compatibility between electric trains and electrification "
                "systems”), a Manufacturing and Supply Agreement compliance requirement, "
                "identifies that the supply frequency can fall to 48.5Hz in extreme conditions.",
            )
        ],
    ),
    rep(
        "K5   ",
        "Ofgem 2.7: traction supply standards 47 Hz and 49-51 Hz",
        [
            ofg(
                20,
                OFG_2 + ", 2.7",
                "Traction supply standards in the rail sector specify a lower operating limit of "
                "47Hz, however, they also refer to a narrower range of 49Hz – 51Hz within "
                "which the trains are required to operate normally. Outside this range, they are "
                "permitted to reduce their performance or disconnect",
            )
        ],
    ),
]

R10_ADDITIONS_CONSTRUCTION = (
    " Full-investigation edition: lines 1-133 are the system-response R10 unchanged "
    "(byte-identical, so its line locators still resolve); Sections F-K are appended from "
    "builder/full_investigation/recon/text/R10_additions.src.txt and restate, item by item, "
    "the fault-ride-through and voltage-damping requirements Ofgem describes, the ESO's account "
    "of the generator compliance process, the reconnection and incident-notification "
    "arrangements as described, LFDD and essential services, and rail traction-supply frequency "
    "limits as ORR, GTR and Ofgem describe them. Clause numbers appear only where a report's "
    "footnote cites them; no ESQCR duty or OC7/OC10 obligation is restated (handoff T19), and "
    "ORR's 2.1 sentence attributing the 50 Hz +/-0.5 Hz range to the SQSS and the ESQCR is left "
    "out for that reason (the SQSS limits are already in Section A)."
)
