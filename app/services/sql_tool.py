import re
from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db import engine

BLOCKED_SQL = {
    "alter",
    "attach",
    "create",
    "delete",
    "detach",
    "drop",
    "insert",
    "pragma",
    "replace",
    "truncate",
    "update",
    "vacuum",
}

KNOWN_REGIONS = {
    "palangka raya": "Kota Palangka Raya",
    "palangka": "Kota Palangka Raya",
    "kotawaringin barat": "Kabupaten Kotawaringin Barat",
    "kotawaringin": "Kabupaten Kotawaringin Barat",
    "kapuas": "Kabupaten Kapuas",
    "barito utara": "Kabupaten Barito Utara",
    "barito": "Kabupaten Barito Utara",
    "murung raya": "Kabupaten Murung Raya",
    "murung": "Kabupaten Murung Raya",
}

KNOWN_SERVICES = {
    "ktp elektronik": "KTP Elektronik",
    "ktp": "KTP Elektronik",
    "kartu keluarga": "Kartu Keluarga",
    "rujukan kesehatan": "Rujukan Kesehatan",
    "rujukan": "Rujukan Kesehatan",
    "laporan jalan rusak": "Laporan Jalan Rusak",
    "jalan rusak": "Laporan Jalan Rusak",
}

SUGGESTED_QUESTIONS = [
    "Region dan layanan mana yang memiliki backlog tertinggi?",
    "Apa kebijakan eskalasi untuk complaint high severity?",
    "Gabungkan backlog dan aturan eskalasi SLA untuk rekomendasi operasi.",
    "Apa risiko operasional di Kabupaten Kapuas jika jaringan intermittent?",
]


@dataclass
class SQLResult:
    query: str
    columns: list[str]
    rows: list[dict]


def schema_summary(db_engine: Engine = engine) -> dict[str, list[str]]:
    inspector = inspect(db_engine)
    return {
        table: [column["name"] for column in inspector.get_columns(table)]
        for table in inspector.get_table_names()
    }


