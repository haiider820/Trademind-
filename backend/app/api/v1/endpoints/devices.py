from fastapi import APIRouter, Depends

from app.api.deps import AuthUser, get_current_user
from app.schemas.device import DeviceRegisterRequest
from app.services.supabase_service import SupabaseService

router = APIRouter()


@router.post("/register")
async def register_device(
    payload: DeviceRegisterRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = SupabaseService()
    row = await service.upsert(
        "device_tokens",
        payload={
            "user_id": user.id,
            "token": payload.token,
            "platform": payload.platform,
            "is_active": True,
        },
        on_conflict="token",
        use_service_key=True,
    )
    return {"success": True, "data": row}
