from datetime import datetime
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.settings import (
    SettingsResponse,
    SearchSettings,
    PipelineSettings,
    MaintenanceSettings,
)
from app.core.config import settings as app_settings


DEFAULTS = {
    "search": SearchSettings(
        bm25_weight=app_settings.SEARCH_BM25_WEIGHT,
        vector_weight=app_settings.SEARCH_VECTOR_WEIGHT,
        default_limit=app_settings.SEARCH_DEFAULT_LIMIT,
    ),
    "pipeline": PipelineSettings(
        similarity_skip_threshold=app_settings.PIPELINE_SIMILARITY_SKIP_THRESHOLD,
        similarity_variant_threshold=app_settings.PIPELINE_SIMILARITY_VARIANT_THRESHOLD,
        similarity_merge_threshold=app_settings.PIPELINE_SIMILARITY_MERGE_THRESHOLD,
        confidence_threshold=app_settings.PIPELINE_CONFIDENCE_THRESHOLD,
        min_body_length=app_settings.PIPELINE_MIN_BODY_LENGTH,
        min_closure_notes_length=app_settings.PIPELINE_MIN_CLOSURE_NOTES_LENGTH,
    ),
    "maintenance": MaintenanceSettings(
        version_retention_days=app_settings.VERSION_RETENTION_DAYS,
        hit_retention_days=app_settings.HIT_RETENTION_DAYS,
    ),
}


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_settings(self) -> SettingsResponse:
        result = await self.session.execute(
            text("SELECT category, settings FROM agent.system_settings")
        )
        rows = {row.category: row.settings for row in result.fetchall()}

        return SettingsResponse(
            search=SearchSettings(**rows["search"]) if "search" in rows else DEFAULTS["search"],
            pipeline=PipelineSettings(**rows["pipeline"]) if "pipeline" in rows else DEFAULTS["pipeline"],
            maintenance=MaintenanceSettings(**rows["maintenance"]) if "maintenance" in rows else DEFAULTS["maintenance"],
        )

    async def update_settings(
        self,
        search: Optional[SearchSettings] = None,
        pipeline: Optional[PipelineSettings] = None,
        maintenance: Optional[MaintenanceSettings] = None,
    ) -> SettingsResponse:
        updates = [
            ("search", search),
            ("pipeline", pipeline),
            ("maintenance", maintenance),
        ]

        for category, data in updates:
            if data is not None:
                await self.session.execute(
                    text("""
                        INSERT INTO agent.system_settings (category, settings, updated_at)
                        VALUES (:category, :settings, :updated_at)
                        ON CONFLICT (category) DO UPDATE SET
                            settings = EXCLUDED.settings,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {
                        "category": category,
                        "settings": data.model_dump_json(),
                        "updated_at": datetime.utcnow(),
                    },
                )

        await self.session.commit()
        return await self.get_settings()
