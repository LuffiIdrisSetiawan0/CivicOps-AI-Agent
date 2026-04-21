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


def analytical_sql_for_question(question: str) -> str | None:
    q = question.lower()
    if any(term in q for term in ["backlog", "tertunda", "open ticket"]):
        return """
        SELECT r.name AS region, s.name AS service, k.month, k.backlog_count,
               k.request_count, k.completed_count, k.satisfaction_score
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        ORDER BY k.backlog_count DESC, k.month DESC
        LIMIT 10
        """
    if any(term in q for term in ["satisfaction", "kepuasan", "skor"]):
        return """
        SELECT r.name AS region, s.name AS service,
               ROUND(AVG(k.satisfaction_score), 2) AS avg_satisfaction,
               ROUND(AVG(k.avg_resolution_days), 2) AS avg_resolution_days
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        GROUP BY r.name, s.name
        ORDER BY avg_satisfaction ASC
        LIMIT 10
        """
    if any(term in q for term in ["budget", "anggaran", "realisasi", "spending"]):
        return """
        SELECT r.name AS region, s.category, s.name AS service,
               b.allocated_billion_idr, b.spent_billion_idr,
               ROUND((b.spent_billion_idr / b.allocated_billion_idr) * 100, 1) AS spend_pct,
               b.program_status
        FROM budgets b
        JOIN regions r ON r.id = b.region_id
        JOIN public_services s ON s.id = b.service_id
        ORDER BY spend_pct ASC, b.program_status DESC
        LIMIT 10
        """
    if any(term in q for term in ["complaint", "keluhan", "sentiment", "sentimen", "topik"]):
        return """
        SELECT r.name AS region, s.name AS service, c.topic, c.severity,
               COUNT(*) AS complaint_count, ROUND(AVG(c.sentiment), 2) AS avg_sentiment
        FROM complaint_logs c
        JOIN regions r ON r.id = c.region_id
        JOIN public_services s ON s.id = c.service_id
        GROUP BY r.name, s.name, c.topic, c.severity
        ORDER BY complaint_count DESC, avg_sentiment ASC
        LIMIT 10
        """
    if any(term in q for term in ["sla", "resolution", "penyelesaian", "terlambat"]):
        return """
        SELECT r.name AS region, s.name AS service, s.sla_days,
               ROUND(AVG(k.avg_resolution_days), 2) AS avg_resolution_days,
               ROUND(AVG(k.avg_resolution_days - s.sla_days), 2) AS days_over_sla
        FROM monthly_kpis k
        JOIN regions r ON r.id = k.region_id
        JOIN public_services s ON s.id = k.service_id
        GROUP BY r.name, s.name, s.sla_days
        HAVING avg_resolution_days > s.sla_days
        ORDER BY days_over_sla DESC
        LIMIT 10
        """
    if any(term in q for term in ["layanan", "service", "permintaan", "request"]):
        return """
        SELECT s.name AS service, s.category,
               SUM(k.request_count) AS total_requests,
               SUM(k.completed_count) AS total_completed,
               SUM(k.backlog_count) AS total_backlog
        FROM monthly_kpis k
        JOIN public_services s ON s.id = k.service_id
        GROUP BY s.name, s.category
        ORDER BY total_requests DESC
        LIMIT 10
        """
    return None

