import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:123@localhost:5432/metrics_db",
)


if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    login         = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    last_name     = Column(String(100), nullable=True)
    first_name    = Column(String(100), nullable=False)
    middle_name   = Column(String(100), nullable=True)
    role          = Column(String(20),  nullable=False, default="analyst")
    created_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    projects = relationship("Project", back_populates="owner", cascade="all, delete")


class Project(Base):
    __tablename__ = "projects"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    owner    = relationship("User", back_populates="projects")
    datasets = relationship("Dataset", back_populates="project", cascade="all, delete")
    reports  = relationship("Report",  back_populates="project", cascade="all, delete")


class Dataset(Base):
    __tablename__ = "datasets"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id  = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id     = Column(String, ForeignKey("users.id",    ondelete="CASCADE"), nullable=False)
    filename    = Column(String(255), nullable=False)
    file_path   = Column(Text, nullable=False)
    row_count   = Column(Integer, default=0)
    columns     = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    project = relationship("Project", back_populates="datasets")
    reports = relationship("Report",  back_populates="dataset", cascade="all, delete")


class Report(Base):
    __tablename__ = "reports"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id  = Column(String, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    project_id  = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    metrics     = Column(JSON, nullable=False)
    result_json = Column(JSON, nullable=False, default=dict)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    dataset = relationship("Dataset", back_populates="reports")
    project = relationship("Project", back_populates="reports")