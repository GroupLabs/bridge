from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Optional

class Status(Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"

class Health():
    def __init__(self, status=Status.DEGRADED, ENV=None):
        self.STATUS = status
        self.ENV = ENV
    
    def __repr__(self):
        return f'{self.STATUS}, {self.ENV}'
    
class Query(BaseModel):
    query: str
    index: str
    use_llm: Optional[bool] = False

class Load(BaseModel):
    filepath: str
    typehint: Optional[str] = "unknown"

#for chat with GPT-4:
class ChatRequest(BaseModel):
    message: str

class InferenceRequest(BaseModel):
    model: str
    modelVersion: str
