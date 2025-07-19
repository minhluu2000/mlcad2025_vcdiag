from pydantic import BaseModel
from typing import List

class BugFrequency(BaseModel):
    name: str
    amount: int

class Stats(BaseModel):
    bugStats: List[BugFrequency]
    successes: int
    totalAttempts: int

bug_frequencies = [
    BugFrequency(name="Bug A", amount=10),
    BugFrequency(name="Bug B", amount=5),
]

stats_instance = Stats(bugStats=bug_frequencies, successes=25, totalAttempts=100)

print(stats_instance.model_dump())