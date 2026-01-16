from typing import List, Optional, Dict, Any, Set, Tuple
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.models.enums import NodeType, EdgeType
from app.schemas.llm_context import (
    LLMContextRequest,
    LLMContextResponse,
    LLMContextStats,
    KnowledgeContext,
    KnowledgeGroup,
    FAQItem,
    PlaybookItem,
    PermissionItem,
    ConceptItem,
    SchemaContext,
    ConceptFieldGroup,
    FieldItem,
    ExampleItem,
)
from app.services.node_service import NodeService
from app.services.graph_service import GraphService
from app.clients.embedding_client import EmbeddingClient
from app.utils.schema import sql as schema_sql


class LLMContextService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient,
    ):
        self.session = session
        self.embedding_client = embedding_client
        self.node_service = NodeService(session, embedding_client)
        self.graph_service = GraphService(session)

    async def get_llm_context(
        self,
        request: LLMContextRequest,
    ) -> LLMContextResponse:
        knowledge_context: Optional[KnowledgeContext] = None
        schema_context: Optional[SchemaContext] = None
        stats = LLMContextStats()
        debug_info: Dict[str, Any] = {"entry_point_ids": [], "expanded_ids": []}

        if request.include_knowledge:
            knowledge_context, k_stats, k_debug = await self._get_knowledge_context(request)
            stats.faqs = k_stats.get("faqs", 0)
            stats.playbooks = k_stats.get("playbooks", 0)
            stats.permissions = k_stats.get("permissions", 0)
            stats.concepts = k_stats.get("concepts", 0)
            stats.entry_points_found += k_stats.get("entry_points", 0)
            stats.nodes_expanded += k_stats.get("expanded", 0)
            stats.max_depth_reached = max(stats.max_depth_reached, k_stats.get("max_depth", 0))
            debug_info["knowledge"] = k_debug

        if request.include_schema:
            schema_context, s_stats, s_debug = await self._get_schema_context(request)
            stats.schema_fields = s_stats.get("fields", 0)
            stats.schema_concepts = s_stats.get("concepts", 0)
            stats.examples = s_stats.get("examples", 0)
            stats.entry_points_found += s_stats.get("entry_points", 0)
            stats.nodes_expanded += s_stats.get("expanded", 0)
            stats.max_depth_reached = max(stats.max_depth_reached, s_stats.get("max_depth", 0))
            debug_info["schema"] = s_debug

        formatted_context = self._format_combined_context(knowledge_context, schema_context)

        return LLMContextResponse(
            context=formatted_context,
            knowledge=knowledge_context,
            schema_context=schema_context,
            stats=stats,
            debug=debug_info if debug_info.get("knowledge") or debug_info.get("schema") else None,
        )

    async def _get_knowledge_context(
        self,
        request: LLMContextRequest,
    ) -> Tuple[KnowledgeContext, Dict[str, int], Dict[str, Any]]:
        node_types = request.knowledge_types
        if node_types is None:
            node_types = [
                NodeType.FAQ,
                NodeType.PLAYBOOK,
                NodeType.PERMISSION_RULE,
                NodeType.CONCEPT,
            ]

        bm25_weight, vector_weight = self._resolve_search_weights(request.search_method)

        search_results = await self.node_service.hybrid_search(
            query_text=request.query,
            user_tenant_ids=request.tenant_ids,
            node_types=node_types,
            tags=request.tags,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            limit=request.max_knowledge_items,
        )

        entry_ids = [r.node.id for r in search_results]
        expanded_nodes = []
        max_depth = 0

        if request.expand_graph and search_results:
            expanded_nodes, max_depth = await self._expand_knowledge_graph(
                entry_ids=entry_ids,
                tenant_ids=request.tenant_ids,
                max_depth=request.max_depth,
                node_types=node_types,
                limit=request.max_knowledge_items,
            )

        all_nodes = []
        for r in search_results:
            all_nodes.append({
                "id": r.node.id,
                "node_type": r.node.node_type,
                "title": r.node.title,
                "summary": r.node.summary,
                "content": r.node.content,
                "tags": r.node.tags or [],
                "score": r.rrf_score,
                "is_entry_point": True,
            })

        seen_ids = set(entry_ids)
        for node in expanded_nodes:
            if node["id"] not in seen_ids:
                all_nodes.append(node)
                seen_ids.add(node["id"])

        groups = self._group_knowledge_by_topic(all_nodes)
        knowledge_context = KnowledgeContext(
            groups=groups,
            formatted=self._format_knowledge_context(groups),
            total_faqs=sum(len(g.faqs) for g in groups),
            total_playbooks=sum(len(g.playbooks) for g in groups),
            total_permissions=sum(len(g.permissions) for g in groups),
            total_concepts=sum(len(g.concepts) for g in groups),
        )

        stats = {
            "faqs": knowledge_context.total_faqs,
            "playbooks": knowledge_context.total_playbooks,
            "permissions": knowledge_context.total_permissions,
            "concepts": knowledge_context.total_concepts,
            "entry_points": len(entry_ids),
            "expanded": len(expanded_nodes),
            "max_depth": max_depth,
        }

        debug = {
            "entry_point_ids": entry_ids,
            "expanded_ids": [n["id"] for n in expanded_nodes],
        }

        return knowledge_context, stats, debug

    async def _expand_knowledge_graph(
        self,
        entry_ids: List[int],
        tenant_ids: List[str],
        max_depth: int,
        node_types: List[NodeType],
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        await self.graph_service.load_graph(tenant_ids)

        visited: Set[int] = set(entry_ids)
        expanded_nodes: List[Dict[str, Any]] = []
        max_depth_reached = 0
        type_values = [t.value for t in node_types]
        current_level = set(entry_ids)

        for depth in range(1, max_depth + 1):
            if len(expanded_nodes) >= limit:
                break

            next_level: Set[int] = set()

            for node_id in current_level:
                if node_id not in self.graph_service.graph:
                    continue

                successors = set(self.graph_service.graph.successors(node_id))
                predecessors = set(self.graph_service.graph.predecessors(node_id))
                neighbors = (successors | predecessors) - visited

                for neighbor_id in neighbors:
                    if len(expanded_nodes) >= limit:
                        break

                    node_data = self.graph_service.graph.nodes.get(neighbor_id, {})
                    neighbor_type = node_data.get("node_type")

                    if neighbor_type not in type_values:
                        continue

                    node_detail = await self._get_node_detail(neighbor_id, tenant_ids)
                    if node_detail:
                        node_detail["score"] = 1.0 / (depth + 1)
                        node_detail["is_entry_point"] = False
                        expanded_nodes.append(node_detail)
                        visited.add(neighbor_id)
                        next_level.add(neighbor_id)
                        max_depth_reached = max(max_depth_reached, depth)

            current_level = next_level
            if not current_level:
                break

        return expanded_nodes, max_depth_reached

    def _group_knowledge_by_topic(
        self,
        nodes: List[Dict[str, Any]],
    ) -> List[KnowledgeGroup]:
        tag_to_nodes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for node in nodes:
            tags = node.get("tags", [])
            if tags:
                primary_tag = tags[0]
                tag_to_nodes[primary_tag].append(node)
            else:
                tag_to_nodes["General"].append(node)

        groups = []
        for topic, topic_nodes in sorted(tag_to_nodes.items(), key=lambda x: -max((n.get("score", 0) for n in x[1]), default=0)):
            faqs = []
            playbooks = []
            permissions = []
            concepts = []
            max_score = 0.0

            for node in topic_nodes:
                score = node.get("score", 0.0)
                max_score = max(max_score, score)
                node_type = node.get("node_type")
                content = node.get("content", {})

                if node_type == NodeType.FAQ.value or node_type == NodeType.FAQ:
                    faqs.append(FAQItem(
                        id=node["id"],
                        question=node["title"],
                        answer=content.get("answer", ""),
                        tags=node.get("tags", []),
                        score=score,
                    ))
                elif node_type == NodeType.PLAYBOOK.value or node_type == NodeType.PLAYBOOK:
                    playbooks.append(PlaybookItem(
                        id=node["id"],
                        title=node["title"],
                        domain=content.get("domain"),
                        summary=node.get("summary"),
                        content=content.get("content", ""),
                        tags=node.get("tags", []),
                        score=score,
                    ))
                elif node_type == NodeType.PERMISSION_RULE.value or node_type == NodeType.PERMISSION_RULE:
                    permissions.append(PermissionItem(
                        id=node["id"],
                        title=node["title"],
                        feature=content.get("feature"),
                        description=content.get("description", ""),
                        permissions=content.get("permissions", []),
                        roles=content.get("roles", []),
                        conditions=content.get("context"),
                        tags=node.get("tags", []),
                        score=score,
                    ))
                elif node_type == NodeType.CONCEPT.value or node_type == NodeType.CONCEPT:
                    concepts.append(ConceptItem(
                        id=node["id"],
                        name=node["title"],
                        description=content.get("description", ""),
                        aliases=content.get("aliases", []),
                        related_questions=content.get("key_questions", []),
                        tags=node.get("tags", []),
                        score=score,
                    ))

            if faqs or playbooks or permissions or concepts:
                groups.append(KnowledgeGroup(
                    topic=topic,
                    relevance_score=max_score,
                    faqs=sorted(faqs, key=lambda x: -x.score),
                    playbooks=sorted(playbooks, key=lambda x: -x.score),
                    permissions=sorted(permissions, key=lambda x: -x.score),
                    concepts=sorted(concepts, key=lambda x: -x.score),
                ))

        return sorted(groups, key=lambda g: -g.relevance_score)

    async def _get_schema_context(
        self,
        request: LLMContextRequest,
    ) -> Tuple[SchemaContext, Dict[str, int], Dict[str, Any]]:
        node_types = [NodeType.SCHEMA_INDEX, NodeType.SCHEMA_FIELD]

        bm25_weight, vector_weight = self._resolve_search_weights(request.search_method)

        search_results = await self.node_service.hybrid_search(
            query_text=request.query,
            user_tenant_ids=request.tenant_ids,
            node_types=node_types,
            tags=request.tags,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            limit=request.max_schema_fields * 2,
        )

        if request.dataset_names:
            search_results = [
                r for r in search_results
                if r.node.dataset_name in request.dataset_names
            ][:request.max_schema_fields]

        entry_ids = [r.node.id for r in search_results]
        all_fields: List[Dict[str, Any]] = []
        dataset_name = None
        source_type = None

        for r in search_results:
            content = r.node.content or {}
            if r.node.node_type == NodeType.SCHEMA_INDEX:
                dataset_name = dataset_name or r.node.dataset_name
                source_type = source_type or content.get("source_type")
            elif r.node.node_type == NodeType.SCHEMA_FIELD:
                all_fields.append({
                    "id": r.node.id,
                    "path": r.node.title,
                    "data_type": content.get("data_type", content.get("es_type", "unknown")),
                    "description": content.get("description", ""),
                    "business_meaning": content.get("business_meaning") or content.get("maps_to"),
                    "allowed_values": content.get("allowed_values"),
                    "value_meanings": content.get("value_synonyms"),
                    "is_nullable": content.get("nullable", True),
                    "is_primary_key": content.get("is_primary_key", False),
                    "is_foreign_key": content.get("is_foreign_key", False),
                    "references": content.get("references"),
                    "score": r.rrf_score,
                    "is_direct_match": True,
                    "concept": content.get("maps_to") or content.get("concept"),
                    "dataset_name": r.node.dataset_name,
                })

        if request.expand_graph and entry_ids:
            expanded_fields, _ = await self._expand_schema_graph(
                entry_ids=entry_ids,
                tenant_ids=request.tenant_ids,
                max_depth=request.max_depth,
                limit=request.max_schema_fields - len(all_fields),
            )
            seen_ids = set(f["id"] for f in all_fields)
            for field in expanded_fields:
                if field["id"] not in seen_ids:
                    all_fields.append(field)
                    seen_ids.add(field["id"])

        examples = await self._get_related_examples(
            tenant_ids=request.tenant_ids,
            dataset_names=request.dataset_names or ([dataset_name] if dataset_name else None),
            query=request.query,
            limit=request.max_examples,
        )

        concept_groups = self._group_fields_by_concept(all_fields)
        schema_context = SchemaContext(
            dataset_name=dataset_name,
            source_type=source_type,
            concept_groups=concept_groups,
            examples=examples,
            formatted=self._format_schema_context(concept_groups, examples),
            total_fields=len(all_fields),
            total_concepts=len(concept_groups),
            total_examples=len(examples),
        )

        stats = {
            "fields": len(all_fields),
            "concepts": len(concept_groups),
            "examples": len(examples),
            "entry_points": len(entry_ids),
            "expanded": len(all_fields) - len(entry_ids),
            "max_depth": request.max_depth if request.expand_graph else 0,
        }

        debug = {
            "entry_point_ids": entry_ids,
            "dataset_name": dataset_name,
            "source_type": source_type,
        }

        return schema_context, stats, debug

    async def _expand_schema_graph(
        self,
        entry_ids: List[int],
        tenant_ids: List[str],
        max_depth: int,
        limit: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        await self.graph_service.load_graph(tenant_ids)

        visited: Set[int] = set(entry_ids)
        expanded_fields: List[Dict[str, Any]] = []
        max_depth_reached = 0
        current_level = set(entry_ids)

        for depth in range(1, max_depth + 1):
            if len(expanded_fields) >= limit:
                break

            next_level: Set[int] = set()

            for node_id in current_level:
                if node_id not in self.graph_service.graph:
                    continue

                successors = set(self.graph_service.graph.successors(node_id))
                predecessors = set(self.graph_service.graph.predecessors(node_id))
                neighbors = (successors | predecessors) - visited

                for neighbor_id in neighbors:
                    if len(expanded_fields) >= limit:
                        break

                    node_data = self.graph_service.graph.nodes.get(neighbor_id, {})
                    neighbor_type = node_data.get("node_type")

                    if neighbor_type != NodeType.SCHEMA_FIELD.value:
                        continue

                    node_detail = await self._get_node_detail(neighbor_id, tenant_ids)
                    if node_detail:
                        content = node_detail.get("content", {})
                        expanded_fields.append({
                            "id": node_detail["id"],
                            "path": node_detail["title"],
                            "data_type": content.get("data_type", content.get("es_type", "unknown")),
                            "description": content.get("description", ""),
                            "business_meaning": content.get("business_meaning") or content.get("maps_to"),
                            "allowed_values": content.get("allowed_values"),
                            "value_meanings": content.get("value_synonyms"),
                            "is_nullable": content.get("nullable", True),
                            "is_primary_key": content.get("is_primary_key", False),
                            "is_foreign_key": content.get("is_foreign_key", False),
                            "references": content.get("references"),
                            "score": 1.0 / (depth + 1),
                            "is_direct_match": False,
                            "concept": content.get("maps_to") or content.get("concept"),
                            "dataset_name": node_detail.get("dataset_name"),
                        })
                        visited.add(neighbor_id)
                        next_level.add(neighbor_id)
                        max_depth_reached = max(max_depth_reached, depth)

            current_level = next_level
            if not current_level:
                break

        return expanded_fields, max_depth_reached

    def _group_fields_by_concept(
        self,
        fields: List[Dict[str, Any]],
    ) -> List[ConceptFieldGroup]:
        concept_to_fields: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for field in fields:
            concept = field.get("concept") or "Other"
            concept_to_fields[concept].append(field)

        groups = []
        for concept, concept_fields in concept_to_fields.items():
            max_score = max((f.get("score", 0) for f in concept_fields), default=0.0)
            has_match = any(f.get("is_direct_match", False) for f in concept_fields)

            field_items = [
                FieldItem(
                    path=f["path"],
                    data_type=f["data_type"],
                    description=f["description"],
                    business_meaning=f.get("business_meaning"),
                    allowed_values=f.get("allowed_values"),
                    value_meanings=f.get("value_meanings"),
                    is_nullable=f.get("is_nullable", True),
                    is_primary_key=f.get("is_primary_key", False),
                    is_foreign_key=f.get("is_foreign_key", False),
                    references=f.get("references"),
                    score=f.get("score", 0.0),
                    is_direct_match=f.get("is_direct_match", False),
                )
                for f in sorted(concept_fields, key=lambda x: -x.get("score", 0))
            ]

            groups.append(ConceptFieldGroup(
                concept=concept,
                relevance_score=max_score,
                is_matched=has_match,
                fields=field_items,
            ))

        return sorted(groups, key=lambda g: (-int(g.is_matched), -g.relevance_score))

    async def _get_related_examples(
        self,
        tenant_ids: List[str],
        dataset_names: Optional[List[str]],
        query: str,
        limit: int,
    ) -> List[ExampleItem]:
        if limit <= 0:
            return []

        dataset_filter = ""
        params: Dict[str, Any] = {"tenant_ids": tenant_ids, "limit": limit, "query": query}

        if dataset_names:
            dataset_filter = "AND n.dataset_name = ANY(:dataset_names)"
            params["dataset_names"] = dataset_names

        result = await self.session.execute(
            text(schema_sql(f"""
                SELECT n.id, n.title, n.content
                FROM {{schema}}.knowledge_nodes n
                WHERE n.node_type = 'example'
                  AND n.tenant_id = ANY(:tenant_ids)
                  AND n.is_deleted = FALSE
                  AND n.status = 'published'
                  {dataset_filter}
                ORDER BY n.created_at DESC
                LIMIT :limit
            """)),
            params,
        )

        examples = []
        for row in result.fetchall():
            content = row.content or {}
            examples.append(ExampleItem(
                question=row.title or content.get("question", ""),
                query=content.get("query", ""),
                query_type=content.get("query_type", "sql"),
                explanation=content.get("explanation"),
                verified=content.get("verified", False),
                relevance_score=0.8,
            ))

        return examples

    async def _get_node_detail(
        self,
        node_id: int,
        tenant_ids: List[str],
    ) -> Optional[Dict[str, Any]]:
        result = await self.session.execute(
            text(schema_sql("""
                SELECT id, tenant_id, node_type, title, summary, content, tags, dataset_name
                FROM {schema}.knowledge_nodes
                WHERE id = :node_id 
                  AND tenant_id = ANY(:tenant_ids)
                  AND is_deleted = FALSE
                  AND status = 'published'
            """)),
            {"node_id": node_id, "tenant_ids": tenant_ids}
        )
        row = result.fetchone()
        if not row:
            return None

        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "node_type": row.node_type,
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "tags": row.tags or [],
            "dataset_name": row.dataset_name,
        }

    def _resolve_search_weights(self, search_method: str) -> Tuple[float, float]:
        if search_method == "bm25":
            return 1.0, 0.0
        elif search_method == "vector":
            return 0.0, 1.0
        return 0.4, 0.6

    def _format_knowledge_context(self, groups: List[KnowledgeGroup]) -> str:
        if not groups:
            return "No relevant knowledge found."

        lines = []

        for group in groups:
            lines.append(f"## {group.topic}")
            lines.append("")

            if group.faqs:
                lines.append("### FAQs")
                for faq in group.faqs:
                    lines.append(f"**Q: {faq.question}**")
                    lines.append(f"A: {faq.answer}")
                    lines.append("")

            if group.playbooks:
                lines.append("### Playbooks")
                for pb in group.playbooks:
                    lines.append(f"**{pb.title}**")
                    if pb.domain:
                        lines.append(f"Domain: {pb.domain}")
                    if pb.summary:
                        lines.append(f"Summary: {pb.summary}")
                    lines.append(pb.content)
                    lines.append("")

            if group.permissions:
                lines.append("### Permissions")
                for perm in group.permissions:
                    lines.append(f"**{perm.title}**")
                    if perm.feature:
                        lines.append(f"Feature: {perm.feature}")
                    lines.append(f"Description: {perm.description}")
                    if perm.roles:
                        lines.append(f"Roles: {', '.join(perm.roles)}")
                    if perm.permissions:
                        lines.append(f"Permissions: {', '.join(perm.permissions)}")
                    if perm.conditions:
                        lines.append(f"Conditions: {perm.conditions}")
                    lines.append("")

            if group.concepts:
                lines.append("### Concepts")
                for concept in group.concepts:
                    lines.append(f"**{concept.name}**")
                    lines.append(concept.description)
                    if concept.aliases:
                        lines.append(f"Also known as: {', '.join(concept.aliases)}")
                    lines.append("")

        return "\n".join(lines)

    def _format_schema_context(
        self,
        concept_groups: List[ConceptFieldGroup],
        examples: List[ExampleItem],
    ) -> str:
        if not concept_groups and not examples:
            return "No relevant schema information found."

        lines = ["## Schema Fields", ""]

        for group in concept_groups:
            match_marker = " [MATCHED]" if group.is_matched else ""
            lines.append(f"### [{group.concept}]{match_marker}")
            lines.append("")

            for field in group.fields:
                match_marker = " *" if field.is_direct_match else ""
                lines.append(f"- **{field.path}** ({field.data_type}){match_marker}")

                if field.description:
                    lines.append(f"  {field.description}")

                if field.business_meaning:
                    lines.append(f"  Business meaning: {field.business_meaning}")

                if field.allowed_values:
                    values_str = ", ".join(field.allowed_values[:5])
                    if len(field.allowed_values) > 5:
                        values_str += f" (+{len(field.allowed_values) - 5} more)"
                    lines.append(f"  Values: {values_str}")

                if field.value_meanings:
                    meanings = [f"{k}={v}" for k, v in list(field.value_meanings.items())[:5]]
                    lines.append(f"  Value meanings: {', '.join(meanings)}")

                if field.references:
                    lines.append(f"  References: {field.references}")

            lines.append("")

        if examples:
            lines.append("## Examples")
            lines.append("")

            for i, ex in enumerate(examples, 1):
                verified_marker = " [verified]" if ex.verified else ""
                lines.append(f"**{i}. {ex.question}**{verified_marker}")
                lines.append(f"```{ex.query_type}")
                lines.append(ex.query)
                lines.append("```")
                if ex.explanation:
                    lines.append(f"Explanation: {ex.explanation}")
                lines.append("")

        return "\n".join(lines)

    def _format_combined_context(
        self,
        knowledge: Optional[KnowledgeContext],
        schema: Optional[SchemaContext],
    ) -> str:
        parts = []

        if knowledge and knowledge.formatted:
            parts.append("# Knowledge Context")
            parts.append("")
            parts.append(knowledge.formatted)

        if schema and schema.formatted:
            if parts:
                parts.append("")
                parts.append("---")
                parts.append("")
            parts.append("# Schema Context")
            parts.append("")
            parts.append(schema.formatted)

        if not parts:
            return "No relevant context found."

        return "\n".join(parts)
