"""S09 witness fact cards added for the full investigation (reconstructed; roles, not people).

Increment A's five cards are copied unchanged into the full-investigation bundle by the
integration step; these five are new. The conventions are increment A's (decision 24,
``builder/system_response/recon/recon_witnesses.py``): each block answers one subject in the
first person of the role and restates only what its provenance passages say (every quote is
checked on its page; every number in an answer occurs in the block's quotes or section labels).
A block never presents another party's findings as the witness's own knowledge: other parties'
accounts are attributed ("ORR's report gives ...", "Ofgem reports ..."), and where published
accounts of the witness's own organisation differ, the block gives both (documented
disagreement). Topics name subjects, never findings. Anything else gets the card's fixed
``unknown_response``. The hospital card's statement summary is a builder-written index entry
(the trust's statement is not openly licensed and is not reproduced).
"""

from __future__ import annotations

from typing import Any

from fi_doc_specs import (
    APP_F,
    APP_M,
    E3C_4,
    E3CI_ES,
    E3CI_EXEC,
    ESO_7,
    ESO_52,
    ESO_53,
    OFG_2,
    OFG_DNO,
    OFG_H,
    ORR_1,
    ORR_4,
    ORR_22,
    ORR_23,
    ORR_24,
    ORR_31,
    ORR_32,
    ORR_T1,
)
from fi_recon_common import WITNESS_EVIDENCE_ID, cat_src, raw_src, real_src, src

ESO_25 = "2.5 DNO Roles and Responsibilities"
ESO_61 = "6.1 Operational Communications"
ESO_62 = "6.2 Engagement with government and the regulator"
ESO_63 = "6.3 External Communications with Media and Wider Industry, Table 8"
ESO_64 = "6.4 Communications by industry and consumers"
ESO_T6 = "5.1 Distribution Demand, Table 6 - DNO customers affected by LFDD relays"
ESO_T9 = "6.4, Table 9 - Calls received by the 6 largest DNOs"


def block(
    response_id: str, topics: list[str], text: str, provenance: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "response_id": response_id,
        "topics": topics,
        "response_text": text,
        "provenance": provenance,
    }


def app(page: int, section: str, quote: str) -> dict[str, Any]:
    return src("APP", page, section, quote)


# --------------------------------------------------------------------------- GTR

