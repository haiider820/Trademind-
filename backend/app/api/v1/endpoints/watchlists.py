from fastapi import APIRouter, Depends

from app.api.deps import AuthUser, get_current_user
from app.services.supabase_service import SupabaseService

router = APIRouter()


@router.get("")
async def list_watchlist(user: AuthUser = Depends(get_current_user)) -> dict:
    service = SupabaseService()
    rows = await service.select(
        "watchlists",
        query=f"user_id=eq.{user.id}&select=id,symbol,sort_order,created_at&order=sort_order.asc",
        use_service_key=True,
    )
    return {"success": True, "data": rows}

