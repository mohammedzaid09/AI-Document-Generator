

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CodeImport(Base):
    __tablename__ = "code_imports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # The source file containing this import statement.
    code_file_id: Mapped[int] = mapped_column(
        ForeignKey("code_files.id"),
        nullable=False,
        index=True,
    )

    # The imported module, such as app.core.database.
    module: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    import_kind: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    imported_names: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    relative_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # The target file, populated when the import is resolved.
    resolved_code_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("code_files.id"),
        nullable=True,
        index=True,
    )

    code_file = relationship(
        "CodeFile",
        back_populates="imports",
        foreign_keys=[code_file_id],
    )

    resolved_code_file = relationship(
        "CodeFile",
        foreign_keys=[resolved_code_file_id],
    )
