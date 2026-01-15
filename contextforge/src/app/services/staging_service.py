from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staging import StagingNode
from app.models.nodes import KnowledgeNode
from app.models.enums import StagingStatus, KnowledgeStatus, Visibility


class StagingService:
    def __init__(self, session: AsyncSession, user_tenant_ids: List[str]):
        self.session = session
        self.user_tenant_ids = user_tenant_ids

    async def list_items(
        self,
        status: Optional[str] = None,
        action: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[StagingNode], int]:
        query = select(StagingNode).where(
            StagingNode.tenant_id.in_(self.user_tenant_ids)
        )
        
        if status:
            query = query.where(StagingNode.status == status)
        if action:
            query = query.where(StagingNode.action == action)
        
        count_query = select(func.count(StagingNode.id)).where(
            StagingNode.tenant_id.in_(self.user_tenant_ids)
        )
        if status:
            count_query = count_query.where(StagingNode.status == status)
        if action:
            count_query = count_query.where(StagingNode.action == action)
        
        total = (await self.session.execute(count_query)).scalar() or 0
        
        query = query.order_by(StagingNode.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        
        return items, total

    async def get_item(self, item_id: int) -> Optional[StagingNode]:
        query = select(StagingNode).where(
            StagingNode.id == item_id,
            StagingNode.tenant_id.in_(self.user_tenant_ids),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def approve_item(
        self,
        item_id: int,
        edits: Optional[Dict[str, Any]] = None,
        reviewed_by: str = "anonymous",
    ) -> Tuple[bool, Optional[int], str]:
        item = await self.get_item(item_id)
        if not item:
            return False, None, "Staging item not found"
        
        if item.status != "pending":
            return False, None, f"Item already {item.status}"
        
        title = edits.get("title", item.title) if edits else item.title
        content = {**item.content, **(edits.get("content", {}) if edits else {})}
        tags = edits.get("tags", item.tags) if edits else item.tags
        
        created_item_id = None
        
        if item.action == "new":
            new_node = KnowledgeNode(
                tenant_id=item.tenant_id,
                node_type=item.node_type,
                title=title,
                content=content,
                tags=tags,
                status=KnowledgeStatus.PUBLISHED,
                visibility=Visibility.INTERNAL,
                created_by=reviewed_by,
            )
            self.session.add(new_node)
            await self.session.flush()
            created_item_id = new_node.id
            
        elif item.action == "merge" and item.target_node_id:
            target_query = select(KnowledgeNode).where(
                KnowledgeNode.id == item.target_node_id,
                KnowledgeNode.is_deleted == False,
            )
            target_result = await self.session.execute(target_query)
            target = target_result.scalar_one_or_none()
            
            if target:
                merged_content = {**target.content, **content}
                target.content = merged_content
                target.tags = list(set(target.tags + tags))
                target.updated_by = reviewed_by
                target.updated_at = datetime.utcnow()
                created_item_id = target.id
                
        elif item.action == "add_variant" and item.target_node_id:
            created_item_id = item.target_node_id
        
        item.status = "approved"
        item.reviewed_by = reviewed_by
        item.reviewed_at = datetime.utcnow()
        
        await self.session.commit()
        
        return True, created_item_id, "Item approved successfully"

    async def reject_item(
        self,
        item_id: int,
        reason: Optional[str] = None,
        reviewed_by: str = "anonymous",
    ) -> Tuple[bool, str]:
        item = await self.get_item(item_id)
        if not item:
            return False, "Staging item not found"
        
        if item.status != "pending":
            return False, f"Item already {item.status}"
        
        item.status = "rejected"
        item.reviewed_by = reviewed_by
        item.reviewed_at = datetime.utcnow()
        item.review_notes = reason
        
        await self.session.commit()
        
        return True, "Item rejected"
