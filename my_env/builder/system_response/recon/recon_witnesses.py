"""S09 witness fact cards (reconstructed; roles, not people).

Each block answers one topic in the first person of the role and restates only what its
provenance passages say (verify_recon.py checks every quote on its page and that every number
in the answer occurs in the block's quotes). Blocks never carry another party's findings as the
witness's own knowledge; where the published record holds two versions of the witness's own
organisation's account, the block says so (documented disagreement). Anything else gets the
card's fixed ``unknown_response``.
"""

from __future__ import annotations

from typing import Any

from recon_common import WITNESS_EVIDENCE_ID, src
from recon_doc_specs import (
    APP_D,
    APP_H,
    APP_M,
    APP_M_DATE,
    E3C_F,
    E3C_I,
    ESO_42EG,
    ESO_42LB,
    ESO_43,
    ESO_61,
    ESO_T1,
    ESO_T6,
    OFG_24,
    OFG_DNO,
)

APP_C = "Appendix C – NGET Technical Report"
APP_E = "Appendix E – RWE Preliminary Findings (dated 30 August 2019)"
ESO_42H = "4.2 Generation Performance – Hornsea"
OFG_H = "Ofgem section 3, Hornsea 1"
OFG_L = "Ofgem section 3, Little Barford"


def block(
    response_id: str, topics: list[str], text: str, provenance: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "response_id": response_id,
        "topics": topics,
        "response_text": text,
        "provenance": provenance,
    }


