from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    province: Mapped[str] = mapped_column(String(120), index=True)
    type: Mapped[str] = mapped_column(String(30))
    population: Mapped[int] = mapped_column(Integer)

    kpis: Mapped[list["MonthlyKPI"]] = relationship(back_populates="region")
    complaints: Mapped[list["ComplaintLog"]] = relationship(back_populates="region")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="region")


class PublicService(Base):
    __tablename__ = "public_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    channel: Mapped[str] = mapped_column(String(80))
    sla_days: Mapped[int] = mapped_column(Integer)

    kpis: Mapped[list["MonthlyKPI"]] = relationship(back_populates="service")
    complaints: Mapped[list["ComplaintLog"]] = relationship(back_populates="service")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="service")


class MonthlyKPI(Base):
    __tablename__ = "monthly_kpis"
    __table_args__ = (UniqueConstraint("region_id", "service_id", "month", name="uq_kpi_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("public_services.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    request_count: Mapped[int] = mapped_column(Integer)
    completed_count: Mapped[int] = mapped_column(Integer)
    avg_resolution_days: Mapped[float] = mapped_column(Float)
    satisfaction_score: Mapped[float] = mapped_column(Float)
    backlog_count: Mapped[int] = mapped_column(Integer)

    region: Mapped[Region] = relationship(back_populates="kpis")
    service: Mapped[PublicService] = relationship(back_populates="kpis")


class ComplaintLog(Base):
    __tablename__ = "complaint_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("public_services.id"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    channel: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(30), index=True)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    sentiment: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)

    region: Mapped[Region] = relationship(back_populates="complaints")
    service: Mapped[PublicService] = relationship(back_populates="complaints")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("region_id", "service_id", "year", name="uq_budget_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("public_services.id"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    allocated_billion_idr: Mapped[float] = mapped_column(Float)
    spent_billion_idr: Mapped[float] = mapped_column(Float)
    vendor: Mapped[str] = mapped_column(String(120))
    program_status: Mapped[str] = mapped_column(String(40), index=True)

    region: Mapped[Region] = relationship(back_populates="budgets")
    service: Mapped[PublicService] = relationship(back_populates="budgets")

