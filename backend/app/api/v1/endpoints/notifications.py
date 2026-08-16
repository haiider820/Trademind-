from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthUser, get_current_user
from app.services.supabase_service import SupabaseService

router = APIRouter()


@router.get("")
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    service = SupabaseService()
    query = f"user_id=eq.{user.id}&select=id,title,body,type,data,is_read,created_at&order=created_at.desc&limit={limit}"
    if unread_only:
        query = f"{query}&is_read=eq.false"
    rows = await service.select("notifications", query=query, use_service_key=True)
    return {"success": True, "data": rows}


@router.patch("/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    service = SupabaseService()
    row = await service.update(
        "notifications",
        payload={"is_read": True},
        query=f"id=eq.{notification_id}&user_id=eq.{user.id}",
        use_service_key=True,
    )
    return {"success": True, "data": row}
