from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.models import Budget, ComplaintLog, MonthlyKPI, PublicService, Region

SEED_VERSION = "2026-04-demo-v2"
SEED_MARKER_PATH = Path("data/.demo_seed_version")
MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"]
CHANNEL_ROTATION = ["WhatsApp", "Mobile", "Web", "Call Center", "Loket"]
VENDORS = ["Nusantara Data", "Borneo Integrasi", "Kalteng Digital", "Sistem Prima"]

REGIONS = [
    {
        "code": "KTG-PKY",
        "name": "Kota Palangka Raya",
        "province": "Kalimantan Tengah",
        "type": "kota",
        "population": 305907,
    },
    {
        "code": "KTG-KTW",
        "name": "Kabupaten Kotawaringin Barat",
        "province": "Kalimantan Tengah",
        "type": "kabupaten",
        "population": 285521,
    },
    {
        "code": "KTG-KAP",
        "name": "Kabupaten Kapuas",
        "province": "Kalimantan Tengah",
        "type": "kabupaten",
        "population": 423210,
    },
    {
        "code": "KTG-BTU",
        "name": "Kabupaten Barito Utara",
        "province": "Kalimantan Tengah",
        "type": "kabupaten",
        "population": 162310,
    },
    {
        "code": "KTG-MUR",
        "name": "Kabupaten Murung Raya",
        "province": "Kalimantan Tengah",
        "type": "kabupaten",
        "population": 122745,
    },
]

SERVICES = [
    {
        "service_code": "DUKCAPIL-KTP",
        "name": "KTP Elektronik",
        "category": "dukcapil",
        "channel": "web, loket, mobile",
        "sla_days": 3,
    },
    {
        "service_code": "DUKCAPIL-KK",
        "name": "Kartu Keluarga",
        "category": "dukcapil",
        "channel": "web, loket",
        "sla_days": 4,
    },
    {
        "service_code": "DINKES-RUJUKAN",
        "name": "Rujukan Kesehatan",
        "category": "kesehatan",
        "channel": "web, puskesmas",
        "sla_days": 2,
    },
    {
        "service_code": "PUPR-JALAN",
        "name": "Laporan Jalan Rusak",
        "category": "infrastruktur",
        "channel": "mobile, call center",
        "sla_days": 14,
    },
]

REGION_PROFILES = {
    "KTG-PKY": {
        "request_multiplier": 1.08,
        "backlog_bias": 1.0,
        "delivery_drag": 0.05,
        "satisfaction_bonus": 0.1,
        "complaint_bias": 0,
        "budget_multiplier": 1.1,
        "budget_bias": 0.06,
    },
    "KTG-KTW": {
        "request_multiplier": 0.98,
        "backlog_bias": 2.0,
        "delivery_drag": 0.1,
        "satisfaction_bonus": 0.02,
        "complaint_bias": 1,
        "budget_multiplier": 1.02,
        "budget_bias": -0.01,
    },
    "KTG-KAP": {
        "request_multiplier": 1.14,
        "backlog_bias": 3.0,
        "delivery_drag": 0.14,
        "satisfaction_bonus": -0.08,
        "complaint_bias": 2,
        "budget_multiplier": 1.12,
        "budget_bias": -0.05,
    },
    "KTG-BTU": {
        "request_multiplier": 0.9,
        "backlog_bias": 2.0,
        "delivery_drag": 0.08,
        "satisfaction_bonus": -0.02,
        "complaint_bias": 1,
        "budget_multiplier": 0.94,
        "budget_bias": -0.03,
    },
    "KTG-MUR": {
        "request_multiplier": 0.84,
        "backlog_bias": 4.0,
        "delivery_drag": 0.16,
        "satisfaction_bonus": -0.12,
        "complaint_bias": 2,
        "budget_multiplier": 0.88,
        "budget_bias": -0.07,
    },
}

