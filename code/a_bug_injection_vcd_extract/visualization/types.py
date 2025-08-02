from pydantic import BaseModel
from typing import Literal, Optional, List

class Loadable(BaseModel):
    loadingText: str

class Stage(BaseModel):
    name: str
    status: Literal['notStarted', 'inProgress', 'completed']
    justification: Optional[str] = None

class VerilogLine(BaseModel):
    lineNumber: int
    before: str
    after: Optional[str] = None
    justification: Optional[str] = None

class BugFrequency(BaseModel):
    name: str
    amount: int

class Stats(BaseModel):
    bugStats: List[BugFrequency]
    successes: int
    totalAttempts: int

class Bug(BaseModel):
    name: str
    description: str

class Region(BaseModel):
    name: str
    description: Optional[str] = None
    totalLines: int
    buggyLines: int

class EvaluationResult(BaseModel):
    status: Literal['success', 'failure']
    error: Optional[str] = None