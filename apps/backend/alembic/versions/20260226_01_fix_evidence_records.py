"""Ensure evidence_records has the full set of PS3 fields.

Revision ID: 20260226_01
Revises: None
Create Date: 2026-02-26
"""
from __future__ import annotations

from typing import Dict

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector


revision = "20260226_01"
down_revision = None
branch_labels = None
depends_on = None

TABLE_NAME = "evidence_records"
FK_NAME = "fk_evidence_records_clinvar_variation"

EXPECTED_COLUMN_TYPES: Dict[str, sa.types.TypeEngine] = {
	"clinvar_variation_id": sa.BigInteger(),
	"transcript_id": sa.String(length=100),
	"reference_genome": sa.String(length=50),
	"disease_name": sa.String(length=500),
	"arbitration_score": sa.Float(),
}


def _column_missing(existing: Dict[str, Dict[str, object]], column_name: str) -> bool:
	return column_name not in existing


def _needs_type_update(existing_column: Dict[str, object], desired_type: sa.types.TypeEngine) -> bool:
	existing_type = existing_column["type"]
	if type(existing_type) is not type(desired_type):
		return True
	desired_length = getattr(desired_type, "length", None)
	existing_length = getattr(existing_type, "length", None)
	return desired_length != existing_length


def _ensure_foreign_key(inspector: Inspector) -> None:
	for fk in inspector.get_foreign_keys(TABLE_NAME):
		if fk.get("referred_table") == "clinvar_variations" and fk.get("constrained_columns") == ["clinvar_variation_id"]:
			return
	op.create_foreign_key(
		FK_NAME,
		TABLE_NAME,
		"clinvar_variations",
		["clinvar_variation_id"],
		["variation_id"],
	)


def upgrade() -> None:
	bind = op.get_bind()
	inspector = inspect(bind)
	existing_columns = {col["name"]: col for col in inspector.get_columns(TABLE_NAME)}

	for column_name, desired_type in EXPECTED_COLUMN_TYPES.items():
		if _column_missing(existing_columns, column_name):
			op.add_column(TABLE_NAME, sa.Column(column_name, desired_type, nullable=True))
		else:
			column = existing_columns[column_name]
			if _needs_type_update(column, desired_type):
				op.alter_column(
					TABLE_NAME,
					column_name,
					existing_type=column["type"],
					type_=desired_type,
				)

	if "clinvar_variation_id" in EXPECTED_COLUMN_TYPES:
		_ensure_foreign_key(inspector)


def downgrade() -> None:
	bind = op.get_bind()
	inspector = inspect(bind)
	existing_columns = {col["name"]: col for col in inspector.get_columns(TABLE_NAME)}

	for fk in inspector.get_foreign_keys(TABLE_NAME):
		if fk.get("name") == FK_NAME:
			op.drop_constraint(FK_NAME, TABLE_NAME, type_="foreignkey")
			break

	for column_name in reversed(list(EXPECTED_COLUMN_TYPES.keys())):
		if column_name in existing_columns:
			op.drop_column(TABLE_NAME, column_name)
