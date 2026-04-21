from dataclasses import dataclass


@dataclass
class RegionalRiskSignal:
    region: str
    flood_risk: str
    network_status: str
    operational_note: str


RISK_SIGNALS = {
    "palangka": RegionalRiskSignal(
        region="Kota Palangka Raya",
        flood_risk="medium",
        network_status="stable",
        operational_note="Mobile channel normal; monitor Dukcapil peak demand after public holidays.",
    ),
    "kapuas": RegionalRiskSignal(
        region="Kabupaten Kapuas",
        flood_risk="high",
        network_status="intermittent",
        operational_note="Prioritize offline queue sync for public service counters during flood alerts.",
    ),
    "kotawaringin": RegionalRiskSignal(
        region="Kabupaten Kotawaringin Barat",
        flood_risk="low",
        network_status="stable",
        operational_note="Good candidate for digital-only service pilot because channel stability is high.",
    ),
    "barito": RegionalRiskSignal(
        region="Kabupaten Barito Utara",
        flood_risk="medium",
        network_status="degraded",
        operational_note="Schedule batch sync outside working hours to reduce portal latency complaints.",
    ),
    "murung": RegionalRiskSignal(
        region="Kabupaten Murung Raya",
        flood_risk="medium",
        network_status="intermittent",
        operational_note="Escalate recurrent identity-data mismatch to the data engineering team.",
    ),
}


def get_regional_risk_signal(question: str) -> RegionalRiskSignal:
    q = question.lower()
    for key, signal in RISK_SIGNALS.items():
        if key in q:
            return signal
    return RegionalRiskSignal(
        region="Province-wide",
        flood_risk="mixed",
        network_status="varies by region",
        operational_note="Use SQL KPIs and complaint topics to choose the region that needs escalation first.",
    )