SERVICE_PROFILES = {
    "DUKCAPIL-KTP": {
        "base_requests": 150,
        "backlog_bias": 1.5,
        "resolution_bias": 0.08,
        "satisfaction_bias": 0.04,
        "budget_base": 2.4,
        "budget_bias": 0.04,
        "topics": ["data tidak sinkron", "status permohonan tidak berubah", "antrean loket menumpuk"],
    },
    "DUKCAPIL-KK": {
        "base_requests": 132,
        "backlog_bias": 1.8,
        "resolution_bias": 0.05,
        "satisfaction_bias": 0.03,
        "budget_base": 2.2,
        "budget_bias": 0.01,
        "topics": ["dokumen tertunda", "jadwal pengambilan tidak jelas", "sinkronisasi terlambat"],
    },
    "DINKES-RUJUKAN": {
        "base_requests": 168,
        "backlog_bias": 2.3,
        "resolution_bias": 0.14,
        "satisfaction_bias": -0.03,
        "budget_base": 2.65,
        "budget_bias": -0.02,
        "topics": ["rujukan belum tervalidasi", "status permohonan tidak berubah", "aplikasi mobile gagal unggah"],
    },
    "PUPR-JALAN": {
        "base_requests": 98,
        "backlog_bias": 3.6,
        "resolution_bias": 0.18,
        "satisfaction_bias": -0.09,
        "budget_base": 3.4,
        "budget_bias": -0.06,
        "topics": ["jalan akses terdampak banjir", "drainase belum ditangani", "jadwal survei tidak jelas"],
    },
}

MONTH_PROFILES = {
    "2025-01": {"request_shift": -0.04, "backlog_shift": -1.0, "resolution_shift": -0.04, "complaint_shift": 0},
    "2025-02": {"request_shift": 0.0, "backlog_shift": 0.0, "resolution_shift": 0.0, "complaint_shift": 0},
    "2025-03": {"request_shift": 0.04, "backlog_shift": 1.0, "resolution_shift": 0.04, "complaint_shift": 1},
    "2025-04": {"request_shift": 0.07, "backlog_shift": 2.0, "resolution_shift": 0.08, "complaint_shift": 1},
    "2025-05": {"request_shift": 0.1, "backlog_shift": 3.0, "resolution_shift": 0.12, "complaint_shift": 2},
    "2025-06": {"request_shift": 0.08, "backlog_shift": 2.0, "resolution_shift": 0.1, "complaint_shift": 1},
}

BACKLOG_EVENTS = {
    ("2025-03", "KTG-PKY", "DUKCAPIL-KTP"): {
        "request_bonus": 18,
        "backlog_bonus": 3,
        "resolution_bonus": 0.12,
        "complaint_bonus": 1,
        "topic": "sinkronisasi terlambat",
    },
    ("2025-04", "KTG-KTW", "DINKES-RUJUKAN"): {
        "request_bonus": 22,
        "backlog_bonus": 4,
        "resolution_bonus": 0.18,
        "complaint_bonus": 1,
        "topic": "rujukan belum tervalidasi",
    },
    ("2025-05", "KTG-KAP", "PUPR-JALAN"): {
        "request_bonus": 28,
        "backlog_bonus": 6,
        "resolution_bonus": 0.24,
        "complaint_bonus": 2,
        "topic": "jalan akses terdampak banjir",
    },
    ("2025-06", "KTG-KAP", "PUPR-JALAN"): {
        "request_bonus": 38,
        "backlog_bonus": 10,
        "resolution_bonus": 0.34,
        "complaint_bonus": 3,
        "topic": "jalan akses terdampak banjir",
    },
    ("2025-06", "KTG-MUR", "PUPR-JALAN"): {
        "request_bonus": 16,
        "backlog_bonus": 5,
        "resolution_bonus": 0.22,
        "complaint_bonus": 2,
        "topic": "jaringan kantor kecamatan putus",
    },
    ("2025-06", "KTG-KTW", "DINKES-RUJUKAN"): {
        "request_bonus": 18,
        "backlog_bonus": 4,
        "resolution_bonus": 0.18,
        "complaint_bonus": 1,
        "topic": "rujukan belum tervalidasi",
    },
    ("2025-06", "KTG-PKY", "DUKCAPIL-KTP"): {
        "request_bonus": 14,
        "backlog_bonus": 3,
        "resolution_bonus": 0.12,
        "complaint_bonus": 1,
        "topic": "antrean loket menumpuk",
    },
}

