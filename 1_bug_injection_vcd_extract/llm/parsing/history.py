class VerilogChange:
    def __init__(self, line_idx: int, old_line: str, new_line: str, bug_type='', description='', filename='', valid=True):
        self.line_idx = line_idx
        self.old_line = old_line
        self.new_line = new_line
        self.bug_type = bug_type
        self.description = description
        self.filename = filename
        self.valid = valid
    
    def stringify(self) -> str:
        return f'{self.bug_type} on line {self.line_idx}: {self.description}\n' + \
               f'\t- {self.old_line}\n' + \
               f'\t+ {self.new_line}' + \
               (f'\n\tFAILED' if not self.valid else '')
        
class VerilogHistory:
    def __init__(self):
        self.undo_stack : list[VerilogChange] = []
        self.redo_stack : list[VerilogChange] = []

    def add_change(self, change: VerilogChange):
        self.undo_stack.append(change)
        self.redo_stack.clear()
    
    def get_changes(self) -> list[VerilogChange]:
        return self.undo_stack

    def stringify(self) -> list[str]:
        return [change.stringify() for change in self.undo_stack]

    def undo(self) -> VerilogChange:
        if not self.undo_stack:
            return None
        change = self.undo_stack.pop()
        self.redo_stack.append(change)
        return change
    
    def redo(self) -> VerilogChange:
        if not self.redo_stack:
            return None
        change = self.redo_stack.pop()
        self.undo_stack.append(change)
        return change