GTR_CARD = {
    "persona_id": "gtr-fleet-engineer",
    "role": "Fleet engineer, Govia Thameslink Railway (GTR) fleet control",
    "organisation": "Govia Thameslink Railway (GTR)",
    "unknown_response": "Not known — that is not covered by the GTR fleet records I can "
    "speak to.",
    "blocks": [
        block(
            "S09-GTR-01",
            ["units affected", "protective shutdown", "4QC", "fleet affected"],
            "All our Desiro City Class 700 and 717 units operating on AC suffered a Protective "
            "Shutdown: the converter known as the 4QC (4 Quadrant Controller) shut down. In "
            "passenger service that was circa 60 [estimated] units, Class 700 FLU/RLUs and Class "
            "717. None of our other AC trains, for example Class 387, Class 365 or Class 313, had "
            "power-related issues from the event.",
            [
                app(
                    48,
                    f"{APP_F}, Event Summary, item 3",
                    "All Desiro City class 700 and 717 units operating on AC Voltage suffered a "
                    "Protective Shutdown where the converter, known as the 4QC (4 Quadrant "
                    "Controller) shut down. None of the other AC trains in the GTR fleet suffered "
                    "any power related issues from this event e.g. Class 387, Class 365, Class 313.",
                ),
                app(
                    48,
                    f"{APP_F}, Event Summary, item 4",
                    "In Passenger Service this involved circa 60 units, consisting of Class 700 "
                    "FLU/RLUs and Class 717, suffering a 4QC lock out.",
                ),
            ],
        ),
        block(
            "S09-GTR-02",
            ["train condition after shutdown", "battery power", "onboard systems"],
            "With the 4QC shut down the train switches to battery power: no traction power, loss "
            "of HVAC apart from fan-only fresh air, reduced standby lighting, no at-seat power and "
            "no PIS displays, with audio only from the cab. The GSM-R radio stays active.",
            [
                app(
                    48,
                    f"{APP_F}, Event Summary, item 5",
                    "The effect of the 4QC shutting down on the train is that the train switches to "
                    "battery power which causes a loss of HVAC (fan only fresh air supply), stand by "
                    "reduced lighting (emergency lighting is activated when battery voltage drops), "
                    "no at seat power, no PIS displays (audio only from the cab), and no traction "
                    "power. The GSM-R radio remains active.",
                )
            ],
        ),
        block(
            "S09-GTR-03",
            ["battery reset", "driver reset", "recovery by drivers"],
            "After failed attempts to repower the trains, the established first response is a "
            "driver reboot known as a Battery Reset, which takes approximately 10 minutes "
            "[estimated]. Fleet Control diagnosed the issue quickly and a global GSM-R call told "
            "drivers to carry out the Battery Reset. After this, 27 [reported] of the affected "
            "units were recovered.",
            [
                app(
                    48,
                    f"{APP_F}, Event Summary, items 6-8",
                    "Following failed attempts to repower the trains, the established first "
                    "response for a train failing with these symptoms is for the Driver to perform "
                    "a reboot of the train known as a Battery Reset. This takes approximately 10 "
                    "minutes. 7. Fleet Control diagnosed the issue quickly and a global GSM-R call "
                    "was broadcast to instruct drivers to carry out the Battery Reset process. 8. "
                    "After this 27 of the affected units were recovered.",
                ),
            ],
        ),
        block(
            "S09-GTR-04",
            ["technician resets", "technicians", "laptop recovery", "evacuations"],
            "The remaining circa 30 [estimated] units needed a technician with a laptop to attend "
            "each one to unlock the Protective Shutdown; our review also states that "
            "30 [reported] trains were not recoverable by Battery Reset. 17 [reported] technicians "
            "were available and were sent immediately, and a further 24 [reported] were mobilised "
            "within the next hour. The trains were widely spread and some were not easily "
            "accessible, so this took some time and resulted in 23 [reported] train evacuations.",
            [
                app(
                    48,
                    f"{APP_F}, Event Summary, items 9-11",
                    "The remaining circa 30 units required the Protective Shutdown to be unlocked "
                    "by the intervention of a Technician with a laptop attending each unit. 10. "
                    "There were 17 Technicians available at the time of the event. These 17 were "
                    "immediately sent to stranded units with laptops and a further 24 technicians "
                    "were mobilized within the next hour. The trains affected were widely spread "
                    "geographically and some were not easily accessible. 11. Therefore, this "
                    "process took some time and resulted in 23 train evacuations",
                ),
                app(
                    49,
                    f"{APP_F}, Cause, item 6",
                    "All trains should have been recoverable via Battery Reset whereas 30 trains "
                    "were not recoverable.",
                ),
            ],
        ),
        block(
            "S09-GTR-05",
            ["software versions", "TCMS software", "software change"],
            "The new TCMS software version 3.27 removed the driver's ability to recover from a "
            "Permanent Lockout by Battery Reset. On 9 August every unit that needed a technician "
            "to recover power was at software level 3.27 or above; the 28 [reported] units the "
            "drivers recovered by Battery Reset were at the previous level, 3.25 or below. The "
            "fleet was undergoing that software change at the time.",
            [
                app(
                    49,
                    f"{APP_F}, Cause, item 8",
                    "Separately as a part of the new TCMS (Train Control Management System) "
                    "software version 3.27, the ability for the driver to recover from a Permanent "
                    "Lockout by using the Battery Reset process was removed.",
                ),
                app(
                    49,
                    f"{APP_F}, Cause, item 9",
                    "On the 9th of August all the units which required a Technician to recover "
                    "power were at software level 3.27 or above. The 28 units recovered by the "
                    "driver performing a Battery Reset were at the previous TCMS software level of "
                    "3.25 or below.",
                ),
                app(
                    50,
                    f"{APP_F}, Conclusion, item 3",
                    "The effects of this were exacerbated as the fleet was undergoing a software "
                    "change",
                ),
            ],
        ),
        block(
            "S09-GTR-06",
            ["frequency threshold", "design threshold", "train specification"],
            "Siemens advised that the train's supply frequency response was designed to comply "
            "with EN 50163 Clause 4.2 Note 2, which permits the drives to disconnect at 49 Hz "
            "[reported], so the train shut its drives down when the supply fell below 49 Hz "
            "[reported]. The Siemens technical specification says the train will keep operating "
            "with drops down to 48.5 Hz [reported] for short periods, and NR/GN/ELP/27010 "
            "identifies that the supply can fall to 48.5 Hz [reported] in extreme conditions.",
            [
                app(
                    49,
                    f"{APP_F}, Cause, item 5",
                    "Siemens advised that the supply frequency response of the train was designed "
                    "to comply with the EN 50163 Clause 4.2 Note 2. This note permits train drives "
                    "to disconnected at 49Hz. Use of this supply frequency value in the train "
                    "design led to the train protectively shutting down its drives when the supply "
                    "frequency response fell below 49Hz.",
                ),
                app(
                    49,
                    f"{APP_F}, Cause, item 2",
                    "Siemens Technical Specification for the train states that the train will "
                    "continue to operate with supply frequency drops down to 48.5Hz for short "
                    "periods of time.",
                ),
                app(
                    49,
                    f"{APP_F}, Cause, item 3",
                    "NR/GN/ELP/27010 (“Guidance for compatibility between electric trains and "
                    "electrification systems”), a Manufacturing and Supply Agreement "
                    "compliance requirement, identifies that the supply frequency can fall to "
                    "48.5Hz in extreme conditions.",
                ),
            ],
        ),
        block(
            "S09-GTR-07",
            ["design intent", "intended behaviour", "why the lockout happened"],
            "Siemens clarified that a supply frequency drop should not have led to a Permanent "
            "Lockout; all trains should have been recoverable by Battery Reset. It was not how "
            "the train system had been specified to operate, and the risk was not known before "
            "the power event on Friday 9 August.",
            [
                app(
                    49,
                    f"{APP_F}, Cause, items 6-7",
                    "Importantly Siemens have also clarified that there should not have been a "
                    "Permanent Lockout on the train following a protective shutdown caused by a "
                    "supply voltage frequency drop. All trains should have been recoverable via "
                    "Battery Reset",
                ),
                app(
                    49,
                    f"{APP_F}, Cause, item 7",
                    "The risk of this happening was not known prior to the power event on Friday 9 "
                    "August.",
                ),
                app(
                    50,
                    f"{APP_F}, Conclusion, item 2",
                    "This was not how the train system had been specified to operate.",
                ),
            ],
        ),
        block(
            "S09-GTR-08",
            [
                "supply frequency information",
                "information from National Grid",
                "OLE supply",
            ],
            "Our review records that, from information supplied by the National Grid at 1653, the "
            "frequency of the OLE AC supply dropped below 49 Hz [reported] for 16 seconds "
            "[reported], and below 48.89 Hz [reported] to a minimum of 48.8 Hz [reported] for "
            "milliseconds. There was no identified OLE AC supply interruption.",
            [
                app(
                    48,
                    f"{APP_F}, Event Summary, items 1-2",
                    "From information supplied by the National Grid at 1653 on Friday the 9th of "
                    "August the frequency of the OLE AC voltage supply dropped below 49Hz for 16 "
                    "seconds. It dropped below 48.89Hz to a minimum of 48.8 Hz for milliseconds. 2. "
                    "There was no identified OLE AC Voltage supply interruption.",
                )
            ],
        ),
        block(
            "S09-GTR-09",
            ["mitigation", "software patch", "changes after the event"],
            "Siemens are developing a patch so that units which shut down below 49 Hz [reported] "
            "recover by themselves, without a reboot or laptop, when the frequency rises above "
            "49.5 Hz [reported], and will investigate how the train could operate for a short "
            "time with the supply falling to 48.5 Hz [reported]. Siemens and GTR do not propose "
            "reverting units to earlier software versions, because of concerns that this could "
            "severely affect unit availability.",
            [
                app(
                    50,
                    f"{APP_F}, Planned Mitigation, items 1-3",
                    "Siemens are developing a software patch to allow units which protectively "
                    "shutdown below 49Hz supply frequency to recover themselves without the need of "
                    "a reboot or laptop when the frequency rises above 49.5Hz. 2. It is not proposed "
                    "by Siemens or GTR to revert units to previous software versions as there are "
                    "concerns this could severely impact unit availability.",
                ),
                app(
                    50,
                    f"{APP_F}, Planned Mitigation, item 3",
                    "In addition to this Siemens will investigate how the train could be made to "
                    "operate for a short time with supply frequency falling to 48.5Hz.",
                ),
            ],
        ),
        block(
            "S09-GTR-10",
            ["ORR figures", "regulator's report", "ORR published counts"],
            "ORR's report, which summarises its engagement with Ofgem, Network Rail, GTR and "
            "Siemens, states that 29 [reported] trains were locked out, of which 22 [reported] "
            "needed a technician and 7 [reported] were restored by driver reset; that two Class "
            "387 trains were also trapped; and that 18 [reported] technicians were sent "
            "immediately. It describes the protection as operating within 200 ms [reported] of "
            "the frequency falling to 49.0 Hz [reported].",
            [
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "On the Class 700 and Class 717 rolling stock, protection systems operated "
                    "within 200ms of the frequency falling to 49.0Hz causing a lock-out of 29 "
                    "trains. 22 trains were permanently locked-out and could not be reset without a "
                    "technician attending on site while 7 trains were restored through "
                    "driver-reset. Two Class 387 trains were also trapped",
                ),
                src(
                    "ORR",
                    5,
                    ORR_22,
                    "18 Technicians with laptops were sent to restore the trains immediately",
                ),
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "This report summarises ORR’s engagement with Ofgem, Network Rail, GTR and "
                    "Siemens following the power disruption",
                ),
            ],
        ),
        block(
            "S09-GTR-11",
            ["lock-out types", "lock-out recovery"],
            "ORR describes the units on software 3.25.x as going into a temporary lock-out that "
            "drivers could clear with a battery reset, and the units on 3.27.x as going into a "
            "permanent lock-out that needed a technician. Siemens brought in the permanent "
            "lock-out in 3.27.x so that a battery reset could not clear a lock-out imposed for a "
            "serious fault; detection of a low power supply frequency was among the trigger "
            "conditions selected.",
            [
                src(
                    "ORR",
                    9,
                    ORR_31,
                    "On detecting the frequency drop, the units with software version 3.25.x went "
                    "into a temporary lock-out while the units with version 3.27.x went into "
                    "permanent lock-out. The drivers were able to reset units with a temporary "
                    "lock-out by carrying out a battery reset, while the units with a permanent "
                    "lockout required a technician to attend to perform a reset.",
                ),
                src(
                    "ORR",
                    9,
                    ORR_32,
                    "Siemens decided to implement a “permanent lock-out” in software "
                    "version 3.27.x that could not be cleared by a battery reset.",
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
    ],
}

# --------------------------------------------------------------------------- Network Rail

NR_CARD = {
    "persona_id": "network-rail-control-manager",
    "role": "Control duty manager, Network Rail (railway infrastructure operator)",
    "organisation": "Network Rail",
    "unknown_response": "Not known — that is not in the Network Rail records I can speak to.",
    "blocks": [
        block(
            "S09-NR-01",
            ["traction power", "overhead line supply", "electrical infrastructure"],
            "The overhead line power supply operated continually, and the built-in resilience of "
            "our electrical power infrastructure maintained traction power to the vast majority "
            "of the railway throughout the incident. There were supply-related trips at two DC "
            "traction locations, which we are investigating further.",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The Network Rail overhead line power supply operated continually.",
                ),
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "While the built-in resilience of Network Rail’s electrical power "
                    "infrastructure meant traction power was maintained to the vast majority of "
                    "the railway throughout the incident, there were supply related trips which "
                    "occurred at two DC traction locations which Network Rail are investigating "
                    "further.",
                ),
            ],
        ),
        block(
            "S09-NR-02",
            ["traction substations", "rectifiers", "Tattenham and Chipstead"],
            "ORR's report says the substations at Tattenham and Chipstead had power quality "
            "issues that operated the protective devices of the traction rectifiers, switching "
            "the power off temporarily; the rectifiers were quickly reinstated and traction "
            "supply was maintained. The E3C final report describes two railway traction "
            "substations in the South of England as automatically switching to back-up "
            "generation.",
            [
                src(
                    "ORR",
                    7,
                    ORR_24,
                    "The substations at Tattenham and Chipstead also experienced power quality "
                    "issues, which caused the protective devices for the traction rectifiers to "
                    "operate, temporarily switching the power off. The rectifiers were however "
                    "quickly reinstated. The resilience of the system meant that traction power "
                    "supply was maintained during this time.",
                ),
                src(
                    "E3C",
                    19,
                    E3C_4,
                    "Two railway traction substations in the South of England were also disrupted "
                    "as a result of the drop in frequency on the electricity network; these assets "
                    "automatically switched to back-up generation",
                ),
            ],
        ),
        block(
            "S09-NR-03",
            ["Wirral line", "Merseyrail", "traction outage"],
            "According to ORR, traction power was lost on the Wirral line of Merseyrail after "
            "rectifiers tripped when domestic supply was lost to LFDD, causing 428 minutes "
            "[reported] of delay; elsewhere no traction power outage was reported. Ofgem "
            "attributes the disconnection of the Wirral line traction supplies to SP Energy "
            "Networks' LFDD operations.",
            [
                src(
                    "ORR",
                    6,
                    ORR_24,
                    "There was traction power outage on the Wirral line of the MerseyRail after "
                    "rectifiers tripped when domestic supply was lost to LFDD. This resulted in 428 "
                    "minutes delay.",
                ),
                src(
                    "ORR",
                    3,
                    ORR_1,
                    "but in other areas, there was no report of traction power outage.",
                ),
                src(
                    "OFG",
                    20,
                    OFG_2 + ", 2.8",
                    "The traction supplies to the Wirral line on Merseyrail were disconnected as a "
                    "result of SP Energy Networks’ LFDD operations.",
                ),
            ],
        ),
        block(
            "S09-NR-04",
            ["signalling supplies", "signal power", "rural signalling"],
            "Eight signalling power supplies in rural locations were lost: Wye, Southease, "
            "Norwood Fork, Trowbridge, Magor, Bangor, Croes Newydd and Kirby Thore, all fed by "
            "local DNO networks that may have been affected by LFDD; investigations into the "
            "cause are ongoing. The ESO's report describes them as minor outages with minimal "
            "passenger impact, and the E3C final report says 2 [reported] of the eight were "
            "disconnected by the LFDD scheme. We are reviewing resilience at these locations with "
            "the DNOs.",
            [
                src(
                    "ORR",
                    7,
                    ORR_24,
                    "eight signalling power supplies were lost in rural locations. The affected "
                    "locations were fed by local DNO networks which may have been affected by the "
                    "LFDD implementation. Affected locations were: • Wye, Kent • "
                    "Southease, Sussex • Norwood Fork, London • Trowbridge, Wiltshire "
                    "• Magor, Wales • Bangor, Wales • Croes Newydd, Wales • "
                    "Kirby Thore, Cumbria Investigations are still ongoing",
                ),
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "Eight signal power supplies in principally rural locations suffered minor "
                    "outages with minimal passenger impact. Network Rail are reviewing resilience "
                    "at these locations with the DNOs.",
                ),
                src(
                    "E3C",
                    18,
                    E3C_4,
                    "2 assets were disconnected as a result of the LFDD scheme",
                ),
            ],
        ),
        block(
            "S09-NR-05",
            ["cause of supply disruption", "DNO supplies", "supply interruption"],
            "Our investigation stated that our supply disruption was likely to have been caused "
            "by supply interruption from the DNO networks, and we are to discuss this further "
            "with the DNOs. The DNOs, for their part, confirmed to the ESO that no track supplies "
            "were lost due to their LFDD protection operation.",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The DNOs confirmed that no track supplies were lost due to the DNO’s LFDD "
                    "protection operation. Through their investigation, Network Rail have stated "
                    "that their supply disruption was likely to have been caused by supply "
                    "interruption from the DNO networks. Network Rail are to undertake key "
                    "discussions with the DNOs to explore further.",
                )
            ],
        ),
        block(
            "S09-NR-06",
            ["DNO supply points", "Chatham and Lewes"],
            "Two DNO supply points, at Chatham and Lewes, were lost during the disruption; ORR "
            "notes that this is still under investigation and may have been caused by LFDD.",
            [
                src(
                    "ORR",
                    7,
                    ORR_24,
                    "During the time of the power disruption there was also a loss of two DNO "
                    "supply points at Chatham and Lewes. This is still under investigation and may "
                    "have been caused by LFDD.",
                )
            ],
        ),
        block(
            "S09-NR-07",
            ["cancellations", "delay minutes", "service impact"],
            "Our National Daily Report for 9 August, as ORR tabulates it, totals 371 [reported] "
            "cancellations, 220 [reported] part-cancellations and 14428 [reported] delay minutes "
            "across eight routes: Sussex, Wessex, Kent, Western, LNE-York, LNE-EM, LNW-N and "
            "Wales. The ESO and E3C reports also give 873 [reported] trains delayed.",
            [
                src(
                    "ORR",
                    6,
                    ORR_T1,
                    "Wessex 0 2 716 Kent 36 43 1727 Western 0 0 658 LNE-York 86 44 5569 LNE-EM 197 "
                    "79 2780 LNW-N 14 24 428 Wales 0 6 499 TOTAL 371 220 14428 Table 1 – "
                    "Affected routes, cancellations and delays Source: Network Rail’s National "
                    "Daily Report 09/08/2019",
                ),
                src(
                    "ORR",
                    5,
                    ORR_T1,
                    "Routes Cancelled Part- Cancelled Delay Minutes Sussex 38 22 2051",
                ),
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "with 371 trains cancelled, 220 part cancelled, and 873 trains delayed.",
                ),
                src(
                    "E3C",
                    18,
                    E3C_4,
                    "371 cancelled services, 220 part cancelled services and 873 delayed services.",
                ),
            ],
        ),
        block(
            "S09-NR-08",
            ["stations", "station closures", "overcrowding"],
            "London St Pancras and King's Cross had to close for several hours because of "
            "overcrowding, and London Euston went exit only for a period, according to the ESO's "
            "report. The E3C interim report says St Pancras International, King's Cross and "
            "Euston had to limit passenger numbers entering the stations at various times.",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "London St Pancras and King’s Cross stations had to close for several "
                    "hours due to overcrowding and London Euston went exit only for a period of "
                    "time.",
                ),
                src(
                    "E3C-I",
                    12,
                    f"{E3CI_ES}, Rail",
                    "This led to St Pancras International, King’s Cross and Euston stations "
                    "having to limit passenger numbers entering the stations at various times.",
                ),
            ],
        ),
        block(
            "S09-NR-09",
            ["service recovery", "recovery of services", "following days"],
            "ORR reports that full service was restored within 24 hours [reported]. The E3C "
            "interim report says some trains were not in their correct locations at the end of "
            "the day, disrupting some early services on Saturday 10 August, and that rail delays "
            "extended into Sunday 11 August.",
            [
                src(
                    "ORR",
                    5,
                    ORR_23,
                    "However, full service was restored within 24 hours.",
                ),
                src(
                    "E3C-I",
                    12,
                    f"{E3CI_ES}, Rail",
                    "a number of trains did not end up in their correct location at the end of the "
                    "day, which led to some early morning services on Saturday 10 th August being "
                    "disrupted.",
                ),
                src(
                    "E3C-I",
                    4,
                    E3CI_EXEC,
                    "rail services which experienced major delays that extended into Sunday 11th "
                    "August.",
                ),
            ],
        ),
        block(
            "S09-NR-10",
            ["resilience work", "back-up supplies", "actions after the event"],
            "ORR reports that our electrical system reacted well although some resilience issues "
            "were identified, and that we have begun work to ensure adequate back-up supplies for "
            "non-traction essential supplies where necessary and are working with the DNO to "
            "improve resilience.",
            [
                src(
                    "ORR",
                    11,
                    ORR_4,
                    "Network Rail’s electrical system reacted well although some resilience "
                    "issues were identified. Network Rail have begun work to ensure, where "
                    "necessary, adequate back up supplies are available for non-traction essential "
                    "supplies and are working with the DNO to improve resilience.",
                )
            ],
        ),
        block(
            "S09-NR-11",
            ["train stoppages", "stopped trains", "Farringdon"],
            "Class 700 and 717 trains shut down north of Farringdon and Kings Cross because their "
            "own internal protection systems were triggered, and that delayed all the other "
            "trains behind them, according to the ESO's report.",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "Class 700 and 717 trains shut down north of Farringdon and Kings Cross "
                    "stations due to their internal protection systems being triggered.",
                ),
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "The shutdown of these trains had a knock-on impact by delaying all other "
                    "trains behind them",
                ),
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- UKPN (EPN/SPN)

