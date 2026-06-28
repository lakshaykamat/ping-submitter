import json
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker


Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


def init_database(app):
    engine = create_engine(app.config["DATABASE_URL"], future=True)
    session_factory = scoped_session(
        sessionmaker(bind=engine, expire_on_commit=False, future=True)
    )
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = session_factory
    Base.metadata.create_all(bind=engine)
    sync_sqlite_columns(engine)

    @app.teardown_appcontext
    def remove_session(error=None):
        session_factory.remove()


def get_session():
    return current_app.extensions["db_session_factory"]()


def sync_sqlite_columns(engine):
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "submission_attempts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("submission_attempts")}
    columns_to_add = {
        "failure_reason": "TEXT",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "started_at": "DATETIME",
        "finished_at": "DATETIME",
        "runner_mode": "VARCHAR(40) NOT NULL DEFAULT 'agentic'",
        "captcha_policy": "VARCHAR(40) NOT NULL DEFAULT 'solve'",
    }
    with engine.begin() as connection:
        for column_name, column_type in columns_to_add.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE submission_attempts ADD COLUMN {column_name} {column_type}"))


class SubmissionJob(Base):
    __tablename__ = "submission_jobs"

    id = Column(String(36), primary_key=True)
    status = Column(String(40), nullable=False, default="queued")
    max_attempts = Column(Integer, nullable=False, default=3)
    url_count = Column(Integer, nullable=False, default=0)
    site_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    attempts = relationship(
        "SubmissionAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="SubmissionAttempt.id",
    )
    events = relationship(
        "JobEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobEvent.id",
    )
    report = relationship(
        "JobReport",
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def to_dict(self, include_attempts=False):
        data = {
            "id": self.id,
            "status": self.status,
            "max_attempts": self.max_attempts,
            "url_count": self.url_count,
            "site_count": self.site_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_attempts:
            data["attempts"] = [attempt.to_dict() for attempt in self.attempts]
        return data


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("submission_jobs.id"), nullable=False, index=True)
    site_id = Column(String(80), nullable=False)
    site_name = Column(String(200), nullable=False)
    submitted_url = Column(Text, nullable=False)
    status = Column(String(40), nullable=False, default="queued")
    runner_mode = Column(String(40), nullable=False, default="agentic")
    captcha_policy = Column(String(40), nullable=False, default="solve")
    attempt_number = Column(Integer, nullable=False, default=1)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("SubmissionJob", back_populates="attempts")
    captcha_challenges = relationship(
        "CaptchaChallenge",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="CaptchaChallenge.id",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "submitted_url": self.submitted_url,
            "status": self.status,
            "runner_mode": self.runner_mode,
            "captcha_policy": self.captcha_policy,
            "attempt_number": self.attempt_number,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class CaptchaChallenge(Base):
    __tablename__ = "captcha_challenges"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("submission_jobs.id"), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey("submission_attempts.id"), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="captcha_required")
    screenshot_path = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    attempt = relationship("SubmissionAttempt", back_populates="captcha_challenges")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "status": self.status,
            "screenshot_path": self.screenshot_path,
            "answer": self.answer,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class BrowserProfile(Base):
    __tablename__ = "browser_profiles"

    id = Column(Integer, primary_key=True)
    site_id = Column(String(80), nullable=False, index=True)
    account_label = Column(String(120), nullable=False, default="default")
    directory_path = Column(Text, nullable=False)
    approved_for_reuse = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "site_id": self.site_id,
            "account_label": self.account_label,
            "directory_path": self.directory_path,
            "approved_for_reuse": bool(self.approved_for_reuse),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }


class SiteMemory(Base):
    __tablename__ = "site_memories"

    id = Column(Integer, primary_key=True)
    site_id = Column(String(80), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="pending")
    source_attempt_id = Column(Integer, nullable=True, index=True)
    strategy_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def strategy(self):
        return json.loads(self.strategy_json)

    def to_dict(self):
        return {
            "id": self.id,
            "site_id": self.site_id,
            "status": self.status,
            "source_attempt_id": self.source_attempt_id,
            "strategy": self.strategy,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
        }


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("submission_jobs.id"), nullable=False, index=True)
    attempt_id = Column(Integer, nullable=True)
    site_id = Column(String(80), nullable=True)
    submitted_url = Column(Text, nullable=True)
    event_type = Column(String(80), nullable=False)
    level = Column(String(20), nullable=False, default="info")
    message = Column(Text, nullable=False)
    context_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    job = relationship("SubmissionJob", back_populates="events")

    @property
    def context(self):
        return json.loads(self.context_json)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.created_at.isoformat(),
            "level": self.level,
            "job_id": self.job_id,
            "attempt_id": self.attempt_id,
            "site_id": self.site_id,
            "submitted_url": self.submitted_url,
            "event_type": self.event_type,
            "message": self.message,
            "context": self.context,
        }


class JobReport(Base):
    __tablename__ = "job_reports"

    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), ForeignKey("submission_jobs.id"), nullable=False, unique=True, index=True)
    json_content = Column(Text, nullable=False)
    markdown_content = Column(Text, nullable=False)
    json_path = Column(Text, nullable=False)
    markdown_path = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    job = relationship("SubmissionJob", back_populates="report")

    def json_data(self):
        return json.loads(self.json_content)

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "json_path": self.json_path,
            "markdown_path": self.markdown_path,
            "generated_at": self.generated_at.isoformat(),
        }
