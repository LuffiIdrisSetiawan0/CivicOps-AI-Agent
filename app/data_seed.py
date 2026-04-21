from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import Base, engine
from app.models import Budget, ComplaintLog, MonthlyKPI, PublicService, Region

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

TOPICS = [
    ("dokumen tertunda", -0.35, "medium"),
    ("data tidak sinkron", -0.55, "high"),
    ("aplikasi lambat", -0.25, "medium"),
    ("petugas responsif", 0.62, "low"),
    ("jadwal tidak jelas", -0.44, "medium"),
    ("status permohonan tidak berubah", -0.49, "high"),
]


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def seed_database(db: Session) -> None:
    create_schema()
    if db.scalar(select(Region.id).limit(1)):
        return

    regions = [Region(**item) for item in REGIONS]
    services = [PublicService(**item) for item in SERVICES]
    db.add_all(regions + services)
    db.flush()

    months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"]
    for month_index, month in enumerate(months, start=1):
        for region_index, region in enumerate(regions, start=1):
            for service_index, service in enumerate(services, start=1):
                demand = 80 + (region_index * 26) + (service_index * 19) + (month_index * 11)
                if service.category == "infrastruktur":
                    demand = int(demand * 0.55)
                backlog = (region_index + service_index + month_index) % 12
                completed = max(demand - backlog - (service_index % 2), 0)
                resolution = round(service.sla_days * (0.72 + 0.08 * region_index + 0.03 * month_index), 2)
                satisfaction = round(4.6 - (backlog * 0.08) - (resolution / max(service.sla_days, 1) * 0.18), 2)
                db.add(
                    MonthlyKPI(
                        region_id=region.id,
                        service_id=service.id,
                        month=month,
                        request_count=demand,
                        completed_count=completed,
                        avg_resolution_days=resolution,
                        satisfaction_score=max(satisfaction, 2.8),
                        backlog_count=backlog,
                    )
                )

    ticket_no = 1000
    for month_index, month in enumerate(months, start=1):
        for region_index, region in enumerate(regions, start=1):
            for service_index, service in enumerate(services, start=1):
                topic, sentiment, severity = TOPICS[(month_index + region_index + service_index) % len(TOPICS)]
                ticket_no += 1
                db.add(
                    ComplaintLog(
                        ticket_id=f"SD-{ticket_no}",
                        region_id=region.id,
                        service_id=service.id,
                        month=month,
                        channel=["WhatsApp", "Mobile", "Web", "Call Center"][
                            (region_index + service_index) % 4
                        ],
                        severity=severity,
                        topic=topic,
                        sentiment=sentiment,
                        message=(
                            f"Warga {region.name} melaporkan {topic} pada layanan "
                            f"{service.name}. Butuh tindak lanjut lintas dinas dan update status."
                        ),
                    )
                )

    for region_index, region in enumerate(regions, start=1):
        for service_index, service in enumerate(services, start=1):
            allocated = round(1.2 + region_index * 0.48 + service_index * 0.36, 2)
            spent_ratio = 0.55 + ((region_index + service_index) % 4) * 0.09
            db.add(
                Budget(
                    region_id=region.id,
                    service_id=service.id,
                    year=2025,
                    allocated_billion_idr=allocated,
                    spent_billion_idr=round(allocated * spent_ratio, 2),
                    vendor=["Nusantara Data", "Borneo Integrasi", "Kalteng Digital", "Sistem Prima"][
                        (region_index + service_index) % 4
                    ],
                    program_status=["on_track", "watch", "delayed"][
                        (region_index + service_index) % 3
                    ],
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
    seed_database(db)
    ensure_policy_docs()

