from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.settings import SettingsResponse, SettingsUpdateRequest
from app.services.settings_service import SettingsService


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(session: AsyncSession = Depends(get_session)):
    service = SettingsService(session)
    return await service.get_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    service = SettingsService(session)
    return await service.update_settings(
        search=data.search,
        pipeline=data.pipeline,
        maintenance=data.maintenance,
    )
