"""SQLite database models for QSENTINEL."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Boolean, Column, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "db" / "qsentinel.db"
DB_PATH = Path(os.environ.get("QSENTINEL_DB_PATH", _DEFAULT_DB))
if os.environ.get("VERCEL"):
    DB_PATH = Path("/tmp/qsentinel.db")


class Base(DeclarativeBase):
    pass


class CusumState(Base):
    __tablename__ = "cusum_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    cusum_value = Column(Float, nullable=False, default=0.0)
    log_likelihood_ratio = Column(Float, nullable=False, default=0.0)
    drift_detected = Column(Boolean, nullable=False, default=False)


_engine = None
_session_factory = None


def init_db() -> None:
    global _engine, _session_factory
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Base.metadata.create_all(_engine)
    _session_factory = sessionmaker(bind=_engine)


def get_session_factory():
    if _session_factory is None:
        init_db()
    return _session_factory
