"""
Database Models
SQLAlchemy ORM models for the miner monitoring system.
Uses async SQLite for development; easily swappable to PostgreSQL/TimescaleDB.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, Boolean,
    DateTime, Text, JSON, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Miner(Base):
    """A registered miner device."""
    __tablename__ = "miners"

    id = Column(String(64), primary_key=True)          # user-defined slug e.g. "l3-01"
    name = Column(String(128), nullable=False)
    ip = Column(String(45), nullable=False)             # IPv4 or IPv6
    port = Column(Integer, default=4028)
    preset_id = Column(String(64), default="antminer_l3")
    poll_interval = Column(Integer, default=30)        # seconds
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # JSON blob of the last raw API response — useful for debugging
    last_raw_response = Column(JSON, nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    telemetry = relationship("TelemetryReading", back_populates="miner", cascade="all, delete-orphan")
    anomaly_events = relationship("AnomalyEvent", back_populates="miner", cascade="all, delete-orphan")


class TelemetryReading(Base):
    """
    One time-series row per poll cycle.
    Values are stored as a JSON dict so the schema is flexible
    regardless of which features the user selected.
    """
    __tablename__ = "telemetry_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    miner_id = Column(String(64), ForeignKey("miners.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    values = Column(JSON, nullable=False)               # {"Hashrate (5s avg)": 90.6, ...}
    poll_ok = Column(Boolean, default=True)             # False if the miner was unreachable

    miner = relationship("Miner", back_populates="telemetry")

    __table_args__ = (
        Index("ix_telemetry_miner_ts", "miner_id", "timestamp"),
    )


class TrainingRun(Base):
    """
    Tracks a calibration / learning phase for a miner.
    The system learns normal behavior during this period.
    """
    __tablename__ = "training_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    miner_id = Column(String(64), ForeignKey("miners.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    sample_count = Column(Integer, default=0)
    target_samples = Column(Integer, default=240)       # 240 × 30s = 2 hours
    features = Column(JSON, nullable=True)              # list of feature names used
    baseline_stats = Column(JSON, nullable=True)        # {"feature": {"mean": ..., "std": ...}}
    model_path = Column(String(256), nullable=True)     # path to saved sklearn/torch model
    is_active = Column(Boolean, default=True)           # False once monitoring starts
    status = Column(String(32), default="learning")     # learning | complete | failed


class AnomalyEvent(Base):
    """
    Records each anomaly detection event (YELLOW or RED status change).
    """
    __tablename__ = "anomaly_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    miner_id = Column(String(64), ForeignKey("miners.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(16), nullable=False)          # GREEN | YELLOW | RED
    if_score = Column(Float, nullable=True)              # Isolation Forest anomaly score
    lstm_error = Column(Float, nullable=True)            # LSTM reconstruction error
    triggered_rules = Column(JSON, nullable=True)        # list of rule names that fired
    affected_features = Column(JSON, nullable=True)      # features outside normal range
    raw_values = Column(JSON, nullable=True)             # snapshot of values at event time
    chatbot_diagnosis = Column(Text, nullable=True)      # LLM-generated explanation

    miner = relationship("Miner", back_populates="anomaly_events")


class ChatMessage(Base):
    """Persists chatbot conversation history per miner."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    miner_id = Column(String(64), nullable=True)        # None = general chat
    role = Column(String(16), nullable=False)            # user | assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
