from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str
    type: Literal['FOLDER', 'FILE']
    url: str = Field(default=None, min_length=1, max_length=255)
    parentId: str | None = None
    size: int = Field(default=None, gt=0)
    

class CreateSchema(BaseModel):
    items: list[Item]
    updateDate: datetime = Field(default_factory=lambda: datetime.utcnow().isoformat(sep='T', timespec='seconds')+"Z")

    class Config:
        schema_extra = {
            "example": {
                "items": [{"id": "Пример_1_1", "type": "FOLDER"}],
                "updateDate": "2022-05-28T21:12:01.000Z"
            }
        }

