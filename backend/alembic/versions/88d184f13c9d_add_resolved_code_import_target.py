
"""Add resolved code import target"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "88d184f13c9d"
down_revision: Union[str, Sequence[str], None] = "9fdc7eea23b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "code_imports",
        sa.Column("resolved_code_file_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_code_imports_resolved_code_file_id_code_files",
        "code_imports",
        "code_files",
        ["resolved_code_file_id"],
        ["id"],
    )
    op.create_index(
        "ix_code_imports_resolved_code_file_id",
        "code_imports",
        ["resolved_code_file_id"],
        unique=False,
    )



def downgrade() -> None:
    op.drop_index(
        "ix_code_imports_resolved_code_file_id",
        table_name="code_imports",
    )
    op.drop_constraint(
        "fk_code_imports_resolved_code_file_id_code_files",
        "code_imports",
        type_="foreignkey",
    )
    op.drop_column("code_imports", "resolved_code_file_id")