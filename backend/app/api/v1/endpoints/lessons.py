from fastapi import APIRouter, Depends

from app.api.deps import AuthUser, get_current_user
from app.schemas.lesson import LessonProgressUpdate
from app.services.supabase_service import SupabaseService

router = APIRouter()


@router.get("/progress")
async def my_lesson_progress(user: AuthUser = Depends(get_current_user)) -> dict:
    service = SupabaseService()
    rows = await service.select(
        "user_lesson_progress",
        query=f"user_id=eq.{user.id}&select=user_id,lesson_id,percent_watched,quiz_score,completed_at,updated_at",
        use_service_key=True,
    )
    return {"success": True, "data": rows}


@router.post("/progress")
async def upsert_lesson_progress(payload: LessonProgressUpdate, user: AuthUser = Depends(get_current_user)) -> dict:
    service = SupabaseService()
    row = await service.upsert(
        "user_lesson_progress",
        payload={
            "user_id": user.id,
            "lesson_id": str(payload.lesson_id),
            "percent_watched": payload.percent_watched,
            "quiz_score": payload.quiz_score,
            "completed_at": payload.completed_at,
        },
        on_conflict="user_id,lesson_id",
        use_service_key=True,
    )
    return {"success": True, "data": row}
