from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String, nullable=False)  # platform_summary, accommodation, university, landlord
    period_year = Column(Integer, nullable=False)
    period_month = Column(Integer, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="generating")  # generating, complete, failed
    entity_id = Column(Integer, nullable=True)
    entity_type = Column(String, nullable=True)  # accommodation, university, landlord

    metrics = relationship("ReportMetric", back_populates="report", cascade="all, delete-orphan")


class ReportMetric(Base):
    __tablename__ = "report_metrics"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False)
    metric_key = Column(String, nullable=False)
    metric_value = Column(Float, nullable=True)
    metric_label = Column(String, nullable=False)
    metric_category = Column(String, nullable=False)
    breakdown = Column(JSONB, nullable=True)

    report = relationship("MonthlyReport", back_populates="metrics")