ESO_CARD = {
    "persona_id": "eso-control-engineer",
    "role": "Control engineer, ESO Electricity National Control Centre (ENCC)",
    "organisation": "National Grid ESO",
    "unknown_response": "Not known — that is not something I know or hold records on.",
    "blocks": [
        block(
            "S09-ESO-01",
            ["securing", "largest infeed loss", "pre-event conditions", "secured loss"],
            "Before the event we were securing for a loss of power infeed of 1000 MW [reported], "
            "with frequency at 50.0 Hz [reported] at 16:52:26 [reported]. The largest single "
            "infeed loss on the day was 1,000 MW [reported], the loss of a single interconnector.",
            [
                src(
                    "ESO",
                    12,
                    ESO_T1,
                    "16:52:26 Frequency at 50.0Hz, ESO securing for a loss of power infeed of 1000MW",
                ),
                src(
                    "APP",
                    56,
                    APP_H,
                    "The largest single Infeed Loss on the day was 1,000 MW, the loss of a single "
                    "interconnector.",
                ),
            ],
        ),
        block(
            "S09-ESO-02",
            [
                "automatic response",
                "frequency response",
                "trigger settings",
                "static response",
            ],
            "Frequency response initiated at 16:52:34 [reported]. Response is provided "
            "automatically once the control room has armed it. The automatic services included "
            "static low frequency Firm Frequency Response designed to trigger at 49.7 Hz "
            "[reported], the EWIC and Moyle interconnectors initiated at 49.6 Hz [reported], and a "
            "service contracted with gas turbines initiated at 49.6 Hz [reported] and 49.5 Hz "
            "[reported] depending on the agreement with each provider.",
            [
                src("ESO", 12, ESO_T1, "16:52:34 Frequency response initiates."),
                src(
                    "APP",
                    82,
                    APP_M + ", answer 17",
                    "Therefore, both types of response are automatically provided once armed by the "
                    "Control Room.",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "static Low Frequency initiated Firm Frequency Responses (FFR) which is designed "
                    "to be triggered at 49.7Hz, EWIC and Moyle interconnectors being initiated at "
                    "49.6Hz and a service contracted with Gas Turbines which was initiated at 49.6Hz "
                    "and 49.5Hz respectively, depending on the agreement between NGESO and the "
                    "providers.",
                ),
            ],
        ),
        block(
            "S09-ESO-03",
            [
                "manual actions",
                "reserve",
                "STOR",
                "balancing actions",
                "control room instructions",
            ],
            "At 16:54:20 [reported] the control room initiated instructions to generation to "
            "restore the system frequency and response levels. In total 1,240 MW [reported] of "
            "actions were taken, using Short Term Operating Reserve, Rapid Start, Balancing "
            "Mechanism actions and Fast Reserve. They included rapid start of one Dinorwig unit, "
            "instructions to another Dinorwig unit and two Ffestiniog units from a synchronising "
            "position to generating, an additional distribution-connected diesel generator and "
            "400 MW [reported] of short term operating reserve. Coryton South and Carrington were "
            "instructed to cover the enduring loss of generation.",
            [
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "16:54:20 Control room initiate instructions to generation to restore the system "
                    "frequency and response levels to stabilise the system",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "1,240 MW of actions were taken by the ESO to restore frequency to operational "
                    "limits, using the following services:",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "Short Term Operating Reserve Rapid Start Balancing Mechanism Actions Fast "
                    "Reserve (from BM and non-BM providers).",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "rapid start service being instructed to one Dinorwig unit, instructions to "
                    "another Dinorwig Unit and two Ffestiniog units from a synchronising position to "
                    "generating and an additional distribution connected diesel generator.",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "400MW of short term operational reserve was also instructed.",
                ),
                src(
                    "APP",
                    83,
                    APP_M + ", answer 20",
                    "To cover the enduring loss of generation at Little Barford and Hornsea One, "
                    "Coryton South and Carrington were both instructed by NGESO.",
                ),
            ],
        ),
        block(
            "S09-ESO-04",
            ["demand disconnection reports", "first report", "DNO calls", "load lost"],
            "The first report of demand disconnection from a DNO reached the control room at 16:56 "
            "[reported]. Reports kept arriving with numbers of customers and load lost, and DNOs "
            "asked when restoration could begin. Some DNOs called the NGET control room instead; "
            "it referred them to us, with no impact on restoration.",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[16:56] First report of demand disconnection from DNO was received by the ESO "
                    "control room.",
                ),
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Reports continued to arrive with number of customers and load lost. Enquires "
                    "were received about when demand restoration could begin.",
                ),
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Whilst some DNOs incorrectly called the NGET control room, NGET control room "
                    "correctly referred DNO’s to the ESO, with no impact on the restoration process.",
                ),
            ],
        ),
        block(
            "S09-ESO-05",
            ["restoration instructions", "restore demand", "permission", "phraseology"],
            "We instructed the DNOs to restore demand progressively from 16:58 to 17:16 [reported]. "
            "The DNOs did ask our specific permission to restore. Our verbal instructions did not "
            "follow the agreed phraseology, but they were clear and understood. All DNOs had "
            "confirmed that restoration was complete at 17:37 [reported].",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[16:58 to 17:16] Demand restoration instruction to DNOs was initiated by the "
                    "ESO control room. The demand was instructed to restore in a progressive manner.",
                ),
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Indications are that DNOs did ask specific permission from the ESO control room "
                    "to restore demand. While verbal instructions to DNOs to restore demand did not "
                    "follow agreed phraseology, they were clear and understood.",
                ),
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "17:37 All DNO’s have confirmed that demand restoration has been completed",
                ),
            ],
        ),
        block(
            "S09-ESO-06",
            ["NGET control room", "TNCC", "calls with NGET"],
            "Our technical report records that we told the NGET control room at 17:32 [reported] "
            "that DNOs had started restoration. Our earlier answers to the E3C, based on the data "
            "we had on 28 August 2019, gave 17:22 [reported] for that message.",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "[17:32] ESO control room informed NGET control room that DNOs had started "
                    "restoration.",
                ),
                src(
                    "APP",
                    87,
                    APP_M + ", answer 33",
                    "At 17:22hrs, ENCC informed TNCC that all DNOs had started demand restoration.",
                ),
                APP_M_DATE,
            ],
        ),
        block(
            "S09-ESO-07",
            ["frequency recovery", "nominal frequency", "system stability"],
            "Our timeline records frequency returning to 50 Hz [reported] at 16:57:15 [reported], "
            "following over 1,000 MW [reported] of response and a further 1240 MW [reported] of "
            "control room actions. The power system was confirmed to be stable within 15 minutes "
            "[reported].",
            [
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "16:57:15 Frequency returns to 50Hz following over 1,000MW of response and a "
                    "further 1240MW of control room actions to restore frequency and stabilise the "
                    "situation",
                ),
                src(
                    "APP",
                    88,
                    APP_M + ", answer 34",
                    "The power system was confirmed to be stable within 15 minutes",
                ),
            ],
        ),
        block(
            "S09-ESO-08",
            [
                "embedded generation visibility",
                "distributed generation data",
                "IEMS estimate",
            ],
            "Most distribution-connected generation gives us no indication of its proposed output "
            "and no actual output data. Our estimate of approximately 500 MW [estimated] of "
            "embedded generation lost came from the change in metered flows between the "
            "transmission and distribution networks in our IEMS system, corrected for the frequency "
            "characteristics of demand and for frequency response services in the distribution "
            "network.",
            [
                src(
                    "APP",
                    76,
                    APP_M + ", answer 10",
                    "The majority of distribution connected generation provides no indication of "
                    "proposed output, and no actual output data to the ESO.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "We estimate that approximately 500 MW of embedded generation was lost in the "
                    "incident.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "The volume has been estimated by analysing the changes in flows between the "
                    "Transmission Networks and the Distribution Networks using metered data gathered "
                    "from our IEMS system.",
                ),
                src(
                    "APP",
                    75,
                    APP_M + ", answer 7",
                    "We have corrected this change for the frequency characteristics of demand and "
                    "allowed for frequency response services in the distribution network.",
                ),
            ],
        ),
        block(
            "S09-ESO-09",
            [
                "embedded generation protection",
                "protection settings",
                "islanding protection",
                "distributed generation trips",
            ],
            "We secure the system to within a RoCoF limit of 0.125 Hz/s [reported] for the largest "
            "credible loss. Approximately 2 GW [reported] of small generators are on relays that "
            "disconnect above 0.125 Hz/s [reported], and approximately 8.5 GW [reported] on relays "
            "that disconnect for a vector shift angle greater than 6 degrees [reported]. We also "
            "consider the impact of vector shift protection on embedded generation where "
            "appropriate.",
            [
                src(
                    "APP",
                    78,
                    APP_M + ", answer 11",
                    "We also secure the system to within a ROCOF limit of 0.125 Hz/s for the largest "
                    "credible loss.",
                ),
                src(
                    "APP",
                    78,
                    APP_M + ", answer 11",
                    "We also consider the impact of vector shift protection on embedded generation "
                    "where appropriate to do so.",
                ),
                src(
                    "APP",
                    58,
                    APP_H,
                    "Approximately 2 GW of small generators are connected to the distribution "
                    "networks via relays which disconnect the generators if the RoCoF is greater "
                    "than 0.125Hz/s.",
                ),
                src(
                    "APP",
                    59,
                    APP_H,
                    "Approximately 8.5 GW of small generators are connected to the distribution "
                    "networks via relays which disconnect the generators if the Vector Shift angle is "
                    "greater than 6 degrees.",
                ),
            ],
        ),
        block(
            "S09-ESO-10",
            ["inertia", "inertia estimate"],
            "We do not currently measure system inertia directly; we estimate it with a model, "
            "derived from the forecast demand level and embedded solar and wind.",
            [
                src(
                    "APP",
                    90,
                    APP_M + ", answer 42",
                    "The ESO does not currently measure system inertia directly but instead "
                    "estimates it using a model. The inertia estimate is derived from the forecasted "
                    "demand level, embedded solar and wind",
                )
            ],
        ),
        block(
            "S09-ESO-11",
            ["security standard", "securing distributed generation losses", "SQSS"],
            "Where a large infeed loss is more likely to come with significant vector shift "
            "protection losses, we manage for that event too, even though this is strictly not "
            "within the requirements of the security standards. We secure for the potential "
            "cumulative effect of vector shift and infeed loss where we consider it appropriate.",
            [
                src(
                    "APP",
                    78,
                    APP_M + ", answer 11",
                    "where there is a higher probability that a large infeed loss may also be "
                    "associated with significant vector shift protection losses then we manage this "
                    "for this event even though this is strictly not within the requirements of the "
                    "security standards.",
                ),
                src(
                    "APP",
                    57,
                    APP_H,
                    "Based on this assessment the ESO will secure for the potential cumulative effect "
                    "of vector shift (e.g., following a transmission fault) and infeed loss where it "
                    "considers it appropriate to do so.",
                ),
            ],
        ),
    ],
}

