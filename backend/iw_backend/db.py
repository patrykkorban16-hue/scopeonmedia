"""Warstwa składowania (SQLAlchemy 2): baza metadanych + baza treści. Surowe HTML/JSON i zrzuty ekranu
trafiają do Object Storage (storage.py) – w SQL przechowujemy klucze obiektów."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
                        create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from . import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    """Podmiot z rejestru: firmy inwestycyjne (KNF) i Lista ostrzeżeń publicznych KNF."""
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("name", "category", name="uq_entity_name_cat"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(400), index=True)
    former_names: Mapped[list] = mapped_column(JSON, default=list)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    social_handles: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(40))
    authorized: Mapped[bool] = mapped_column(Boolean, default=True)
    country: Mapped[str] = mapped_column(String(8), default="PL")
    register_id: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(400))
    license_date: Mapped[str | None] = mapped_column(String(20))
    scope: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(200), default="demo")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="running")
    pages: Mapped[int] = mapped_column(Integer, default=0)
    new_documents: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Document(Base):
    """Metadane materiału (strona WWW, post, reklama)."""
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("url", name="uq_document_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2000))
    fetched_url: Mapped[str] = mapped_column(String(2000))
    domain: Mapped[str] = mapped_column(String(300), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str | None] = mapped_column(String(1000))
    author: Mapped[str | None] = mapped_column(String(300))
    author_url: Mapped[str | None] = mapped_column(String(2000))
    language: Mapped[str | None] = mapped_column(String(8))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    availability: Mapped[str] = mapped_column(String(20), default="online")     # online | removed
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    simhash: Mapped[str | None] = mapped_column(String(20))
    raw_key: Mapped[str | None] = mapped_column(String(300))
    screenshots: Mapped[dict] = mapped_column(JSON, default=dict)                # viewport -> klucz obiektu
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    crawl_job_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_jobs.id"))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)                       # wynik ekstrakcji (JSON)
    ground_truth: Mapped[dict] = mapped_column(JSON, default=dict)               # etykiety zbioru walidacyjnego
    content: Mapped["Content"] = relationship(back_populates="document", uselist=False, cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Content(Base):
    """Baza treści: tekst po preprocessingu, tokeny, embedding, bloki z cechami wizualnymi."""
    __tablename__ = "contents"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    tokens: Mapped[list] = mapped_column(JSON, default=list)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list | None] = mapped_column(JSON)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    preprocessed: Mapped[dict] = mapped_column(JSON, default=dict)               # pełna odpowiedź /v1/preprocess
    document: Mapped[Document] = relationship(back_populates="content")


class Finding(Base):
    """Ujednolicony wynik (agregat modułów 1/2/3) + stan obsługi przez analityka."""
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("document_id", "module", name="uq_finding_doc_module"),
                      Index("ix_findings_module_score", "module", "score"))
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    module: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(120))
    score: Mapped[float] = mapped_column(Float)
    rule_score: Mapped[float] = mapped_column(Float)
    llm_score: Mapped[float | None] = mapped_column(Float)
    llm: Mapped[dict] = mapped_column(JSON, default=dict)
    firm: Mapped[dict] = mapped_column(JSON, default=dict)
    advertiser: Mapped[dict] = mapped_column(JSON, default=dict)
    entity: Mapped[dict] = mapped_column(JSON, default=dict)
    excerpt: Mapped[str] = mapped_column(Text)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    analyst_note: Mapped[str | None] = mapped_column(Text)
    ground_truth: Mapped[bool | None] = mapped_column(Boolean)
    event_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    document: Mapped[Document] = relationship(back_populates="findings")


class StatusHistory(Base):
    __tablename__ = "status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    old_status: Mapped[str] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


# ------------------------------------------------------------------------------ silnik
_sqlite = config.DATABASE_URL.startswith("sqlite")
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True,
                       connect_args={"check_same_thread": False, "timeout": 30} if _sqlite else {})
if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):  # pragma: no cover
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ------------------------------------------------------------------------------ ustawienia / progi
def get_setting(s, key: str, default=None):
    row = s.get(Setting, key)
    return row.value if row else default


def put_setting(s, key: str, value) -> None:
    row = s.get(Setting, key)
    if row:
        row.value = value
    else:
        s.add(Setting(key=key, value=value))


def get_thresholds(s) -> dict[int, float]:
    th = dict(config.DEFAULT_THRESHOLDS)
    th.update({int(k): float(v) for k, v in (get_setting(s, "thresholds") or {}).items()})
    return th


def set_threshold(s, module: int, value: float) -> dict[int, float]:
    th = get_thresholds(s)
    th[module] = round(max(0.0, min(1.0, float(value))), 3)
    put_setting(s, "thresholds", {str(k): v for k, v in th.items()})
    return th


def high_cut(threshold: float) -> float:
    return threshold + (1 - threshold) / 2


def risk_level(score: float, threshold: float) -> str:
    """low = poniżej progu (nie flagowane); medium = [próg, połowa przedziału); high = górna połowa nad progiem."""
    if score < threshold:
        return "low"
    return "high" if score >= high_cut(threshold) else "medium"
