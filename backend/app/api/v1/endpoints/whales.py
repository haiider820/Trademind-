from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthUser, get_current_user
from app.services.supabase_service import SupabaseService

router = APIRouter()


@router.get("")
async def list_whales(
    limit: int = Query(default=20, ge=1, le=100),
    _: AuthUser = Depends(get_current_user),
) -> dict:
    service = SupabaseService()
    rows = await service.select(
        "whale_alerts",
        query=f"select=id,coin,amount,wallet_type,action,created_at&order=created_at.desc&limit={limit}",
        use_service_key=True,
    )
    return {"success": True, "data": rows}