NGET_CARD = {
    "persona_id": "nget-protection-engineer",
    "role": "Protection engineer, transmission owner",
    "organisation": "National Grid Electricity Transmission (NGET)",
    "unknown_response": "Not known — NGET's records that I can speak to do not cover that.",
    "blocks": [
        block(
            "S09-NGET-01",
            ["fault", "fault type", "faulted phase", "fault location"],
            "At 16:52 [reported] lightning struck the Eaton Socon – Wymondley Main circuit "
            "4.5 km [reported] from Wymondley substation. The middle conductor (blue phase) "
            "faulted to the earthed transmission tower.",
            [
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "At 16:52 on the 9th August 2019 the electricity transmission system saw a "
                    "lightning strike on the Eaton Socon – Wymondley Main Circuit, 4.5km from "
                    "Wymondley substation. This caused the middle conductor (blue phase) to fault to "
                    "the earthed transmission tower",
                )
            ],
        ),
        block(
            "S09-NGET-02",
            ["fault current", "fault level", "voltage during the fault"],
            "The fault currents were 21 kA [reported] at Wymondley Main and 7 kA [reported] at "
            "Eaton Socon, and the blue phase voltage was reduced by approximately 50% [reported].",
            [
                src(
                    "APP",
                    20,
                    APP_C + ", 1.1",
                    "the blue conductor phase voltage was reduced by approximately 50% and currents "
                    "of 21kA (21 thousand amps) were recorded at Wymondley Main and 7kA at Eaton "
                    "Socon.",
                )
            ],
        ),
        block(
            "S09-NGET-03",
            [
                "protection operation",
                "clearance time",
                "circuit breakers",
                "Grid Code clearance",
            ],
            "The main protection at Wymondley Main operated in 70 ms [reported] and at Eaton Socon "
            "in 74 ms [reported], clearing the fault within the 80 ms [reported] the Grid Code "
            "requires at 400 kV (Connection Condition CC.6.2.3.1.1). Both circuit breakers "
            "operated as designed.",
            [
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "The main protection at Wymondley Main operated in 70ms and the main protection "
                    "at Eaton Socon operated in 74ms, therefore clearing the fault within the 80ms "
                    "required in the Grid Code.",
                ),
                src(
                    "APP",
                    21,
                    APP_C + ", 1.1",
                    "One requirement of the Grid Code (Connection Condition CC.6.2.3.1.1) is that "
                    "our 400kV primary main circuit breaker protection operates within 80ms to clear "
                    "electrical faults.",
                ),
                src(
                    "APP",
                    27,
                    APP_C + ", 3.2.3",
                    "The operation of both circuit breakers at Wymondley Main and Eaton Socon was as "
                    "expected, with both operating as designed",
                ),
            ],
        ),
        block(
            "S09-NGET-04",
            ["return to service", "reclose", "circuit restoration"],
            "The Delayed Auto-Reclose system was available and in service on the circuit and "
            "returned it to service within 20 seconds [reported]. That restored the network to the "
            "configuration it had before the event and needed no further operational intervention "
            "or immediate site attendance.",
            [
                src(
                    "APP",
                    21,
                    APP_C + ", 1.2",
                    "the DAR system was available and in service on the Eaton Socon - Wymondley Main "
                    "circuit and it successfully returned the circuit to service within 20 seconds",
                ),
                src(
                    "APP",
                    21,
                    APP_C + ", 1.2",
                    "This restored the network to the same configuration seen prior to the event. "
                    "The DAR system in this case again operated exactly as expected and required no "
                    "further operational intervention or immediate site attendance.",
                ),
            ],
        ),
        block(
            "S09-NGET-05",
            ["lightning data", "MeteoGroup", "cause of the fault"],
            "MeteoGroup's recorded lightning activity near the circuit aligns with our protection "
            "data placing the fault 4.5 km [reported] from Wymondley Main, just outside Letchworth "
            "Garden City. One of the strikes is timed at the same time as the fault, so we can be "
            "confident that a lightning strike was the cause of the fault.",
            [
                src(
                    "APP",
                    25,
                    APP_C + ", 3.1.1",
                    "The activity aligns with the protection data indicating the fault was 4.5km "
                    "from Wymondley Main, just outside Letchworth Garden City.",
                ),
                src(
                    "APP",
                    25,
                    APP_C + ", 3.1.1",
                    "One of these strikes is timed at the same time as the fault. As such we can be "
                    "confident that a lightning strike was the cause of the fault.",
                ),
            ],
        ),
        block(
            "S09-NGET-06",
            ["power quality", "voltage measurements", "Ryhall", "Necton"],
            "A voltage depression of circa 50% [reported] at the fault location lasted 100 ms "
            "[reported]; further from the fault, dips of 20% [reported] lasting 80 ms [reported] "
            "were seen. Our monitor at Ryhall recorded a 44% [reported] depression on the blue "
            "phase and the one at Necton 21% [reported]. The monitor near Killingholme was "
            "unavailable because the Killingholme – Keadby circuit was out of service for planned "
            "maintenance.",
            [
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "A voltage depression of circa 50% was seen at the fault location on the blue "
                    "phase which lasted for 100ms in the vicinity of the fault. Further from the "
                    "fault, voltage dips of 20% were observed with 80ms duration.",
                ),
                src(
                    "APP",
                    28,
                    APP_C + ", 3.3.1",
                    "Figure 3.3.1 below shows the 44% voltage depression on the Blue phase of the "
                    "circuit experienced at Ryhall.",
                ),
                src(
                    "APP",
                    30,
                    APP_C + ", 3.3.2",
                    "Killingholme – Keadby circuit which was out of service for planned maintenance "
                    "on 9th August.",
                ),
                src(
                    "APP",
                    30,
                    APP_C + ", 3.3.2",
                    "Figure 3.3.2 below shows voltage depression of 21% on the Blue phase of the "
                    "circuit experienced at Necton 400kV.",
                ),
            ],
        ),
        block(
            "S09-NGET-07",
            ["site inspection", "defects", "overhead line inspection"],
            "Engineers attended Wymondley Main and Eaton Socon substations to collect data, "
            "including protection operating data; all assets were operating as normal and no "
            "defects were identified. Our overhead line engineers inspected the line on the "
            "morning of Saturday 10 August and observed no defects.",
            [
                src(
                    "APP",
                    22,
                    APP_C + ", 2.2",
                    "Engineers went to both sites and confirmed all assets were operating as normal "
                    "at each substation and no defects on our assets were identified.",
                ),
                src(
                    "APP",
                    22,
                    APP_C + ", 2.2",
                    "Our overhead line engineers undertook a visual inspection of the Eaton Socon – "
                    "Wymondley Main overhead line, on the morning Saturday 10th August. No identified "
                    "defects were observed.",
                ),
            ],
        ),
        block(
            "S09-NGET-08",
            ["TNCC", "LFDD alarms", "transmission control room calls", "public calls"],
            "As is standard practice, the ESO's control room led the response. Our TNCC received "
            "electronic alarm indications that the LFDD scheme had operated and confirmed this by "
            "phone with the ENCC and DNOs over a period of 8 minutes [reported] after the first "
            "indications. Members of the public who rang our safety number were redirected to the "
            "105 number.",
            [
                src(
                    "APP",
                    22,
                    APP_C + ", 2.1",
                    "As is standard practice the ENCC led the response to the system fault on 9th "
                    "August.",
                ),
                src(
                    "APP",
                    22,
                    APP_C + ", 2.1",
                    "This was confirmed by phone with the ENCC and DNOs over a period of 8mins "
                    "following receipt of the initial alarm indications.",
                ),
                src(
                    "APP",
                    22,
                    APP_C + ", 2.1",
                    "we redirected each call to the Electricity Networks Association (ENA) "
                    "information “105” number.",
                ),
            ],
        ),
        block(
            "S09-NGET-09",
            ["network performance", "steady state voltages", "standards"],
            "Our key finding is that the transmission network operated as designed and in line "
            "with standards. Pre-fault and post-fault steady state voltages were within the limits "
            "required by industry standards, and harmonic and negative phase sequence currents "
            "were within limits.",
            [
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "our key finding is that the electricity transmission network operated as "
                    "designed and in line with standards",
                ),
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "All pre-fault and post-fault steady state voltages were within limits required "
                    "within industry standards",
                ),
                src(
                    "APP",
                    17,
                    APP_C + ", Executive Summary",
                    "Harmonic and Negative Phase Sequence currents were within limits set out within "
                    "the relevant standards and codes.",
                ),
            ],
        ),
    ],
}

