from enum import Enum
from pydantic import BaseModel

class HealthCheckResponse(Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"

class Query(BaseModel):
    query: str
    streaming: bool