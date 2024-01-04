from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Optional


class Query(BaseModel):
    query: str
    model: Optional[str] = ""
