from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    id: str
    title: str
    sentiment: str
    category: str
    source: str
    published_at: datetime
