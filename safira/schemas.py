from pydantic import BaseModel
from typing import Optional, Dict, Any

class SafiraRequest(BaseModel):
    question: str

class SafiraResponse(BaseModel):
    recognized: bool
    intent: str
    answer: str
    meta: Optional[Dict[str, Any]] = None
