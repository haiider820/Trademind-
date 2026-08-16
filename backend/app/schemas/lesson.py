from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LessonProgressUpdate(BaseModel):
    lesson_id: UUID
    percent_watched: int
    quiz_score: int | None = None
    completed_at: datetime | None = None