TOPIC_LIBRARY = {
    "dokumen tertunda": {"severity": "medium", "sentiment": -0.35},
    "data tidak sinkron": {"severity": "high", "sentiment": -0.56},
    "status permohonan tidak berubah": {"severity": "high", "sentiment": -0.49},
    "antrean loket menumpuk": {"severity": "medium", "sentiment": -0.33},
    "jadwal pengambilan tidak jelas": {"severity": "medium", "sentiment": -0.41},
    "sinkronisasi terlambat": {"severity": "high", "sentiment": -0.46},
    "rujukan belum tervalidasi": {"severity": "high", "sentiment": -0.51},
    "aplikasi mobile gagal unggah": {"severity": "medium", "sentiment": -0.38},
    "jalan akses terdampak banjir": {"severity": "high", "sentiment": -0.52},
    "drainase belum ditangani": {"severity": "medium", "sentiment": -0.4},
    "jadwal survei tidak jelas": {"severity": "medium", "sentiment": -0.34},
    "jaringan kantor kecamatan putus": {"severity": "high", "sentiment": -0.53},
    "petugas responsif": {"severity": "low", "sentiment": 0.6},
    "update status cepat": {"severity": "low", "sentiment": 0.54},
}

BUDGET_OVERRIDES = {
    ("KTG-PKY", "DUKCAPIL-KTP"): 0.05,
    ("KTG-PKY", "DINKES-RUJUKAN"): -0.03,
    ("KTG-KTW", "DUKCAPIL-KK"): -0.07,
    ("KTG-KAP", "PUPR-JALAN"): -0.11,
    ("KTG-MUR", "PUPR-JALAN"): -0.07,
    ("KTG-MUR", "DINKES-RUJUKAN"): -0.05,
    ("KTG-BTU", "DUKCAPIL-KTP"): -0.03,
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def _should_refresh_seed() -> bool:
    if not SEED_MARKER_PATH.exists():
        return True
    return SEED_MARKER_PATH.read_text(encoding="utf-8").strip() != SEED_VERSION


def _write_seed_marker() -> None:
    SEED_MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_MARKER_PATH.write_text(SEED_VERSION, encoding="utf-8")


def _reset_demo_state(db: Session) -> None:
    db.close()
    Base.metadata.drop_all(bind=engine)
    create_schema()


def seed_database(db: Session) -> None:
    create_schema()
    if db.scalar(select(Region.id).limit(1)):
        return

    regions = [Region(**item) for item in REGIONS]
    services = [PublicService(**item) for item in SERVICES]
    db.add_all(regions + services)
    db.flush()

    latest_snapshots: dict[tuple[str, str], dict[str, float]] = {}
    for month in MONTHS:
        month_profile = MONTH_PROFILES[month]
        for region in regions:
            region_profile = REGION_PROFILES[region.code]
            for service in services:
                service_profile = SERVICE_PROFILES[service.service_code]
                event = BACKLOG_EVENTS.get((month, region.code, service.service_code), {})

                demand = int(
                    round(
                        service_profile["base_requests"]
                        * region_profile["request_multiplier"]
                        * (1 + month_profile["request_shift"])
                        + event.get("request_bonus", 0)
                    )
                )

                structural_backlog = (
                    service_profile["backlog_bias"]
                    + region_profile["backlog_bias"]
                    + month_profile["backlog_shift"]
                    + event.get("backlog_bonus", 0)
                    + max(0, demand - service_profile["base_requests"]) / 38
                )
                backlog = max(2, int(round(structural_backlog)))
                completed = max(demand - backlog, 0)

                resolution_multiplier = (
                    0.84
                    + service_profile["resolution_bias"]
                    + region_profile["delivery_drag"]
                    + month_profile["resolution_shift"]
                    + backlog / 24
                    + event.get("resolution_bonus", 0)
                )
                resolution = round(service.sla_days * resolution_multiplier, 2)
                days_over_sla = max(resolution - service.sla_days, 0)

                satisfaction = (
                    4.76
                    + region_profile["satisfaction_bonus"]
                    + service_profile["satisfaction_bias"]
                    - (backlog * 0.055)
                    - (days_over_sla * 0.12)
                )
                satisfaction = round(clamp(satisfaction, 2.95, 4.74), 2)

                db.add(
                    MonthlyKPI(
                        region_id=region.id,
                        service_id=service.id,
                        month=month,
                        request_count=demand,
                        completed_count=completed,
                        avg_resolution_days=resolution,
                        satisfaction_score=satisfaction,
                        backlog_count=backlog,
                    )
                )

                if month == MONTHS[-1]:
                    latest_snapshots[(region.code, service.service_code)] = {
                        "backlog": backlog,
                        "days_over_sla": days_over_sla,
                        "satisfaction": satisfaction,
                    }

    ticket_no = 1000
    for month_index, month in enumerate(MONTHS):
        month_profile = MONTH_PROFILES[month]
        for region_index, region in enumerate(regions):
            region_profile = REGION_PROFILES[region.code]
            for service_index, service in enumerate(services):
                service_profile = SERVICE_PROFILES[service.service_code]
                event = BACKLOG_EVENTS.get((month, region.code, service.service_code), {})

                demand = int(
                    round(
                        service_profile["base_requests"]
                        * region_profile["request_multiplier"]
                        * (1 + month_profile["request_shift"])
                        + event.get("request_bonus", 0)
                    )
                )
                backlog = max(
                    2,
                    int(
                        round(
                            service_profile["backlog_bias"]
                            + region_profile["backlog_bias"]
                            + month_profile["backlog_shift"]
                            + event.get("backlog_bonus", 0)
                            + max(0, demand - service_profile["base_requests"]) / 38
                        )
                    ),
                )

                primary_topic = event.get(
                    "topic",
                    service_profile["topics"][(month_index + region_index) % len(service_profile["topics"])],
                )
                alternate_topic = service_profile["topics"][
                    (month_index + region_index + service_index + 1) % len(service_profile["topics"])
                ]
                positive_topic = "petugas responsif" if (region_index + service_index + month_index) % 2 == 0 else "update status cepat"

                complaint_count = int(
                    clamp(
                        1
                        + backlog // 4
                        + region_profile["complaint_bias"]
                        + month_profile["complaint_shift"]
                        + event.get("complaint_bonus", 0),
                        1,
                        6,
                    )
                )

                for complaint_index in range(complaint_count):
                    topic = primary_topic
                    if complaint_index == complaint_count - 1 and complaint_count >= 3:
                        topic = alternate_topic
                    if backlog <= 4 and complaint_index == complaint_count - 1:
                        topic = positive_topic

                    topic_meta = TOPIC_LIBRARY[topic]
                    sentiment = clamp(
                        topic_meta["sentiment"] - (backlog * 0.01) + (complaint_index * 0.02),
                        -0.82,
                        0.72,
                    )
                    severity = topic_meta["severity"]
                    if backlog >= 15 and complaint_index == 0:
                        severity = "high"
                    if topic in {"petugas responsif", "update status cepat"}:
                        severity = "low"

                    ticket_no += 1
                    db.add(
                        ComplaintLog(
                            ticket_id=f"SD-{ticket_no}",
                            region_id=region.id,
                            service_id=service.id,
                            month=month,
                            channel=CHANNEL_ROTATION[
                                (region_index + service_index + complaint_index + month_index) % len(CHANNEL_ROTATION)
                            ],
                            severity=severity,
                            topic=topic,
                            sentiment=round(sentiment, 2),
                            message=(
                                f"Warga {region.name} melaporkan {topic} pada layanan {service.name}. "
                                "Perlu update status, kepastian kanal layanan, dan koordinasi lintas instansi."
                            ),
                        )
                    )

    for region_index, region in enumerate(regions):
        region_profile = REGION_PROFILES[region.code]
        for service_index, service in enumerate(services):
            service_profile = SERVICE_PROFILES[service.service_code]
            latest = latest_snapshots[(region.code, service.service_code)]
            allocated = round(
                service_profile["budget_base"] * region_profile["budget_multiplier"] + (service_index * 0.12),
                2,
            )
            spend_ratio = (
                0.72
                + region_profile["budget_bias"]
                + service_profile["budget_bias"]
                + BUDGET_OVERRIDES.get((region.code, service.service_code), 0.0)
                - (latest["backlog"] * 0.012)
                - (latest["days_over_sla"] * 0.028)
            )
            spend_ratio = round(clamp(spend_ratio, 0.43, 0.89), 3)

            if spend_ratio < 0.56 or latest["backlog"] >= 15:
                program_status = "delayed"
            elif spend_ratio < 0.7 or latest["backlog"] >= 10:
                program_status = "watch"
            else:
                program_status = "on_track"

            db.add(
                Budget(
                    region_id=region.id,
                    service_id=service.id,
                    year=2025,
                    allocated_billion_idr=allocated,
                    spent_billion_idr=round(allocated * spend_ratio, 2),
                    vendor=VENDORS[(region_index + service_index) % len(VENDORS)],
                    program_status=program_status,
                )
            )

    db.commit()


def ensure_policy_docs() -> None:
    docs_dir = Path("data/policies")
    docs_dir.mkdir(parents=True, exist_ok=True)
    documents = {
        "satudata_governance.md": """# Satu Data Governance Policy

SatuData Ops consolidates demographic, public service, complaint, and budget data for regional decision making. Every analytical response must separate observed data from recommendations.

Priority services for the 2025 pilot are KTP Elektronik, Kartu Keluarga, Rujukan Kesehatan, and Laporan Jalan Rusak. Cross-agency escalation is required when a service misses SLA for two consecutive months or when high-severity complaints increase.

Data freshness rules: KPI tables are refreshed monthly, complaint logs are refreshed daily, and budget realization is refreshed at the end of each month. A dashboard answer must cite the table, document, or tool used.
""",
        "complaint_sla_policy.md": """# Complaint SLA and Escalation Policy

High-severity complaints require first response within one working day. Medium-severity complaints require first response within three working days. Low-severity complaints may be batched weekly.

Escalate to the regional operations lead when backlog exceeds ten tickets for the same service in one month. Escalate to the data team when repeated complaints mention data mismatch, duplicate identity records, missing document status, or stale synchronization.

Recommended mitigation: publish status updates, identify the affected service channel, and compare complaint topics with monthly KPI trends before assigning a vendor or agency action.
""",
        "budget_monitoring_playbook.md": """# Budget Monitoring Playbook

Budget monitoring compares allocated budget, realized spending, service backlog, and satisfaction score. Programs marked delayed need a short recovery plan with owner, target date, and dependency.

Healthy programs typically show spending realization above 60 percent by mid-year, stable backlog below ten open items per region-service pair, and satisfaction score above 3.8. A low-spend program with rising backlog is a delivery risk.

For executive reporting, summarize the top three risks, affected regions, service categories, and suggested next action. Do not invent procurement data that is not present in the budget table.
""",
        "data_quality_policy.md": """# Data Quality Policy

Analytical agents must reject destructive SQL and avoid exposing personally identifiable information. The demo dataset is synthetic and contains no real citizen records.

When a question cannot be answered from available SQL tables, documents, complaint logs, or mock APIs, the assistant should say what is missing and suggest the closest available metric.

Quality checks should verify that answers include evidence, do not overstate causality, and distinguish metric values from policy recommendations.
""",
    }
    for filename, content in documents.items():
        path = docs_dir / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def bootstrap(db: Session) -> None:
    if _should_refresh_seed():
        _reset_demo_state(db)
    seed_database(db)
    ensure_policy_docs()
    _write_seed_marker()