UKPN_CARD = {
    "persona_id": "ukpn-epn-spn-control-engineer",
    "role": "Control engineer, UK Power Networks (Eastern Power Networks and South Eastern "
    "Power Networks licence areas)",
    "organisation": "UK Power Networks",
    "unknown_response": "Not known — that is not in the UK Power Networks records I can "
    "speak to.",
    "blocks": [
        block(
            "S09-UKPN-01",
            ["LFDD in our areas", "UKPN returns", "demand disconnected"],
            "The ESO's Table 6, based on DNO-reported data as of 13 August 2019 at 12:00, lists "
            "for UK Power Networks: Eastern 69 MW [reported], 79,390 [reported] customers, final "
            "restoration time 16:56 [reported]; London 174 MW [reported], 239,861 [reported] "
            "customers, 17:37 [reported]; Southern 69 MW [reported], 81,358 [reported] "
            "customers, 17:15 [reported].",
            [
                src(
                    "ESO",
                    26,
                    ESO_T6,
                    "The information is based on DNO reported data as of 13 August 2019 at 12:00.",
                ),
                src(
                    "ESO",
                    26,
                    ESO_T6,
                    "UK Power Networks (UKPN) Eastern 69 79,390 16:56 London 174 239,861 17:37 "
                    "Southern 69 81,358 17:15",
                ),
            ],
        ),
        block(
            "S09-UKPN-02",
            ["communication times", "calls with the ESO", "restoration instructions"],
            "The ESO's Table 7 gives, for UKPN SPN, 17:04 [reported] for when the ESO was "
            "informed of the demand loss and 17:13 [reported] for when it instructed restoration; "
            "for UKPN EPN, 17:04 [reported] and 17:14 [reported]; for UKPN LPN, 16:58 [reported] "
            "and 16:58 [reported]. Restoration complete is printed once across the three UKPN "
            "columns, 17:37 [reported]. The ESO's earlier answers to the E3C (data at 28 August "
            "2019) give 17:12 [reported] for the SPN instruction, 17:14 [reported] for EPN and "
            "'Approx. 17:40' [reported] for restoration complete.",
            [
                src("ESO", 29, ESO_61, "Table 7 – DNO Areas Communication times"),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN SPN",
                    "when_eso_informed_demand_loss",
                    "17:04",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN SPN",
                    "when_eso_instructed_restoration",
                    "17:13",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN EPN",
                    "when_eso_informed_demand_loss",
                    "17:04",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN EPN",
                    "when_eso_instructed_restoration",
                    "17:14",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN LPN",
                    "when_eso_informed_demand_loss",
                    "16:58",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN LPN",
                    "when_eso_instructed_restoration",
                    "16:58",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN EPN",
                    "when_restoration_complete",
                    "17:37",
                    ESO_61,
                ),
                cat_src(
                    "CAT-ESOT7",
                    "UKPN EPN",
                    "complete_cell_merged_across",
                    "UKPN SPN+EPN+LPN",
                    ESO_61,
                ),
                cat_src(
                    "CAT-APPQ33",
                    "UKPN SPN",
                    "instruct_restoration",
                    "17:12",
                    APP_M + ", answer 33",
                ),
                cat_src(
                    "CAT-APPQ33",
                    "UKPN EPN",
                    "instruct_restoration",
                    "17:14",
                    APP_M + ", answer 33",
                ),
                cat_src(
                    "CAT-APPQ33",
                    "UKPN EPN",
                    "restoration_complete",
                    "Approx. 17:40",
                    APP_M + ", answer 33",
                ),
                src(
                    "APP",
                    70,
                    APP_M,
                    "These answers are all based on the data available to the ESO on 28 August "
                    "2019.",
                ),
            ],
        ),
        block(
            "S09-UKPN-03",
            [
                "reconnection",
                "reconnection timing",
                "Grid Code requirements",
            ],
            "Ofgem reports that Eastern Power Networks plc and South Eastern Power Networks plc "
            "reconnected sites without being told to do so by the ESO, and that we acknowledge we "
            "do not appear to have technically met the requirements of the Grid Code. Ofgem says "
            "these instances were caused by the configuration of our operational systems, and "
            "that the premature reconnection could potentially have jeopardised the restoration "
            "of system frequency.",
            [
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.43",
                    "Eastern Power Networks plc and South Eastern Power Networks plc (both owned by "
                    "UK Power Networks) reconnected sites without being told to do so by the ESO, "
                    "and acknowledge that they do not appear to have technically met the "
                    "requirements of the Grid Code29. These instances were caused by the "
                    "configuration of the DNOs’ operational systems. The system frequency was "
                    "successfully restored to 50Hz following the LFDD activation on 9 August. "
                    "However, the premature demand",
                ),
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.43",
                    "reconnection by Eastern Power Networks plc and South Eastern Power Networks "
                    "plc could potentially have jeopardised this outcome.",
                ),
            ],
        ),
        block(
            "S09-UKPN-04",
            [
                "restoration rule",
                "instruction requirement",
                "restoring disconnected demand",
            ],
            "As the ESO's report describes Grid Code OC6.6, after the LFDD scheme operates the "
            "DNOs must notify the ESO of its operation and are not permitted to restore "
            "automatically disconnected demand without instruction from National Grid ESO.",
            [
                src(
                    "ESO",
                    8,
                    ESO_25,
                    "Grid Code OC6.6 describes the automatic LFDD scheme and the arrangements that "
                    "the DNO’s are required to make in relation to this scheme. Following "
                    "operation of this scheme, the DNO’s must notify ESO of its operation and "
                    "are not permitted to restore automatically disconnected demand without "
                    "instruction from National Grid ESO.",
                )
            ],
        ),
        block(
            "S09-UKPN-05",
            ["Ipswich Hospital", "hospital supply", "LFDD protection zone"],
            "We confirmed to the ESO that Ipswich Hospital was not part of our LFDD protection "
            "zone and that LFDD did not affect the substations supplying it. Our time-stamped "
            "data show the hospital's load reducing by half in a period of 14 seconds "
            "[reported].",
            [
                src(
                    "ESO",
                    28,
                    ESO_53,
                    "Time stamped data from UKPN shows that the hospital’s load reduced by "
                    "half in a period of 14 seconds. UKPN have confirmed that the hospital was not "
                    "part of their LFDD protection zone and that the LFDD did not affect the "
                    "substations supplying the hospital.",
                )
            ],
        ),
        block(
            "S09-UKPN-06",
            ["Victoria line", "London Underground", "LUL contact"],
            "We confirmed that LFDD did not affect the Victoria line. Our control room contacted "
            "London Underground, which confirmed that it had not lost power supplies at any "
            "stations but had an internal traction issue.",
            [
                src(
                    "ESO",
                    27,
                    ESO_52,
                    "UKPN have confirmed that LFDD did not impact the Victoria line. The UKPN "
                    "control room made contact with LUL who confirmed they did not lose power "
                    "supplies at any stations, but they had an internal traction issue.",
                )
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- ESO comms

ESOC_CARD = {
    "persona_id": "eso-communications-lead",
    "role": "Communications lead, National Grid ESO (stakeholder and media communications)",
    "organisation": "National Grid ESO",
    "unknown_response": "Not known — that is not covered by the ESO communications records I "
    "can speak to.",
    "blocks": [
        block(
            "S09-ESOC-01",
            ["BEIS contact", "government contact", "first call to BEIS"],
            "Our technical report's section 6.2 records the first communication between the "
            "ESO control room and BEIS at 17:41 [reported], when the event was generally "
            "understood, demand restoration was in progress and further disturbances were "
            "considered unlikely; further updates to BEIS followed at 18:09 [reported], "
            "19:29 [reported] and 19:38 [reported]. The report's findings section gives "
            "17:40 [reported] for contacting BEIS.",
            [
                src(
                    "ESO",
                    30,
                    ESO_62,
                    "The first communication between the ESO control room and BEIS was at 17:41hrs. "
                    "At this point the event was generally understood, demand restoration was in "
                    "progress and further disturbances were considered unlikely.",
                ),
                src(
                    "ESO",
                    30,
                    ESO_62,
                    "Further updates to BEIS from the ESO control room were made at 18:09hrs, "
                    "19:29hrs and 19:38hrs respectively.",
                ),
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "The ESO contacted BEIS at 17:40 and Ofgem at 18:00.",
                ),
            ],
        ),
        block(
            "S09-ESOC-02",
            ["Ofgem contact", "regulator contact", "first call to Ofgem"],
            "Our technical report's section 6.2 records the first communication with Ofgem at "
            "17:51 [reported], with further communication at 18:17 [reported] and 18:45 "
            "[reported]. The report's findings section says we contacted Ofgem at 18:00 "
            "[reported], and our earlier answers to the E3C, based on the data available on "
            "28 August 2019, say the first communication with Ofgem was made just after "
            "18:00 [reported] with the ESO Director of Operations.",
            [
                src(
                    "ESO",
                    30,
                    ESO_62,
                    "The first communication with Ofgem was made at 17:51hrs with further "
                    "communication at 18:17hrs and 18:45hrs and then throughout the weekend.",
                ),
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "The ESO contacted BEIS at 17:40 and Ofgem at 18:00.",
                ),
                src(
                    "APP",
                    88,
                    APP_M + ", answer 34",
                    "The 1st communication with Ofgem was made just after 18:00hrs with the "
                    "Director of Operations, ESO.",
                ),
                src(
                    "APP",
                    70,
                    APP_M,
                    "These answers are all based on the data available to the ESO on 28 August "
                    "2019.",
                ),
            ],
        ),
        block(
            "S09-ESOC-03",
            [
                "internal escalation",
                "Head of National Control",
                "control room escalation",
            ],
            "Our answers to the E3C record that at 17:10 [reported] the control room Power System "
            "Manager reported the incident to the ESO Head of National Control.",
            [
                src(
                    "APP",
                    88,
                    APP_M + ", answer 34",
                    "At 17:10hrs, the ENCC Power System Manager (PSM) reported the incident to the "
                    "Head of National Control, ESO.",
                )
            ],
        ),
        block(
            "S09-ESOC-04",
            ["public statements", "media statements", "statement timeline"],
            "Our first external communication was issued at 18:27 [reported] on 9 August, once "
            "it was established that the DNOs had reconnected all customers; it was published on "
            "Twitter, sent to national energy correspondents and newsdesks, and shared with BEIS "
            "and Ofgem. A second statement followed at 20:06 [reported] and a video from the Head "
            "of National Control at 20:11 [reported]; on Saturday a third statement was issued at "
            "08:33 [reported] and a fourth at 19:31 [reported].",
            [
                src(
                    "ESO",
                    30,
                    "6.3 External Communications with Media and Wider Industry",
                    "The first ESO external communication was issued at 18:27hrs on 9 August.",
                ),
                src(
                    "APP",
                    88,
                    APP_M + ", answer 35",
                    "which was issued at 18:27 once it was established that the DNOs had "
                    "reconnected all customers.",
                ),
                src(
                    "ESO",
                    30,
                    ESO_63,
                    "18:27 First Statement – Confirmed that whilst 2 generators had "
                    "disconnected the system was now functioning properly. Published on twitter "
                    "@NG_ESO and sent to all national energy correspondents, and national print, "
                    "TV and Radio newsdesks. Shared with BEIS and Ofgem. 20:06 Second statement",
                ),
                src(
                    "ESO",
                    33,
                    ESO_7,
                    "a video from the Head of National Control being posted at 20:11.",
                ),
                src("ESO", 30, ESO_63, "SATURDAY 08:00 – 13:00 Broadcast interviews"),
                src("ESO", 30, ESO_63, "08:33 Third Statement"),
                src("ESO", 31, ESO_63, "19:31 Fourth Statement"),
            ],
        ),
        block(
            "S09-ESOC-05",
            [
                "statements by others",
                "DNO and rail statements",
                "attribution of the cause",
            ],
            "In the ~90 minutes [estimated] after the initial fault, starting at 17.09 [reported] "
            "(5.09pm in our answers to the E3C), some DNOs and rail companies issued statements "
            "saying that the loss of power and disruption were the result of a National Grid "
            "fault. They were issued ahead of any ESO communication and without coordination with "
            "our communications team. They did not affect the speed with which the incident was "
            "resolved, but they drove a large volume of media queries to us.",
            [
                src(
                    "ESO",
                    31,
                    ESO_64,
                    "In the ~90 minutes immediately following the initial fault on the network "
                    "(starting at 17.09hrs) statements were issued by some DNOs and rail companies "
                    "stating that the loss of power and subsequent disruption was the result of a "
                    "National Grid fault. These statements were issued ahead of any communication "
                    "by the ESO and without engagement or coordination with the ESO communications "
                    "team. These public-facing communications did not impact the speed with which "
                    "the incident was resolved but did drive a large volume of media queries to the "
                    "ESO.",
                ),
                src(
                    "APP",
                    88,
                    APP_M + ", answer 35",
                    "These communications were issued very shortly after the event (from 5.09pm "
                    "onwards).",
                ),
            ],
        ),
        block(
            "S09-ESOC-06",
            ["call volumes", "helpline calls", "customer calls"],
            "Our Table 9 gives calls received by the six largest DNOs during the period 4pm to "
            "7pm on 9 August: 5,482 [reported] in the 16:00 row, 33,266 [reported] in the 17:00 "
            "row and 820 [reported] in the 18:00 row, with calls dropping off dramatically after "
            "6pm. The E3C interim report states, citing our report, that 39,568 [reported] calls "
            "were made to the 105 number between 16:00 and 18:00.",
            [
                src(
                    "ESO",
                    32,
                    ESO_T9,
                    "TOTAL TIME 16:00 265 473 632 1,008 1,030 2,074 5,482 17:00 1,140 2,643 2,699 "
                    "5,292 6,341 15,151 33,266 18:00 81 64 75 238 200 162 820 Table 9 - Calls "
                    "received by the 6 largest DNOs, during the period 4pm to 7pm on 9th August",
                ),
                src(
                    "ESO",
                    31,
                    ESO_64,
                    "with calls dropping off dramatically post 6pm.",
                ),
                src(
                    "E3C-I",
                    14,
                    "Industry and Public Communications",
                    "Between 16:00 and 18:00 on 9th August, the ESO Technical Report states that "
                    "39,568 calls were made to the 105 Single Emergency Number",
                ),
            ],
        ),
        block(
            "S09-ESOC-07",
            [
                "incident reporting procedure",
                "notification procedure",
                "escalation procedure",
            ],
            "ESO procedure says that after a loss of supply a clear communication to Ofgem and "
            "BEIS is essential and should be initiated as soon as possible, in line with Ofgem's "
            "'Energy Incident Reporting' requirement dated December 2017; resolving the incident "
            "remains the primary objective. In the first hour the scale of the secondary impact "
            "on consumers, such as the travel disruption, was not clear to the control room even "
            "after demand restoration had begun.",
            [
                src(
                    "APP",
                    88,
                    APP_M + ", answer 34",
                    "Current ESO procedure outlines that following an event of loss of supply, a "
                    "clear communication to Ofgem & BEIS is essential. The communication is "
                    "recommended to be initiated as soon as possible, and this procedure is in line "
                    "with the ‘Energy Incident Reporting’ requirement set by Ofgem dated "
                    "in December 2017. It is important in all cases that resolution of the "
                    "incident remains the primary objective.",
                ),
                src(
                    "APP",
                    88,
                    APP_M + ", answer 34",
                    "the scale of the secondary impact to the end consumers, e.g. the travel "
                    "disruption, was not clear to ENCC even after the demand restoration was "
                    "initiated.",
                ),
            ],
        ),
        block(
            "S09-ESOC-08",
            ["ENA engagement", "industry engagement", "DNO communications"],
            "We spoke to the ENA early on Saturday 10 August and had a call with the ENA and the "
            "DNOs first thing on Monday 12 August, when we also shared our lines to take; through "
            "the week of 12 August we set out our preliminary technical findings to the ENA and "
            "its members.",
            [
                src(
                    "APP",
                    90,
                    APP_M + ", answer 41",
                    "The ESO spoke to the ENA early on the morning of Saturday 10th August. We had "
                    "a call with them and the DNO’s first thing on the morning of Monday 12th "
                    "August. At this point, we also shared our lines to take with their comms "
                    "team. We engaged with the ENA and it’s relevant members directly through "
                    "week commencing 12th August to set out our preliminary technical findings",
                )
            ],
        ),
        block(
            "S09-ESOC-09",
            ["Hornsea notification", "generator notification", "restart coordination"],
            "Ofgem's report states that Hornsea 1 did not notify the ESO directly when the wind "
            "farm deloaded by 737 MW [reported], and that it then began starting up two of its "
            "modules temporarily without any coordination with the ESO while the ESO was "
            "responding to the generation losses it was aware of.",
            [
                src(
                    "OFG",
                    29,
                    OFG_H + ", 3.23",
                    "Hornsea 1 did not notify the ESO directly when the wind farm deloaded by "
                    "737MW. The wind farm then began its process of starting up two of its modules "
                    "(temporarily) without",
                ),
                src(
                    "OFG",
                    30,
                    OFG_H + ", 3.23",
                    "any coordination with the ESO whilst the ESO was attempting to respond to the "
                    "generation losses it was aware of.",
                ),
            ],
        ),
        block(
            "S09-ESOC-10",
            ["communication systems", "communication issues"],
            "We did not experience issues with our communication systems and are not aware of "
            "any third-party communication system problems; there were no communication issues "
            "with our customers as a result of the disruption.",
            [
                src(
                    "APP",
                    90,
                    APP_M + ", answer 39",
                    "The ESO did not experience any issues in our communication system and we are "
                    "not aware of any third party communication system problems",
                ),
                src(
                    "APP",
                    89,
                    APP_M + ", answer 38",
                    "There were no communication issues with our customers as a result of the "
                    "power disruption",
                ),
            ],
        ),
    ],
}

