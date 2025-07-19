from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd
from datetime import datetime
import os

@dataclass
class MutationRecord:
    mutation_id: str
    bug_scenario_id: str
    design_id: str
    module_path: str
    mutation_class: str
    line_number: int
    original_line: str
    mutated_line: str
    mutation_applied_successfully: bool
    num_retries: int
    timestamp_first_attempt: datetime
    timestamp_final_success: datetime
    generation_time_ms: float
    validation_time_ms: float
    rollback_time_ms: Optional[float]
    in_roi: bool
    roi_id: Optional[str]
    roi_size_lines: Optional[int]
    validation_passed: bool
    failure_signature: Optional[str]
    signature_class: Optional[str]

class MutationLogger:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.mutations = []
        self.save_to_csv()

    def log_mutation(self, mutation: MutationRecord):
        self.mutations.append(asdict(mutation))

    def to_dataframe(self):
        return pd.DataFrame(self.mutations)

    def save_to_csv(self):
        df = self.to_dataframe()
        print('Saving mutation data')
        df.to_csv(self.log_path, index=False)