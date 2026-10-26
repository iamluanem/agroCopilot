"""Data model (reduced). All geometries in EPSG:4326."""
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, SmallInteger,
    String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class Synthetic:
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Farm(Synthetic, Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    municipality: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(2))
    crop: Mapped[str] = mapped_column(String(60))
    area_ha: Mapped[float] = mapped_column(Float)
    reference_date: Mapped[date] = mapped_column(Date)
    soil_notes: Mapped[str | None] = mapped_column(Text)
    boundary = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    fields: Mapped[list["Field"]] = relationship(back_populates="farm", order_by="Field.code")
    seasons: Mapped[list["CropSeason"]] = relationship(order_by="CropSeason.sowing_date")


class CropSeason(Base):
    __tablename__ = "crop_seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(20))
    crop: Mapped[str] = mapped_column(String(60))
    sowing_date: Mapped[date] = mapped_column(Date)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    expected_yield_bags_ha: Mapped[float | None] = mapped_column(Float)
    realized_yield_bags_ha: Mapped[float | None] = mapped_column(Float)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class Field(Synthetic, Base):
    __tablename__ = "fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(60))
    area_ha: Mapped[float] = mapped_column(Float)
    soil_texture: Mapped[str | None] = mapped_column(String(60))
    irrigation: Mapped[str] = mapped_column(String(30), default="rainfed")
    boundary_source: Mapped[str] = mapped_column(String(30), default="synthetic_demo")
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    farm: Mapped[Farm] = relationship(back_populates="fields")


class ManagementCell(Base):
    __tablename__ = "management_cells"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    row: Mapped[int] = mapped_column(Integer)
    col: Mapped[int] = mapped_column(Integer)
    area_ha: Mapped[float] = mapped_column(Float)
    geom = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cell_id: Mapped[int] = mapped_column(ForeignKey("management_cells.id", ondelete="CASCADE"))
    season_id: Mapped[int] = mapped_column(ForeignKey("crop_seasons.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    das: Mapped[int] = mapped_column(SmallInteger)  # days after sowing
    ndvi: Mapped[float | None] = mapped_column(Float)
    ndre: Mapped[float | None] = mapped_column(Float)
    cloud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(30), default="demo")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        Index("ix_obs_season_date", "season_id", "date"),
        Index("ix_obs_cell_date", "cell_id", "date"),
    )


class WeatherDaily(Synthetic, Base):
    __tablename__ = "weather_daily"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    rain_mm: Mapped[float] = mapped_column(Float)
    tmax_c: Mapped[float] = mapped_column(Float)
    tmin_c: Mapped[float] = mapped_column(Float)


class RiskAssessment(Synthetic, Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    cell_id: Mapped[int | None] = mapped_column(ForeignKey("management_cells.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    level: Mapped[str] = mapped_column(String(12))  # green|yellow|red
    anomaly_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(10))  # low|moderate|high
    method: Mapped[str] = mapped_column(String(60))
    affected_ha: Mapped[float | None] = mapped_column(Float)
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326))  # affected zone
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    hypotheses: Mapped[list["Hypothesis"]] = relationship(order_by="Hypothesis.rank")


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(SmallInteger)
    cause: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[str] = mapped_column(String(10))
    supporting_evidence: Mapped[list] = mapped_column(JSON, default=list)
    missing_data: Mapped[list] = mapped_column(JSON, default=list)


class EconomicEstimate(Base):
    __tablename__ = "economic_estimates"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"))
    affected_ha: Mapped[float] = mapped_column(Float)
    exposure_min: Mapped[float] = mapped_column(Float)
    exposure_max: Mapped[float] = mapped_column(Float)
    inspection_cost: Mapped[float] = mapped_column(Float)
    intervention_cost: Mapped[float] = mapped_column(Float)
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)


class Task(Synthetic, Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("risk_assessments.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(30), default="inspection")
    priority: Mapped[str] = mapped_column(String(10))  # high|medium|low
    assignee: Mapped[str | None] = mapped_column(String(80))
    due_date: Mapped[date | None] = mapped_column(Date)
    instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Inspection(Synthetic, Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    inspected_at: Mapped[date] = mapped_column(Date)
    findings: Mapped[str] = mapped_column(Text)
    verified_cause: Mapped[str | None] = mapped_column(String(80))
    photos: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[str] = mapped_column(String(80))


class Intervention(Synthetic, Base):
    __tablename__ = "interventions"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id", ondelete="SET NULL"))
    recommended_action: Mapped[str | None] = mapped_column(Text)
    approved_action: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[str] = mapped_column(String(80))
    executed_at: Mapped[date] = mapped_column(Date)
    actual_cost: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class OutcomeMeasurement(Synthetic, Base):
    __tablename__ = "outcome_measurements"
    id: Mapped[int] = mapped_column(primary_key=True)
    intervention_id: Mapped[int] = mapped_column(ForeignKey("interventions.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(20), default="ndvi")
    before_start: Mapped[date] = mapped_column(Date)
    before_end: Mapped[date] = mapped_column(Date)
    after_start: Mapped[date] = mapped_column(Date)
    after_end: Mapped[date] = mapped_column(Date)
    before_value: Mapped[float] = mapped_column(Float)
    after_value: Mapped[float] = mapped_column(Float)
    comparison_before: Mapped[float | None] = mapped_column(Float)
    comparison_after: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    delta_vs_comparison: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(Text)
    comparison_area: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))


class MemoryEvent(Synthetic, Base):
    __tablename__ = "memory_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id", ondelete="CASCADE"), index=True)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("crop_seasons.id", ondelete="SET NULL"))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(30))  # anomaly|inspection|intervention|outcome|note|season|task
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    refs: Mapped[dict] = mapped_column(JSON, default=dict)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