ORSTED_CARD = {
    "persona_id": "orsted-hornsea-operations-engineer",
    "role": "Operations engineer, Hornsea One offshore wind farm",
    "organisation": "Ørsted",
    "unknown_response": "Not known — that is not covered by the Hornsea One records I can speak to.",
    "blocks": [
        block(
            "S09-ORS-01",
            ["pre-event output", "declared capability", "plant configuration"],
            "Hornsea One was under construction offshore: two modules were fully installed and the "
            "third partially, giving a declared export capability of 800 MW [reported]. Before the "
            "event Hornsea 1B was operating at 400 MW [reported], its maximum, and the site was "
            "generating 799 MW [reported].",
            [
                src(
                    "OFG",
                    29,
                    OFG_H + ", 3.19",
                    "two of its modules were fully installed and the third was partially installed; "
                    "it therefore had declared a total 800MW power export capability.",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "Prior to the event, Hornsea 1B is operating at 400MW (maximum capacity for that "
                    "unit)",
                ),
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events",
                    "Hornsea One de-loaded from 799MW to 62MW",
                ),
            ],
        ),
        block(
            "S09-ORS-02",
            [
                "sequence",
                "what happened",
                "voltage and reactive power",
                "onshore response",
            ],
            "The 400 kV voltage was steady at about 400 kV [reported] until 16:52:33:490 "
            "[reported]. Our reactive compensation control first injected reactive power to "
            "support the voltage, then a significant oscillation followed: we absorbed more than "
            "300 MVAr [reported], depressing the voltage to about 394 kV [reported], and active "
            "power fell from 799 MW [reported] to 400 MW [reported] before returning to 799 MW. "
            "At 16:52:33:700 [reported] reactive power passed about 0 MVAr and the site then "
            "absorbed about 560 MVAr [reported].",
            [
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events",
                    "Figure 3 (above) shows NETS voltage in the 400kV substation initially steady at "
                    "~400kV (16:52:33:000 to 16:52:33:490).",
                ),
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events",
                    "the Hornsea One reactive compensation control systems initially inject reactive "
                    "power (leading MVArs) to boost NETS voltage, before a significant oscillation "
                    "occurs, absorbing reactive power (>300MVAr which depresses NETS and Hornsea One "
                    "systems",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "voltage to ~394kV) and then injecting MVArs again. As a consequence, Hornsea "
                    "reduces active power from 799MW to 400MW before returning to 799MW.",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "so the reactive power output reaches ~0MVAr as it rapidly switches from "
                    "injection and absorption again (16:52:33:700). Hornsea now absorbs ~560MVAr.",
                ),
            ],
        ),
        block(
            "S09-ORS-03",
            [
                "turbine protection",
                "offshore turbines",
                "wind turbines",
                "offshore response",
            ],
            "In the 34 kV [reported] collection system the voltage fell rapidly to 20 kV "
            "[reported]. Trying to hold full active power at that voltage overloaded each turbine "
            "on Hornsea 1B and 1C, and their overcurrent protection de-loaded them, as the industry "
            "standard protection does to avoid permanent damage. The de-load ran from 16:52:33:728 "
            "to 16:52:33:835 [reported], 107 ms [reported]; Hornsea 1A stayed in operation at "
            "62 MW [reported].",
            [
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "In the wind farm 34kV collection cable system the result of this is that the "
                    "voltage rapidly reduces to 20kV (target voltage 34kV) and all WTGs on Hornsea 1B "
                    "and Hornsea 1C reduce to 0MW as a result of overcurrent protection in the "
                    "generators (16:52:33:728 to 16:52:33:835).",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "Hornsea 1B system voltage falls to ~20kV while attempting to maintain full "
                    "active power which leads to an overcurrent of each WTG connected to Hornsea 1B "
                    "and Hornsea 1C at the time.",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "the WTGs de-load as part of the industry standard protection system to avoid "
                    "permanent damage to the generators.",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "completed the de-load at 15.52.33.835, 107ms later. Following the de-load of "
                    "Hornsea 1B and Hornsea 1C, Hornsea 1A remained in operation at 62MW active "
                    "power output.",
                ),
            ],
        ),
        block(
            "S09-ORS-04",
            ["cause", "investigation findings", "explanation"],
            "Our report concludes that the de-load was caused by an unexpected wind farm control "
            "system response, due to an insufficiently damped electrical resonance in the "
            "sub-synchronous frequency range, which was triggered by the initial event.",
            [
                src(
                    "APP",
                    43,
                    APP_D + ", Conclusion",
                    "The de-load was caused by an unexpected wind farm control system response, due "
                    "to an insufficiently damped electrical resonance in the sub-synchronous "
                    "frequency range, which was triggered by the initial event.",
                )
            ],
        ),
        block(
            "S09-ORS-05",
            ["DRC", "dynamic reactive compensator"],
            "At first we understood the Dynamic Reactive Compensator to be responsible for the "
            "rapid de-load. We have since concluded that the DRC worked as designed and was not the "
            "cause.",
            [
                src(
                    "ESO",
                    20,
                    ESO_42H,
                    "Initially, Orsted understood that the Dynamic Reactive Compensator (DRC) was "
                    "responsible for the rapid de-load of Hornsea-1. Orsted have since concluded that "
                    "the DRC worked as designed and was not the cause of the de-load.",
                )
            ],
        ),
        block(
            "S09-ORS-06",
            ["network strength", "outage configuration", "SGT", "OTSUA"],
            "Our internal network had one SGT and one OTSUA circuit on outage. That configuration "
            "was a contributory factor because it created a weak internal network environment; we "
            "have since reviewed and reconfigured it. Our systems identified a weak grid before "
            "detecting the voltage disturbance.",
            [
                src(
                    "ESO",
                    20,
                    ESO_42H,
                    "The configuration of the Hornsea network, with one SGT and one offshore "
                    "transmission system user asset (OTSUA Circuit) on outage, was a contributory "
                    "factor as it created a weak internal network environment. Subsequently Orsted "
                    "have reviewed and reconfigured their network.",
                ),
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events",
                    "Hornsea One’s systems identified a weak grid and then detected an unusual "
                    "voltage disturbance",
                ),
            ],
        ),
        block(
            "S09-ORS-07",
            [
                "earlier in the day",
                "before the fault",
                "plant behaviour before the event",
            ],
            "After the event we identified electrical oscillations before it that caused no "
            "de-loading: 10 minutes [reported] before, the reactive power response to a 2% "
            "[reported] voltage step change was a damped oscillatory response from the overall "
            "voltage control systems.",
            [
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "Subsequent to the event in question and as part of this investigation, "
                    "electrical oscillations at Hornsea One were identified occurring prior to the "
                    "event (and without causing any de-loading). 10 minutes before",
                ),
                src(
                    "APP",
                    42,
                    APP_D + ", Description of events",
                    "Figure 5 – Showing the reactive power output from Hornsea 10 minutes prior to "
                    "the event in response to a 2% voltage step change",
                ),
                src(
                    "APP",
                    42,
                    APP_D + ", Description of events",
                    "In this case the response from Hornsea shows a damped oscillatory response from "
                    "the overall voltage control systems.",
                ),
            ],
        ),
        block(
            "S09-ORS-08",
            ["mitigation", "changes after the event", "remedial action"],
            "A control system software update performed on 10 August 2019 [reported], previously "
            "agreed with the manufacturer, mitigates the observed behaviour. Ofgem records, from "
            "information we gave it, that the update had been planned for 13 August [reported].",
            [
                src(
                    "APP",
                    42,
                    APP_D + ", Description of events",
                    "The software update performed on the 10 August 2019 was previously agreed with "
                    "the manufacturer",
                ),
                src(
                    "APP",
                    42,
                    APP_D + ", Description of events",
                    "This software update mitigates the observed behaviour of Hornsea One",
                ),
                src(
                    "OFG",
                    29,
                    OFG_H + ", 3.22",
                    "which Ørsted informed us it had planned to carry out on 13 August but "
                    "implemented on 10 August immediately following the event.",
                ),
            ],
        ),
        block(
            "S09-ORS-09",
            [
                "prior modelling",
                "testing",
                "manufacturer modelling",
                "compliance studies",
            ],
            "Each stage had been modelled and physically tested in line with grid code "
            "requirements, and the potential for oscillations had been considered. Ofgem reports, "
            "from information we provided, that modelling with our equipment manufacturer before "
            "9 August suggested voltage control performance issues at the full planned 1,200 MW "
            "[reported], that these were not discussed with the ESO, and that prior simulations had "
            "not foreseen such issues at 799 MW [reported].",
            [
                src(
                    "APP",
                    42,
                    APP_D + ", Description of events",
                    "Prior to the event, each stage of Hornsea One had been successfully modelled and "
                    "physically tested in line with all grid code requirements. While the potential "
                    "for oscillations had been considered",
                ),
                src(
                    "OFG",
                    29,
                    OFG_H + ", 3.22",
                    "modelling it carried out with its equipment manufacturer prior to 9 August "
                    "suggested that there were performance issues with the voltage control system "
                    "with Hornsea 1 operating at its full planned 1,200MW capacity. These issues were "
                    "not discussed with the ESO.",
                ),
                src(
                    "OFG",
                    29,
                    OFG_H + ", 3.22",
                    "The issue on 9 August occurred when the wind farm reached generation of 799MW. "
                    "Prior simulations and discussions had not foreseen such issues would occur at "
                    "this capacity",
                ),
            ],
        ),
        block(
            "S09-ORS-10",
            ["lightning time", "timestamps", "event times"],
            "We do not know the exact time of the lightning strike. Our report times the "
            "short circuit at 16:52:33:490 [reported] and the de-load at 16:52:33:728 to "
            "16:52:33:835 [reported]; one passage writes the de-load as 15.52.33.728 to "
            "15.52.33.835 [reported].",
            [
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events, footnote 1",
                    "At the time of publishing Ørsted is unaware of the exact time of the lightning "
                    "strike",
                ),
                src(
                    "APP",
                    40,
                    APP_D + ", Description of events",
                    "The lightning strike results in a phase to Earth short circuit at exactly "
                    "16:52:33:490.",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "(16:52:33:728 to 16:52:33:835)",
                ),
                src(
                    "APP",
                    41,
                    APP_D + ", Description of events",
                    "began de-loading turbines at 15.52.33.728 and completed the de-load at "
                    "15.52.33.835",
                ),
            ],
        ),
    ],
}

