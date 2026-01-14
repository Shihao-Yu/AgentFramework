"""
Storage adapter for Query Plans.

PostgreSQL-backed storage using KnowledgeNode models.
Stores plans with full version history support for audit and rollback.

Key Features:
- Plan CRUD operations with soft delete
- Version history with snapshots
- Semantic search over plans (via PostgreSQL text search)
- Tenant isolation via tenant_id
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from ..core.planning_models import (
    PlanStatus,
    PlanVersion,
    QueryPlan,
    QueryPlanSummary,
)

logger = logging.getLogger(__name__)


class PlanStorage:
    """
    Storage operations for Query Plans.
    
    Uses PostgreSQL with KnowledgeNode models for tenant isolation.
    Provides full version history support for audit and rollback.
    
    Usage:
        storage = PlanStorage(session)
        
        # Save plan
        plan_id = await storage.save_plan(plan)
        
        # Get plan
        plan = await storage.get_plan(tenant_id, document_name, plan_id)
        
        # Search plans
        results = await storage.search_plans(tenant_id, document_name, "orders query")
    """
    
    def __init__(self, session: 'AsyncSession'):
        """
        Initialize plan storage.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        logger.info("Initialized PlanStorage")
    
    # ==========================================================================
    # Plan CRUD Operations
    # ==========================================================================
    
    async def save_plan(
        self,
        plan: QueryPlan,
        create_version: bool = True,
        change_type: str = "update",
        change_description: str = "",
    ) -> str:
        """
        Save or update a plan, optionally creating a version snapshot.
        
        Args:
            plan: QueryPlan to save
            create_version: Whether to create a version snapshot
            change_type: Type of change for version tracking
            change_description: Human-readable change description
        
        Returns:
            plan_id
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus
        from sqlalchemy import select
        
        # Update timestamp
        plan.updated_at = datetime.now()
        
        # Check for existing plan
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == plan.tenant_id,
            KnowledgeNode.dataset_name == plan.document_name,
            KnowledgeNode.node_type == NodeType.QUERY_PLAN,
            KnowledgeNode.source_reference == plan.plan_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        # Build content
        content = {
            "plan_data": plan.model_dump(mode="json"),
            "status": plan.status.value,
            "step_count": len(plan.steps),
            "is_deleted": plan.is_deleted,
        }
        
        # Build summary
        summary = f"{plan.original_question[:100]}..." if len(plan.original_question) > 100 else plan.original_question
        
        if existing:
            existing.title = f"Plan: {plan.original_question[:50]}"
            existing.summary = summary
            existing.content = content
            existing.version = plan.current_version
            existing.updated_at = datetime.utcnow()
            
            await self.session.flush()
            logger.debug(f"Updated plan {plan.plan_id}")
        else:
            node = KnowledgeNode(
                tenant_id=plan.tenant_id,
                node_type=NodeType.QUERY_PLAN,
                title=f"Plan: {plan.original_question[:50]}",
                summary=summary,
                content=content,
                dataset_name=plan.document_name,
                source_reference=plan.plan_id,
                version=plan.current_version,
                status=KnowledgeStatus.PUBLISHED,
                source="contextforge",
            )
            self.session.add(node)
            await self.session.flush()
            logger.debug(f"Created plan {plan.plan_id}")
        
        # Create version if requested
        if create_version:
            await self._save_version(
                plan=plan,
                change_type=change_type,
                change_description=change_description,
            )
        
        logger.info(f"Saved plan {plan.plan_id} (version {plan.current_version})")
        return plan.plan_id
    
    async def get_plan(
        self,
        tenant_id: str,
        document_name: str,
        plan_id: str,
        include_deleted: bool = False,
    ) -> Optional[QueryPlan]:
        """
        Retrieve a plan by ID.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            plan_id: Plan ID to retrieve
            include_deleted: Include soft-deleted plans
        
        Returns:
            QueryPlan if found, None otherwise
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.QUERY_PLAN,
            KnowledgeNode.source_reference == plan_id,
        )
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node or not node.content:
            return None
        
        try:
            plan_data = node.content.get("plan_data")
            if not plan_data:
                return None
            
            plan = QueryPlan.model_validate(plan_data)
            
            # Check soft delete
            if plan.is_deleted and not include_deleted:
                return None
            
            return plan
        except Exception as e:
            logger.error(f"Failed to parse plan {plan_id}: {e}")
            return None
    
    async def list_plans(
        self,
        tenant_id: str,
        document_name: str,
        status_filter: Optional[List[PlanStatus]] = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[QueryPlanSummary]:
        """
        List plans for a tenant/document with optional status filter.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            status_filter: Optional list of statuses to filter by
            include_deleted: Include soft-deleted plans
            limit: Maximum number of plans to return
            offset: Number of plans to skip
        
        Returns:
            List of QueryPlanSummary objects
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.QUERY_PLAN,
        ).order_by(KnowledgeNode.updated_at.desc())
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        summaries = []
        for node in nodes:
            try:
                if not node.content:
                    continue
                    
                plan_data = node.content.get("plan_data")
                if not plan_data:
                    continue
                
                plan = QueryPlan.model_validate(plan_data)
                
                # Apply filters
                if plan.is_deleted and not include_deleted:
                    continue
                
                if status_filter and plan.status not in status_filter:
                    continue
                
                summaries.append(QueryPlanSummary.from_plan(plan))
            except Exception as e:
                logger.warning(f"Failed to parse plan: {e}")
                continue
        
        # Apply pagination
        return summaries[offset:offset + limit]
    
    async def delete_plan(
        self,
        tenant_id: str,
        document_name: str,
        plan_id: str,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete a plan.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            plan_id: Plan to delete
            soft_delete: If True, mark as deleted; if False, permanently remove
        
        Returns:
            True if successful
        """
        if soft_delete:
            plan = await self.get_plan(tenant_id, document_name, plan_id)
            if not plan:
                return False
            
            plan.is_deleted = True
            plan.deleted_at = datetime.now()
            plan.status = PlanStatus.CANCELLED
            
            await self.save_plan(
                plan,
                create_version=True,
                change_type="deletion",
                change_description="Plan soft deleted",
            )
            return True
        else:
            # Hard delete
            from app.models.nodes import KnowledgeNode
            from app.models.enums import NodeType
            from sqlalchemy import delete
            
            stmt = delete(KnowledgeNode).where(
                KnowledgeNode.tenant_id == tenant_id,
                KnowledgeNode.dataset_name == document_name,
                KnowledgeNode.node_type == NodeType.QUERY_PLAN,
                KnowledgeNode.source_reference == plan_id,
            )
            
            try:
                result = await self.session.execute(stmt)
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"Hard deleted plan {plan_id}")
                return deleted
            except Exception as e:
                logger.error(f"Failed to delete plan {plan_id}: {e}")
                return False
    
    # ==========================================================================
    # Version Operations
    # ==========================================================================
    
    async def _save_version(
        self,
        plan: QueryPlan,
        change_type: str,
        change_description: str,
        previous_snapshot: Optional[Dict[str, Any]] = None,
    ) -> PlanVersion:
        """
        Create a new version snapshot.
        
        Args:
            plan: Current plan state
            change_type: Type of change
            change_description: Human-readable description
            previous_snapshot: Optional previous state for diff calculation
        
        Returns:
            Created PlanVersion
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType, KnowledgeStatus
        
        # Create version
        version = PlanVersion(
            version_number=plan.current_version,
            plan_id=plan.plan_id,
            plan_snapshot=plan.model_dump(mode="json"),
            change_type=change_type,
            change_description=change_description,
            changes_diff=self._calculate_diff(previous_snapshot, plan.model_dump(mode="json"))
            if previous_snapshot
            else {},
        )
        
        # Store version as a KnowledgeNode
        version_id = f"{plan.plan_id}_v{plan.current_version}"
        content = {
            "version_data": version.model_dump(mode="json"),
            "plan_id": plan.plan_id,
            "version_number": plan.current_version,
            "change_type": change_type,
        }
        
        node = KnowledgeNode(
            tenant_id=plan.tenant_id,
            node_type=NodeType.PLAN_VERSION,
            title=f"Plan {plan.plan_id} v{plan.current_version}",
            summary=change_description or f"Version {plan.current_version}",
            content=content,
            dataset_name=plan.document_name,
            source_reference=version_id,
            version=plan.current_version,
            status=KnowledgeStatus.PUBLISHED,
            source="contextforge",
        )
        self.session.add(node)
        await self.session.flush()
        
        logger.debug(f"Saved version {plan.current_version} for plan {plan.plan_id}")
        return version
    
    def _calculate_diff(
        self,
        previous: Optional[Dict[str, Any]],
        current: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Calculate diff between two plan states.
        
        Simple implementation - can be enhanced with deepdiff library.
        """
        if not previous:
            return {"type": "creation"}
        
        diff: Dict[str, Any] = {}
        
        # Check key fields for changes
        key_fields = [
            "status",
            "disambiguation_complete",
            "current_version",
        ]
        
        for field in key_fields:
            if previous.get(field) != current.get(field):
                diff[field] = {
                    "old": previous.get(field),
                    "new": current.get(field),
                }
        
        # Check steps changes
        prev_steps = {s["step_id"]: s for s in previous.get("steps", [])}
        curr_steps = {s["step_id"]: s for s in current.get("steps", [])}
        
        added_steps = set(curr_steps.keys()) - set(prev_steps.keys())
        removed_steps = set(prev_steps.keys()) - set(curr_steps.keys())
        
        if added_steps:
            diff["steps_added"] = list(added_steps)
        if removed_steps:
            diff["steps_removed"] = list(removed_steps)
        
        # Check disambiguation answers
        prev_answers = {
            q["question_id"]: q.get("user_answer")
            for q in previous.get("disambiguation_questions", [])
        }
        curr_answers = {
            q["question_id"]: q.get("user_answer")
            for q in current.get("disambiguation_questions", [])
        }
        
        answer_changes = {}
        for qid, answer in curr_answers.items():
            if prev_answers.get(qid) != answer and answer is not None:
                answer_changes[qid] = {
                    "old": prev_answers.get(qid),
                    "new": answer,
                }
        
        if answer_changes:
            diff["answers_changed"] = answer_changes
        
        return diff
    
    async def get_version_history(
        self,
        tenant_id: str,
        document_name: str,
        plan_id: str,
        limit: int = 20,
    ) -> List[PlanVersion]:
        """
        Get version history for a plan.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            plan_id: Plan to get history for
            limit: Maximum versions to return
        
        Returns:
            List of PlanVersion objects, newest first
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.PLAN_VERSION,
            KnowledgeNode.source_reference.like(f"{plan_id}_v%"),
        ).order_by(KnowledgeNode.version.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        versions = []
        for node in nodes:
            try:
                if not node.content:
                    continue
                version_data = node.content.get("version_data")
                if version_data:
                    version = PlanVersion.model_validate(version_data)
                    versions.append(version)
            except Exception as e:
                logger.warning(f"Failed to parse version: {e}")
                continue
        
        return versions
    
    async def get_version(
        self,
        tenant_id: str,
        document_name: str,
        plan_id: str,
        version_number: int,
    ) -> Optional[PlanVersion]:
        """
        Get a specific version of a plan.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            plan_id: Plan ID
            version_number: Version number to retrieve
        
        Returns:
            PlanVersion if found, None otherwise
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        version_id = f"{plan_id}_v{version_number}"
        
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.PLAN_VERSION,
            KnowledgeNode.source_reference == version_id,
        )
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        
        if not node or not node.content:
            return None
        
        try:
            version_data = node.content.get("version_data")
            if version_data:
                return PlanVersion.model_validate(version_data)
        except Exception as e:
            logger.error(f"Failed to get version {version_number}: {e}")
        
        return None
    
    async def rollback_to_version(
        self,
        tenant_id: str,
        document_name: str,
        plan_id: str,
        version_number: int,
    ) -> Optional[QueryPlan]:
        """
        Rollback plan to a previous version.
        
        Creates a new version with the rolled-back state.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            plan_id: Plan to rollback
            version_number: Target version number
        
        Returns:
            Rolled-back QueryPlan, or None if version not found
        """
        # Get target version
        target_version = await self.get_version(
            tenant_id, document_name, plan_id, version_number
        )
        
        if not target_version:
            logger.error(f"Version {version_number} not found for plan {plan_id}")
            return None
        
        # Get current plan for version number
        current_plan = await self.get_plan(tenant_id, document_name, plan_id)
        if not current_plan:
            logger.error(f"Plan {plan_id} not found")
            return None
        
        # Restore from snapshot
        restored_plan = QueryPlan.model_validate(target_version.plan_snapshot)
        
        # Update version and timestamps
        restored_plan.current_version = current_plan.current_version + 1
        restored_plan.updated_at = datetime.now()
        
        # Reset execution state if rolling back from executed state
        if restored_plan.status in [PlanStatus.COMPLETED, PlanStatus.FAILED]:
            restored_plan.status = PlanStatus.CONFIRMED
            restored_plan.execution_started_at = None
            restored_plan.execution_completed_at = None
            restored_plan.current_step = None
            for step in restored_plan.steps:
                from ..core.planning_models import StepStatus
                step.status = StepStatus.PENDING
                step.started_at = None
                step.completed_at = None
                step.execution_result = None
                step.error_message = None
        
        # Save rolled-back plan
        await self.save_plan(
            restored_plan,
            create_version=True,
            change_type="rollback",
            change_description=f"Rolled back to version {version_number}",
        )
        
        logger.info(
            f"Rolled back plan {plan_id} to version {version_number} "
            f"(new version: {restored_plan.current_version})"
        )
        
        return restored_plan
    
    # ==========================================================================
    # Search Operations
    # ==========================================================================
    
    async def search_plans(
        self,
        tenant_id: str,
        document_name: str,
        query: str,
        limit: int = 10,
        status_filter: Optional[List[PlanStatus]] = None,
    ) -> List[QueryPlanSummary]:
        """
        Search plans by text similarity to query.
        
        Args:
            tenant_id: Tenant identifier
            document_name: Document name
            query: Search query
            limit: Maximum results
            status_filter: Optional status filter
        
        Returns:
            List of matching QueryPlanSummary objects
        """
        from app.models.nodes import KnowledgeNode
        from app.models.enums import NodeType
        from sqlalchemy import select
        
        # Get all plans and filter in memory (for simple text matching)
        # In production, this could use PostgreSQL full-text search
        stmt = select(KnowledgeNode).where(
            KnowledgeNode.tenant_id == tenant_id,
            KnowledgeNode.dataset_name == document_name,
            KnowledgeNode.node_type == NodeType.QUERY_PLAN,
        ).order_by(KnowledgeNode.updated_at.desc())
        
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()
        
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        scored_results = []
        for node in nodes:
            try:
                if not node.content:
                    continue
                    
                plan_data = node.content.get("plan_data")
                if not plan_data:
                    continue
                
                plan = QueryPlan.model_validate(plan_data)
                
                # Skip deleted
                if plan.is_deleted:
                    continue
                
                # Apply status filter
                if status_filter and plan.status not in status_filter:
                    continue
                
                # Score based on text matching
                score = 0.0
                text_blob = f"{plan.original_question} {plan.analysis_summary}".lower()
                
                # Exact query match
                if query_lower in text_blob:
                    score += 1.0
                
                # Term matches
                term_matches = sum(1 for term in query_terms if term in text_blob)
                if term_matches > 0:
                    score += 0.5 * (term_matches / len(query_terms))
                
                if score > 0:
                    scored_results.append((plan, score))
                    
            except Exception as e:
                logger.warning(f"Failed to parse plan: {e}")
                continue
        
        # Sort by score
        scored_results.sort(key=lambda x: -x[1])
        
        # Convert to summaries
        summaries = [
            QueryPlanSummary.from_plan(plan)
            for plan, _ in scored_results[:limit]
        ]
        
        return summaries


def create_plan_storage(session: 'AsyncSession') -> PlanStorage:
    """
    Factory function to create a PlanStorage.
    
    Args:
        session: SQLAlchemy async session
        
    Returns:
        Configured PlanStorage instance
    """
    return PlanStorage(session=session)
