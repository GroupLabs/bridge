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

class ChatRequest(BaseModel):
    id: int
    message: str

class Connection(BaseModel):
    database: str
    connectionString: Optional[str] = None
    host: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
