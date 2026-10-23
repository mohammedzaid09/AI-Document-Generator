
from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CodeEntity(Base):
    __tablename__ = "code_entities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    code_file_id: Mapped[int] = mapped_column(
        ForeignKey("code_files.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Stores extra structural details such as parameters,
    # class bases, and whether a function is asynchronous.
    details: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    code_file = relationship("CodeFile", back_populates="entities")
