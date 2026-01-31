"""PostgreSQL implementation of Evidence Repository.

Manages evidence item persistence and querying.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.domain.models.evidence_item import EvidenceItem, ACMGCode
from src.infrastructure.database.postgres_models import (
    EvidenceItem as EvidenceItemModel,
    ACMGCode as ACMGCodeEnum,
)
from src.domain.value_objects.confidence_score import ConfidenceScore


class EvidenceRepositoryImpl:
    """PostgreSQL implementation of evidence repository."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    def _to_domain(self, model: EvidenceItemModel) -> EvidenceItem:
        """Convert database model to domain entity."""
        from src.domain.models.evidence_item import BoundingBox

        bounding_box = BoundingBox(
            x=model.bounding_box["x"],
            y=model.bounding_box["y"],
            width=model.bounding_box["width"],
            height=model.bounding_box["height"]
        ) if model.bounding_box else BoundingBox(0, 0, 1, 1)

        return EvidenceItem(
            id=model.id,
            document_id=model.document_id,
            acmg_code=ACMGCode(model.acmg_code.value),
            confidence_score=model.confidence_score,
            source_page=model.source_page,
            bounding_box=bounding_box,
            source_hash=model.source_hash,
            supporting_text=model.supporting_text,
            review_required=model.review_required,
            human_reviewed=model.human_reviewed,
            human_notes=model.human_notes,
            variant_id=model.variant_id,
            extracted_at=model.extracted_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: EvidenceItem) -> EvidenceItemModel:
        """Convert domain entity to database model."""
        return EvidenceItemModel(
            id=entity.id,
            document_id=entity.document_id,
            acmg_code=ACMGCodeEnum(entity.acmg_code.value),
            confidence_score=entity.confidence_score,
            source_page=entity.source_page,
            bounding_box=entity.bounding_box.to_dict() if entity.bounding_box else None,
            source_hash=entity.source_hash,
            supporting_text=entity.supporting_text,
            review_required=entity.review_required,
            human_reviewed=entity.human_reviewed,
            human_notes=entity.human_notes,
            variant_id=entity.variant_id,
            extracted_at=entity.extracted_at,
            updated_at=entity.updated_at,
        )

    async def save(self, evidence_item: EvidenceItem) -> EvidenceItem:
        """Save or update an evidence item."""
        try:
            # Check if evidence item exists
            stmt = select(EvidenceItemModel).where(EvidenceItemModel.id == evidence_item.id)
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.document_id = evidence_item.document_id
                existing.acmg_code = ACMGCodeEnum(evidence_item.acmg_code.value)
                existing.confidence_score = evidence_item.confidence_score
                existing.source_page = evidence_item.source_page
                existing.bounding_box = evidence_item.bounding_box.to_dict() if evidence_item.bounding_box else None
                existing.source_hash = evidence_item.source_hash
                existing.supporting_text = evidence_item.supporting_text
                existing.review_required = evidence_item.review_required
                existing.human_reviewed = evidence_item.human_reviewed
                existing.human_notes = evidence_item.human_notes
                existing.variant_id = evidence_item.variant_id
                existing.updated_at = evidence_item.updated_at
            else:
                # Create new
                model = self._to_model(evidence_item)
                self.session.add(model)

            await self.session.commit()
            await self.session.refresh(existing if existing else model)
            return self._to_domain(existing if existing else model)

        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Failed to save evidence item: {e}")

    async def find_by_id(self, evidence_id: UUID) -> Optional[EvidenceItem]:
        """Find evidence item by ID."""
        stmt = select(EvidenceItemModel).where(EvidenceItemModel.id == evidence_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def find_by_document_id(self, document_id: UUID) -> List[EvidenceItem]:
        """Find all evidence items for a document."""
        stmt = (
            select(EvidenceItemModel)
            .where(EvidenceItemModel.document_id == document_id)
            .order_by(EvidenceItemModel.extracted_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_by_acmg_code(self, acmg_code: str) -> List[EvidenceItem]:
        """Find evidence items by ACMG code."""
        stmt = (
            select(EvidenceItemModel)
            .where(EvidenceItemModel.acmg_code == ACMGCodeEnum(acmg_code))
            .order_by(EvidenceItemModel.confidence_score.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_needing_review(self, limit: int = 100) -> List[EvidenceItem]:
        """Find evidence items that need human review."""
        stmt = (
            select(EvidenceItemModel)
            .where(
                and_(
                    EvidenceItemModel.review_required == True,
                    EvidenceItemModel.human_reviewed == False
                )
            )
            .order_by(EvidenceItemModel.confidence_score.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_by_variant_id(self, variant_id: UUID) -> List[EvidenceItem]:
        """Find evidence items linked to a specific variant."""
        stmt = (
            select(EvidenceItemModel)
            .where(EvidenceItemModel.variant_id == variant_id)
            .order_by(EvidenceItemModel.extracted_at.desc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_pathogenic_evidence(self, limit: int = 100) -> List[EvidenceItem]:
        """Find evidence items indicating pathogenicity."""
        stmt = (
            select(EvidenceItemModel)
            .where(
                EvidenceItemModel.acmg_code.in_([
                    ACMGCodeEnum.PS1, ACMGCodeEnum.PS2, ACMGCodeEnum.PS3, ACMGCodeEnum.PS4,
                    ACMGCodeEnum.PM1, ACMGCodeEnum.PM2, ACMGCodeEnum.PM3, ACMGCodeEnum.PM4,
                    ACMGCodeEnum.PM5, ACMGCodeEnum.PM6,
                    ACMGCodeEnum.PP1, ACMGCodeEnum.PP2, ACMGCodeEnum.PP3, ACMGCodeEnum.PP4,
                    ACMGCodeEnum.PP5
                ])
            )
            .order_by(EvidenceItemModel.confidence_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def find_benign_evidence(self, limit: int = 100) -> List[EvidenceItem]:
        """Find evidence items indicating benign variants."""
        stmt = (
            select(EvidenceItemModel)
            .where(
                EvidenceItemModel.acmg_code.in_([
                    ACMGCodeEnum.BA1,
                    ACMGCodeEnum.BS1, ACMGCodeEnum.BS2, ACMGCodeEnum.BS3, ACMGCodeEnum.BS4,
                    ACMGCodeEnum.BP1, ACMGCodeEnum.BP2, ACMGCodeEnum.BP3, ACMGCodeEnum.BP4,
                    ACMGCodeEnum.BP5, ACMGCodeEnum.BP6, ACMGCodeEnum.BP7
                ])
            )
            .order_by(EvidenceItemModel.confidence_score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(model) for model in models]

    async def delete(self, evidence_id: UUID) -> bool:
        """Delete an evidence item."""
        stmt = select(EvidenceItemModel).where(EvidenceItemModel.id == evidence_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def delete_by_document_id(self, document_id: UUID) -> int:
        """Delete all evidence items for a document."""
        stmt = select(EvidenceItemModel).where(EvidenceItemModel.document_id == document_id)
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        count = len(models)
        for model in models:
            await self.session.delete(model)

        await self.session.commit()
        return count

    async def count_by_document_id(self, document_id: UUID) -> int:
        """Count evidence items for a document."""
        stmt = (
            select(func.count())
            .select_from(EvidenceItemModel)
            .where(EvidenceItemModel.document_id == document_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def count_needing_review(self) -> int:
        """Count evidence items needing human review."""
        stmt = (
            select(func.count())
            .select_from(EvidenceItemModel)
            .where(
                and_(
                    EvidenceItemModel.review_required == True,
                    EvidenceItemModel.human_reviewed == False
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_confidence_statistics(self) -> dict:
        """Get confidence score statistics."""
        stmt = select(
            func.avg(EvidenceItemModel.confidence_score).label('avg_confidence'),
            func.min(EvidenceItemModel.confidence_score).label('min_confidence'),
            func.max(EvidenceItemModel.confidence_score).label('max_confidence'),
            func.count().label('total_count')
        )
        result = await self.session.execute(stmt)
        stats = result.fetchone()

        return {
            'average_confidence': float(stats.avg_confidence) if stats.avg_confidence else 0.0,
            'min_confidence': float(stats.min_confidence) if stats.min_confidence else 0.0,
            'max_confidence': float(stats.max_confidence) if stats.max_confidence else 0.0,
            'total_items': stats.total_count or 0
        }