def validate_sql(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        raise ValueError("Query is empty.")
    if ";" in normalized.rstrip(";"):
        raise ValueError("Only a single read-only statement is allowed.")
    normalized = normalized.rstrip(";").strip()
    first_token = normalized.split(None, 1)[0].lower()
    if first_token not in {"select", "with"}:
        raise ValueError("Only SELECT statements are allowed.")
    tokens = set(re.findall(r"[a-zA-Z_]+", normalized.lower()))
    blocked = sorted(tokens.intersection(BLOCKED_SQL))
    if blocked:
        raise ValueError(f"Blocked SQL keyword(s): {', '.join(blocked)}")
    return normalized


def execute_safe_sql(query: str, db_engine: Engine = engine) -> SQLResult:
    settings = get_settings()
    safe_query = validate_sql(query)
    limited_query = safe_query
    if " limit " not in f" {safe_query.lower()} ":
        limited_query = f"{safe_query} LIMIT {settings.max_sql_rows}"

    try:
        with db_engine.connect() as connection:
            result = connection.execute(text(limited_query))
            rows = [dict(row._mapping) for row in result.fetchall()]
            columns = list(result.keys())
    except SQLAlchemyError as exc:
        raise ValueError(f"SQL execution failed: {exc}") from exc

    return SQLResult(query=limited_query, columns=columns, rows=rows)


def dataset_preview(db_engine: Engine = engine) -> dict:
    previews: dict[str, dict] = {}
    with db_engine.connect() as connection:
        for table, columns in schema_summary(db_engine).items():
            count = connection.execute(text(f"SELECT COUNT(*) AS count FROM {table}")).scalar_one()
            rows = [
                dict(row._mapping)
                for row in connection.execute(text(f"SELECT * FROM {table} LIMIT 5")).fetchall()
            ]
            previews[table] = {"columns": columns, "row_count": count, "sample_rows": rows}
    return previews


def dashboard_summary(db_engine: Engine = engine) -> dict:
    with db_engine.connect() as connection:
        latest_month = connection.execute(text("SELECT MAX(month) FROM monthly_kpis")).scalar_one()
        trend_rows = [
            dict(row._mapping)
            for row in connection.execute(
                text(
                    """
                    SELECT month,
                           SUM(request_count) AS total_requests,
                           SUM(backlog_count) AS total_backlog,
                           ROUND(AVG(satisfaction_score), 2) AS avg_satisfaction
                    FROM monthly_kpis
                    GROUP BY month
                    ORDER BY month
                    """
                )
            ).fetchall()
        ]

        latest_snapshot = dict(
            connection.execute(
                text(
                    """
                    SELECT SUM(request_count) AS total_requests,
                           SUM(backlog_count) AS total_backlog,
                           ROUND(AVG(satisfaction_score), 2) AS avg_satisfaction
                    FROM monthly_kpis
                    WHERE month = :month
                    """
                ),
                {"month": latest_month},
            ).mappings().one()
        )

        over_sla_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM monthly_kpis k
                JOIN public_services s ON s.id = k.service_id
                WHERE k.month = :month
                  AND k.avg_resolution_days > s.sla_days
                """
            ),
            {"month": latest_month},
        ).scalar_one()

        high_severity_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM complaint_logs
                WHERE month = :month
                  AND severity = 'high'
                """
            ),
            {"month": latest_month},
        ).scalar_one()

        delayed_count = connection.execute(
            text("SELECT COUNT(*) FROM budgets WHERE program_status = 'delayed'")
        ).scalar_one()

        hotspots = [
            dict(row._mapping)
            for row in connection.execute(
                text(
                    """
                    SELECT r.name AS region,
                           s.name AS service,
                           k.backlog_count,
                           ROUND(k.avg_resolution_days, 2) AS avg_resolution_days,
                           s.sla_days,
                           ROUND(k.satisfaction_score, 2) AS satisfaction_score,
                           SUM(CASE WHEN c.severity = 'high' THEN 1 ELSE 0 END) AS high_severity_count
                    FROM monthly_kpis k
                    JOIN regions r ON r.id = k.region_id
                    JOIN public_services s ON s.id = k.service_id
                    LEFT JOIN complaint_logs c
                      ON c.region_id = k.region_id
                     AND c.service_id = k.service_id
                     AND c.month = k.month
                    WHERE k.month = :month
                    GROUP BY r.name, s.name, k.backlog_count, k.avg_resolution_days, s.sla_days, k.satisfaction_score
                    ORDER BY k.backlog_count DESC, high_severity_count DESC, k.avg_resolution_days DESC
                    LIMIT 4
                    """
                ),
                {"month": latest_month},
            ).fetchall()
        ]

        budget_watchlist = [
            dict(row._mapping)
            for row in connection.execute(
                text(
                    """
                    SELECT r.name AS region,
                           s.name AS service,
                           ROUND((b.spent_billion_idr / b.allocated_billion_idr) * 100, 1) AS spend_pct,
                           b.program_status
                    FROM budgets b
                    JOIN regions r ON r.id = b.region_id
                    JOIN public_services s ON s.id = b.service_id
                    ORDER BY CASE b.program_status
                               WHEN 'delayed' THEN 0
                               WHEN 'watch' THEN 1
                               ELSE 2
                             END,
                             spend_pct ASC
                    LIMIT 4
                    """
                )
            ).fetchall()
        ]

    first_month = trend_rows[0]
    last_month = trend_rows[-1]
    request_delta = _percentage_delta(
        first_month["total_requests"],
        last_month["total_requests"],
    )
    backlog_delta = _percentage_delta(
        first_month["total_backlog"],
        last_month["total_backlog"],
    )
    satisfaction_delta = round(last_month["avg_satisfaction"] - first_month["avg_satisfaction"], 2)

    stats = [
        {
            "label": "Request bulan terakhir",
            "value": _compact_number(latest_snapshot["total_requests"]),
            "context": f"{request_delta:+.0f}% vs Jan 2025",
            "tone": "steady" if request_delta >= 0 else "warning",
        },
        {
            "label": "Backlog operasional",
            "value": str(int(latest_snapshot["total_backlog"])),
            "context": f"{backlog_delta:+.0f}% vs Jan 2025",
            "tone": "warning" if latest_snapshot["total_backlog"] >= 150 else "steady",
        },
        {
            "label": "Kepuasan rata-rata",
            "value": f"{latest_snapshot['avg_satisfaction']:.2f}",
            "context": f"{satisfaction_delta:+.2f} poin vs Jan 2025",
            "tone": "steady" if satisfaction_delta >= -0.05 else "watch",
        },
        {
            "label": "At-risk signals",
            "value": str(int(delayed_count + over_sla_count)),
            "context": f"{delayed_count} delayed, {over_sla_count} over SLA",
            "tone": "warning",
        },
    ]

    return {
        "snapshot_month": latest_month,
        "stats": stats,
        "trend": trend_rows,
        "hotspots": hotspots,
        "budget_watchlist": budget_watchlist,
        "high_severity_count": high_severity_count,
        "suggested_questions": SUGGESTED_QUESTIONS,
    }