# --------------------------------------------------------------------------- hospital

HOSPITAL_CARD = {
    "persona_id": "hospital-estates-manager",
    "role": "Estates manager, Ipswich Hospital",
    "organisation": "East Suffolk and North Essex NHS Foundation Trust",
    "unknown_response": "Not known — the hospital's published statement and the reports I can "
    "speak to do not cover that.",
    "blocks": [
        block(
            "S09-HOSP-01",
            ["hospital power", "what happened at the hospital", "hospital supply"],
            "The ESO's report says Ipswich Hospital's internal protection operated coincident "
            "with the timeframe of the lightning strike, and that UKPN's time-stamped data show "
            "the hospital's load reducing by half in a period of 14 seconds [reported].",
            [
                src(
                    "ESO",
                    28,
                    ESO_53,
                    "Ipswich Hospital internal protection operated coincident with the timeframe of "
                    "the lightning strike. Time stamped data from UKPN shows that the hospital’s "
                    "load reduced by half in a period of 14 seconds.",
                )
            ],
        ),
        block(
            "S09-HOSP-02",
            ["LFDD", "demand disconnection", "protection zone"],
            "UKPN confirmed to the ESO that the hospital was not part of its LFDD protection zone "
            "and that LFDD did not affect the substations supplying the hospital.",
            [
                src(
                    "ESO",
                    28,
                    ESO_53,
                    "UKPN have confirmed that the hospital was not part of their LFDD protection "
                    "zone and that the LFDD did not affect the substations supplying the hospital.",
                )
            ],
        ),
        block(
            "S09-HOSP-03",
            ["standby generators", "back-up power", "circuit breaker"],
            "Our trust's public statement of 10 August 2019 [reported], summarised here rather "
            "than quoted, described a minor on-site power problem: every standby generator "
            "operated, but one breaker serving outpatient services failed to, briefly "
            "interrupting electricity to outpatient and x-ray areas; business-continuity plans "
            "were invoked, the problem was resolved quickly and other areas were unaffected. The "
            "statement gives no times.",
            [
                real_src(
                    "esneft_ipswich_hospital_statement",
                    "clock_basis",
                    "datePublished 2019-08-10T10:09:37+00:00",
                ),
                real_src(
                    "esneft_ipswich_hospital_statement", "event_visible", "No times."
                ),
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
        ),
        block(
            "S09-HOSP-04",
            ["other hospitals", "hospitals affected"],
            "The E3C final report says four hospitals were impacted, two disconnected by the LFDD "
            "scheme and two by their internal safety systems, all switching automatically to "
            "back-up supplies. The E3C interim report describes one hospital, not named, where "
            "incorrect protection settings on its own network switched the site to back-up "
            "generation and one of its 11 [reported] generators failed to operate.",
            [
                src(
                    "E3C",
                    19,
                    E3C_4,
                    "Four hospitals were impacted by the power outage; two were disconnected by the "
                    "LFDD scheme and a further two hospitals were disconnected by their internal "
                    "safety systems. All hospitals automatically switched to back-up power "
                    "supplies to ensure continued operation.",
                ),
                src(
                    "E3C-I",
                    12,
                    f"{E3CI_ES}, Health",
                    "Another hospital was affected by the fall in frequency/voltage excursion, "
                    "despite not being disconnected as part of LFDD. This was due to incorrect "
                    "protection settings on the hospital’s own network, which resulted in the "
                    "site switching over to back-up generation and one of its 11 generators failing "
                    "to operate.",
                ),
            ],
        ),
    ],
}


def cards() -> list[dict[str, Any]]:
    out = []
    for card in (ESOC_CARD, GTR_CARD, HOSPITAL_CARD, NR_CARD, UKPN_CARD):
        out.append({**card, "evidence_id": WITNESS_EVIDENCE_ID})
    return sorted(out, key=lambda c: c["persona_id"])