RWE_CARD = {
    "persona_id": "rwe-lb-shift-charge-engineer",
    "role": "Shift charge engineer, Little Barford power station",
    "organisation": "RWE Generation",
    "unknown_response": "Not known — the station records and findings I can speak to do not cover that.",
    "blocks": [
        block(
            "S09-RWE-01",
            ["station configuration", "units", "plant before the event"],
            "Little Barford is a 740 MW [reported] combined cycle gas turbine station connected at "
            "the Eaton Socon 400 kV [reported] substation. It has two gas turbines and one steam "
            "turbine, and all three were operating on 9 August.",
            [
                src(
                    "OFG",
                    30,
                    OFG_L + ", 3.25",
                    "Little Barford is a 740MW combined cycle gas turbine power station, located in "
                    "Bedfordshire.",
                ),
                src(
                    "OFG",
                    30,
                    OFG_L + ", 3.25",
                    "It is connected to the national transmission system at the Eaton Socon 400kV "
                    "substation. The station has two gas turbines and one steam turbine which were "
                    "all operating on 9 August.",
                ),
            ],
        ),
        block(
            "S09-RWE-02",
            ["sequence of events", "SOE", "datum", "timing"],
            "Our Sequence of Events system timed everything from a datum T = 16:52:34 +/- "
            "0.5 seconds [reported]: UPS -B- alarm at T, UPS -A- alarm at +3 ms [reported], steam "
            "turbine control system shutdown initiated at +253 ms [reported], ST breaker open "
            "feedback at +1.185 s [reported], GT1A auto shutdown command at +56.583 s [reported] "
            "and breaker open at +57.620 s [reported], GT1B manual shutdown command at +83.897 s "
            "[reported] and breaker open at +84.613 s [reported]. We have confidence in the "
            "chronology, but more work is needed to align T with the datum the ESO uses.",
            [
                src("APP", 45, APP_E, "Time T = 16:52:34 +/- 0.5seconds"),
                src(
                    "APP",
                    45,
                    APP_E,
                    "110v AC UPS –A- general fault alarm +003 mSec • Initiation of ST Control System "
                    "shutdown +253 mSec",
                ),
                src("APP", 45, APP_E, "ST Generator Breaker Open feedback +1.185 Sec"),
                src(
                    "APP",
                    45,
                    APP_E,
                    "GT1A Auto shutdown command +56.583 Sec • GT1A Breaker Open feedback +57.620 Sec "
                    "• GT1B Manual shutdown command +83.897 Sec • GT1B Breaker Open feedback "
                    "+84.613 Sec",
                ),
                src(
                    "APP",
                    45,
                    APP_E,
                    "RWE have confidence in the chronology of the events, further investigation work "
                    "is required to determine an accurate “T” datum relative to datum used within "
                    "NGESO report.",
                ),
            ],
        ),
        block(
            "S09-RWE-03",
            ["steam turbine trip", "ST1C", "steam turbine"],
            "The steam turbine, generating 244 MW [reported], tripped due to a discrepancy in the "
            "speed signals after the point of the transmission system fault clearance. A "
            "comprehensive investigation of hardware, software, fault handling and diagnostic "
            "coverage for the conditions the steam turbine saw is ongoing.",
            [
                src(
                    "ESO",
                    12,
                    ESO_T1,
                    "Little Barford Steam Turbine trips 244MW instantaneously. Source: RWE",
                ),
                src(
                    "APP",
                    46,
                    APP_E,
                    "Our investigations have confirmed that the Steam Turbine tripped due to a "
                    "discrepancy in the speed signals after the point of the Transmission System "
                    "fault clearance.",
                ),
                src(
                    "APP",
                    46,
                    APP_E,
                    "A comprehensive investigation of hardware, software, fault handling and "
                    "diagnostic coverage for the conditions, that the ST was subjected to during this "
                    "rare system disturbance, is ongoing.",
                ),
            ],
        ),
        block(
            "S09-RWE-04",
            ["GT1A trip", "GT1A", "first gas turbine"],
            "When the steam turbine tripped the gas turbines went into bypass mode, which is the "
            "normal response to allow sustained operation. For reasons presently unknown a "
            "high-pressure excursion occurred on GT1A, resulting in an automated trip of "
            "210 MW [reported]. Given the prevailing conditions all systems functioned as expected.",
            [
                src(
                    "APP",
                    46,
                    APP_E,
                    "Upon initiation of the Steam Turbine Trip the Gas Turbines went into bypass mode "
                    "of operation, which is the normal response to allow sustained operation.",
                ),
                src(
                    "APP",
                    46,
                    APP_E,
                    "For reasons presently unknown a high-pressure excursion occurred on GT1A "
                    "resulting in an automated trip. Given the prevailing conditions all systems "
                    "functioned as expected.",
                ),
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "Little Barford GT1A generator protection settings tripped and 210MW "
                    "instantaneously disconnected.",
                ),
            ],
        ),
        block(
            "S09-RWE-05",
            ["GT1B", "GT1B trip", "second gas turbine"],
            "GT1B was manually tripped shortly afterwards as a result of excessive steam pressure; "
            "the operating staff tripped it in response to the high steam pressures, around 30 "
            "seconds [reported] after GT1A, while it was generating 187 MW [reported].",
            [
                src(
                    "APP",
                    46,
                    APP_E,
                    "GT1B was manually tripped shortly after as a result of excessive steam pressure.",
                ),
                src(
                    "ESO",
                    20,
                    ESO_42LB,
                    "The second gas turbine (GT1B) was manually tripped by the RWE operational staff "
                    "in response to high steam pressures around 30 seconds later.",
                ),
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "Little Barford GT1B tripped with 187MW generation lost instantaneously.",
                ),
            ],
        ),
        block(
            "S09-RWE-06",
            ["UPS", "uninterrupted power supply", "station supplies"],
            "All UPS units at site functioned correctly to keep supplies to plant equipment, and "
            "the OEMs confirmed this, so we do not now believe the UPS were related to the trip. "
            "Our hypothesis is that the UPS changed over to battery back-up as a consequence of the "
            "system disturbance; the exact characteristic of the supply that caused the switch is "
            "still to be determined.",
            [
                src(
                    "APP",
                    45,
                    APP_E,
                    "The investigation to date has found that all UPS’ at Site have functioned "
                    "correctly to enable continuity of supply to plant equipment. Relevant OEM’s have "
                    "been engaged and confirmed the units have functioned as expected. Therefore, we "
                    "do not now believe the UPS’ were related to the subsequent trip.",
                ),
                src(
                    "APP",
                    45,
                    APP_E,
                    "RWE’s hypothesis is that the UPS’ have initiated a changeover to battery back-up "
                    "supplies as a consequence of the system disturbance. The exact characteristic of "
                    "the power supply to the UPS causing it to switch to battery operation is still "
                    "to be determined and subject to further investigation.",
                ),
            ],
        ),
        block(
            "S09-RWE-07",
            ["underlying cause", "cause", "investigation findings"],
            "The root cause of the pressure excursions has not been determined. A physical "
            "inspection of the bypass system is planned during the September 2019 outage to help "
            "determine it.",
            [
                src(
                    "APP",
                    46,
                    APP_E,
                    "A physical inspection of the bypass system is now planned during the "
                    "forthcoming outage in September 2019 to help determine the root cause of the "
                    "pressure excursions.",
                )
            ],
        ),
        block(
            "S09-RWE-08",
            ["improvements", "fixes applied", "review after the outage"],
            "The E3C records that the initial cause of the discrepancy between speed readings is "
            "still unknown due to data limitations. Since the outage we reviewed the sequence and "
            "identified areas for improvement: measurement system tolerances and associated "
            "sensitivities, balancing steam flows between the two boilers that feed the steam "
            "turbine, and verifying the pressure capability overhead of the system. We confirmed "
            "to the E3C that these fixes have all been applied.",
            [
                src(
                    "E3C",
                    11,
                    E3C_F + ", section 1",
                    "The initial cause behind the discrepancy between speed readings is still unknown "
                    "due to data limitations",
                ),
                src(
                    "E3C",
                    11,
                    E3C_F + ", section 1",
                    "Identifying measurement system tolerances and adjusting associated sensitivities "
                    "to increase resilience and maintain safety;",
                ),
                src(
                    "E3C",
                    11,
                    E3C_F + ", section 1",
                    "Balancing steam flows between the two boilers that feed the steam turbine; and",
                ),
                src(
                    "E3C",
                    11,
                    E3C_F + ", section 1",
                    "Verifying the pressure capability overhead of the system and allowing use of "
                    "this margin to achieve greater resilience.",
                ),
                src(
                    "E3C",
                    11,
                    E3C_F + ", section 1",
                    "RWE have confirmed to the E3C that these fixes have all been applied.",
                ),
            ],
        ),
        block(
            "S09-RWE-09",
            ["total loss", "station output lost"],
            "In total the station lost 641 MW [reported].",
            [
                src(
                    "ESO",
                    20,
                    ESO_42LB,
                    "In total this meant a total loss at Little Barford of 641MW.",
                )
            ],
        ),
    ],
}