def analytical_sql_for_question(question: str) -> str | None:
    q = question.lower()
    scoped_clause = _scope_clause(question)

    if any(term in q for term in ["backlog", "tertunda"]) and any(
        term in q for term in ["kepuasan", "satisfaction", "skor"]
    ):
        return f"""
        SELECT r.name AS region, s.name AS service, k.month, k.backlog_count,
               k.satisfaction_score, k.avg_resolution_days
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        {scoped_clause}
        ORDER BY k.month DESC, k.backlog_count DESC
        LIMIT 6
        """

    if any(term in q for term in ["backlog", "tertunda", "open ticket"]):
        return f"""
        SELECT r.name AS region, s.name AS service, k.month, k.backlog_count,
               k.request_count, k.completed_count, k.satisfaction_score
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        {scoped_clause}
        ORDER BY k.backlog_count DESC, k.month DESC
        LIMIT 10
        """
    if any(term in q for term in ["satisfaction", "kepuasan", "skor"]):
        return f"""
        SELECT r.name AS region, s.name AS service,
               ROUND(AVG(k.satisfaction_score), 2) AS avg_satisfaction,
               ROUND(AVG(k.avg_resolution_days), 2) AS avg_resolution_days
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        {scoped_clause}
        GROUP BY r.name, s.name
        ORDER BY avg_satisfaction ASC
        LIMIT 10
        """
    if any(term in q for term in ["budget", "anggaran", "realisasi", "spending"]):
        return f"""
        SELECT r.name AS region, s.category, s.name AS service,
               b.allocated_billion_idr, b.spent_billion_idr,
               ROUND((b.spent_billion_idr / b.allocated_billion_idr) * 100, 1) AS spend_pct,
               b.program_status
        FROM budgets b
        JOIN regions r ON r.id = b.region_id
        JOIN public_services s ON s.id = b.service_id
        {scoped_clause}
        ORDER BY spend_pct ASC, b.program_status DESC
        LIMIT 10
        """
    if any(term in q for term in ["complaint", "keluhan", "sentiment", "sentimen", "topik"]):
        return f"""
        SELECT r.name AS region, s.name AS service, c.topic, c.severity,
               COUNT(*) AS complaint_count, ROUND(AVG(c.sentiment), 2) AS avg_sentiment
        FROM complaint_logs c
        JOIN regions r ON r.id = c.region_id
        JOIN public_services s ON s.id = c.service_id
        {_scope_clause(question, region_alias="r", service_alias="s", clause_keyword="WHERE")}
        GROUP BY r.name, s.name, c.topic, c.severity
        ORDER BY complaint_count DESC, avg_sentiment ASC
        LIMIT 10
        """
    if any(term in q for term in ["sla", "resolution", "penyelesaian", "terlambat"]):
        return f"""
        SELECT r.name AS region, s.name AS service, s.sla_days,
               ROUND(AVG(k.avg_resolution_days), 2) AS avg_resolution_days,
               ROUND(AVG(k.avg_resolution_days - s.sla_days), 2) AS days_over_sla
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        {scoped_clause}
        GROUP BY r.name, s.name, s.sla_days
        HAVING avg_resolution_days > s.sla_days
        ORDER BY days_over_sla DESC
        LIMIT 10
        """
    if any(term in q for term in ["layanan", "service", "permintaan", "request"]):
        return f"""
        SELECT s.name AS service, s.category,
               SUM(k.request_count) AS total_requests,
               SUM(k.completed_count) AS total_completed,
               SUM(k.backlog_count) AS total_backlog
        FROM monthly_kpis k
        JOIN public_services s ON s.id = k.service_id
        {_scope_clause(question, region_alias="", service_alias="s", clause_keyword="WHERE")}
        GROUP BY s.name, s.category
        ORDER BY total_requests DESC
        LIMIT 10
        """
    return None


def _scope_clause(
    question: str,
    region_alias: str = "r",
    service_alias: str = "s",
    clause_keyword: str = "WHERE",
) -> str:
    q = f" {question.lower()} "
    filters: list[str] = []

    if region_alias:
        for term, name in KNOWN_REGIONS.items():
            if term in q:
                filters.append(f"{region_alias}.name = '{name}'")
                break

    if service_alias:
        for term, name in KNOWN_SERVICES.items():
            if term in q:
                filters.append(f"{service_alias}.name = '{name}'")
                break

    if not filters:
        return ""
    return f"{clause_keyword} " + " AND ".join(filters)


def _compact_number(value: int | float) -> str:
    value = float(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(int(value))


def _percentage_delta(previous: int | float, current: int | float) -> float:
    if not previous:
        return 0.0
    return ((float(current) - float(previous)) / float(previous)) * 100
