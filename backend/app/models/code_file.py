
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CodeFile(Base):
    __tablename__ = "code_files"

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "path",
            name="uq_code_files_repository_path",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False,
        index=True,
    )

    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)

    analysis_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    analysis_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    last_analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    repository = relationship("Repository")
    entities = relationship(
        "CodeEntity",
        back_populates="code_file",
        cascade="all, delete-orphan",
    )

    imports = relationship(
        "CodeImport",
        back_populates="code_file",
        foreign_keys="CodeImport.code_file_id",
        cascade="all, delete-orphan",
    )