DNO_CARD = {
    "persona_id": "dno-control-engineer",
    "role": "Control engineer, distribution network operator (collective account of the DNO returns)",
    "organisation": "Distribution Network Operators",
    "unknown_response": "Not known — that is not held in the DNO returns I can speak to.",
    "blocks": [
        block(
            "S09-DNO-01",
            ["LFDD operation", "demand disconnected", "LFDD relays"],
            "The ESO timeline row attributed to the DNOs reads: at 16:53:49.398 [reported] "
            "frequency breached the 48.8 Hz [reported] trigger level, resulting in LFDD, and "
            "931 MW [reported] of demand was automatically disconnected. The DNOs indicated that "
            "this was 931 MW (3.2%) [reported] of demand.",
            [
                src(
                    "ESO",
                    13,
                    ESO_T1,
                    "16:53:49.398 Frequency breaches 48.8Hz trigger level resulting in LFDD. 931MW "
                    "of demand is automatically disconnected. DNOs",
                ),
                src(
                    "ESO",
                    21,
                    ESO_43,
                    "The DNO’s have indicated that 931MW (3.2%) of demand was automatically "
                    "disconnected by the operation of the LFDD scheme.",
                ),
            ],
        ),
        block(
            "S09-DNO-02",
            ["customers affected", "returns", "13 August data"],
            "Our returns as of 13 August 2019 at 12:00 [reported] total 931 MW [reported] and "
            "1,152,878 [reported] customers, with the last area's final restoration at 17:37 "
            "[reported].",
            [
                src(
                    "ESO",
                    26,
                    "5.1 Distribution Demand",
                    "The information is based on DNO reported data as of 13 August 2019 at 12:00.",
                ),
                src("ESO", 26, ESO_T6, "Totals 931 1,152,878 17:37"),
            ],
        ),
        block(
            "S09-DNO-03",
            ["relay performance", "LFDD relay settings", "relay behaviour"],
            "After the event, two DNOs reported that a number of stage 1 LFDD schemes did not "
            "trigger and so did not disconnect demand. The possible reasons given were that the "
            "frequency did not stay at 48.8 Hz [reported] long enough to trigger all schemes, or "
            "the +/-0.01 Hz [reported] tolerance setting, which meant that when frequency fell to "
            "48.792 Hz [reported] not all schemes triggered.",
            [
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "Post event, two DNOs reported that a number of LFDD stage 1 schemes did not "
                    "trigger, and therefore did not disconnect demand.",
                ),
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "the system frequency did not stay at 48.8Hz long enough to trigger the "
                    "operation of all LFDD schemes",
                ),
                src(
                    "E3C-I",
                    11,
                    E3C_I,
                    "the +/-0.01Hz tolerance setting on the LFDD schemes which meant that when the "
                    "system frequency fell to 48.792Hz, not all schemes were triggered.",
                ),
            ],
        ),
        block(
            "S09-DNO-04",
            ["Scotland", "SP Distribution", "Scottish networks"],
            "SP Distribution disconnected 22 MW [reported] of demand in Scotland when frequency "
            "fell to 48.8 Hz [reported], although the Grid Code does not require DNOs there to "
            "disconnect until 48.5 Hz [reported]. It was due to an incorrect setting on its LFDD "
            "equipment, which has since been corrected.",
            [
                src(
                    "E3C",
                    8,
                    E3C_F + ", footnote 4",
                    "SP Distribution erroneously disconnected 22MW of demand in Scotland when the "
                    "system frequency fell to 48.8Hz. The Grid Code does not require Distribution "
                    "Network Operators to disconnect demand until the frequency reaches 48.5Hz. The "
                    "demand disconnection occurred due to an incorrect setting on SP Distribution’s "
                    "LFDD equipment and has since been corrected.",
                )
            ],
        ),
        block(
            "S09-DNO-05",
            ["restoration permission", "instruction to restore", "calling NGET"],
            "According to the ESO, DNOs asked the ESO control room for specific permission before "
            "restoring demand, and some DNOs first called the NGET control room, which referred "
            "them to the ESO.",
            [
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Indications are that DNOs did ask specific permission from the ESO control room "
                    "to restore demand.",
                ),
                src(
                    "ESO",
                    29,
                    ESO_61,
                    "Whilst some DNOs incorrectly called the NGET control room, NGET control room "
                    "correctly referred DNO’s to the ESO",
                ),
            ],
        ),
        block(
            "S09-DNO-06",
            ["reconnection", "reconnection timing", "reconnection process"],
            "Ofgem reports that Eastern Power Networks and South Eastern Power Networks, both owned "
            "by UK Power Networks, reconnected sites without being told to do so by the ESO and "
            "acknowledge that they do not appear to have technically met the Grid Code "
            "requirements; Ofgem attributes this to the configuration of their operational systems.",
            [
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.43",
                    "Eastern Power Networks plc and South Eastern Power Networks plc (both owned by "
                    "UK Power Networks) reconnected sites without being told to do so by the ESO, "
                    "and acknowledge that they do not appear to have technically met the "
                    "requirements of the Grid Code",
                ),
                src(
                    "OFG",
                    35,
                    OFG_DNO + ", 3.43",
                    "These instances were caused by the configuration of the DNOs’ operational "
                    "systems.",
                ),
            ],
        ),
        block(
            "S09-DNO-07",
            ["embedded generation return", "generation lost", "protection type"],
            "All DNOs responded to the ESO's request and together indicated 462 MW [reported] of "
            "embedded generation lost during the event. Some of us had trouble obtaining the data "
            "because of the way it is collected or stored, and without confirmation from the "
            "generators we could not tell whether a given generator tripped on RoCoF or on vector "
            "shift.",
            [
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "All DNOs have responded to this request and indicated a combined total of 462MW "
                    "of embedded generation was lost during the event.",
                ),
                src(
                    "ESO",
                    21,
                    ESO_42EG,
                    "In providing their analysis some DNOs noted challenges in obtaining the data "
                    "due to the way it is collected or stored and without confirmation from "
                    "generators, DNOs were unable to determine whether a specific generator tripped "
                    "due to RoCoF or Vector Shift.",
                ),
            ],
        ),
        block(
            "S09-DNO-08",
            ["generation monitoring", "generation data", "telemetry"],
            "Most DNOs record generation volumes on their networks only half-hourly, which obscures "
            "short events like this one, and DNOs do not monitor distributed generator output in "
            "real time.",
            [
                src(
                    "OFG",
                    36,
                    OFG_DNO + ", 3.45",
                    "Most of the DNOs only record information on generation volumes on their "
                    "networks on a half-hourly basis, obscuring shorter-term events",
                ),
                src(
                    "OFG",
                    18,
                    OFG_24 + ", footnote 19",
                    "as they also do not monitor output from distributed generators in real-time.",
                ),
            ],
        ),
        block(
            "S09-DNO-09",
            ["percentage disconnected", "share of demand", "proportion of demand"],
            "To the E3C the DNOs indicated that 4.0% [reported] of demand was actually "
            "disconnected, equating to over 1 million [reported] customers.",
            [
                src(
                    "E3C",
                    16,
                    E3C_F + ", section 3",
                    "the DNOs have indicated that 4.0% of demand was actually disconnected equating "
                    "to over 1 million customers",
                )
            ],
        ),
    ],
}

CARDS = [ESO_CARD, NGET_CARD, ORSTED_CARD, RWE_CARD, DNO_CARD]


def cards() -> list[dict[str, Any]]:
    out = []
    for card in CARDS:
        out.append({**card, "evidence_id": WITNESS_EVIDENCE_ID})
    return out
