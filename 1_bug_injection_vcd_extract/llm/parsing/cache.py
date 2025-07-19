from .history import VerilogChange
from .verilog import Verilog, VerilogPartition
from typing import Iterable
import pickle

class VerilogCache:
    def __init__(self, changes: list[VerilogChange] = [], partition: VerilogPartition = None):
        self.changes = changes
        self.set_regions(partition)
    
    def set_regions(self, partition: VerilogPartition):
        self.regions = [
            {
                "start_line": region.start_line,
                "end_line": region.end_line,
                "description": region.description,
            }
            for region in partition
        ]
    
    def extract_regions(self, full_verilog: Verilog) -> VerilogPartition:
        partition = VerilogPartition(full_verilog)
        for region in self.regions:
            partition.add_region(region["start_line"], region["end_line"], region["description"])
        return partition

    def get_changes_in_region(self, region_idx: int, show_invalid=False) -> list[VerilogChange]:
        region = self.regions[region_idx]
        region_changes = [
            change
            for change in self.changes
            if change.line_idx >= region["start_line"] and
               change.line_idx <= region["end_line"] and
               (show_invalid or change.valid)
        ]
        region_changes = sorted(region_changes, key=lambda change: change.line_idx)
        return region_changes
    
    def get_changes_by_type(self, mutation_class: str, show_invalid=False) -> list[VerilogChange]:
        changes = [
            change
            for change in self.changes
            if change.bug_type == mutation_class and
               (show_invalid or change.valid)
        ]
        changes = sorted(changes, key=lambda change: change.line_idx)
        return changes
    
    def add_changes(self, new_changes: list[VerilogChange]):
        self.changes.extend(new_changes)
    
    def invalidate_last_change(self):
        if not self.changes:
            return
        
        for i in range(len(self.changes)-1, -1, -1):
            if self.changes[i].valid:
                self.changes[i].valid = False
                break
    
def dump_verilog_cache(verilog_cache: VerilogCache, file_path: str):
    with open(file_path, 'wb') as file:
        pickle.dump(verilog_cache, file)

def load_verilog_cache(file_path: str) -> VerilogCache:
    with open(file_path, 'rb') as file:
        verilog_cache = pickle.load(file)
    return verilog_cache
