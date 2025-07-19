from __future__ import annotations
from vcd_extract.llm.parsing.history import *

def comment_verilog_line(old_line: str, comment: str):
    if old_line.lstrip().startswith("//"):
        first_comment_idx = old_line.find("//")
        last_comment_idx = old_line.rfind("//")
        if first_comment_idx == last_comment_idx:
            updated_line = old_line + f" // {comment}"
        else:
            updated_line = old_line[:last_comment_idx] + f"// {comment}"
    else:
        inline_comment_idx = old_line.find("//")
        if inline_comment_idx != -1:
            updated_line = old_line[:inline_comment_idx].rstrip() + f" // {comment}"
        else:
            updated_line = old_line.rstrip() + f" // {comment}"
    return updated_line

class Verilog:
    EOF_TOKEN = '{END OF FILE}'

    def __init__(self, 
                 name: str,
                 file: str=None, content: str=None, 
                 start_line: int=None, end_line: int=None,
                 description: str=None,
                 line_encoding: str='[*:]'
    ):
        self.name = name
        self.description = description
        self.line_encoding = line_encoding
        self.history = VerilogHistory()
        if file:
            self.load_from_file(file, start_line, end_line)
        else:
            self.load_from_content(content, start_line, end_line)
    
    def load_from_file(self, file_path: str, start_line, end_line):
        with open(file_path, 'r') as f:
            self.load_from_content(f.read(), start_line, end_line)
    
    def load_from_content(self, content: str, start_line, end_line):
        self.content = content
        self.lines = content.splitlines()
        self.start_line = start_line or 1
        self.end_line = end_line or self.start_line + len(self.lines) - 1
        self.num_lines = len(self.lines)
    
    def __lineate(self, line: str, line_num: int, is_extra=False) -> str:
        line_num_str = f'{line_num} (extra)' if is_extra else str(line_num)
        line = self.line_encoding.replace('*', line_num_str) + ' ' + line
        return line

    def copy(self) -> Verilog:
        return Verilog(name=self.name, content=self.get_content(), 
                       start_line=self.start_line, end_line=self.end_line, 
                       description=self.description, line_encoding=self.line_encoding)

    def slice(self, slice_start: int=None, slice_end: int=None) -> Verilog:
        slice_start = slice_start or self.start_line
        slice_end = slice_end or self.end_line

        slice_lines = self.lines[slice_start - self.start_line : slice_end - self.start_line + 1]
        slice_content = '\n'.join(slice_lines)

        return Verilog(name=self.name, content=slice_content, line_encoding=self.line_encoding,
                       start_line=slice_start, end_line=slice_end)

    def update(self, other: Verilog):
        changes = [
            VerilogChange(
                line_idx=line_num, 
                old_line=self.get_line(line_num), 
                new_line=other.get_line(line_num)
            ) 
            for line_num in range(other.start_line, other.end_line+1)
            if self.get_line(line_num) != other.get_line(line_num)
        ]
        self.apply_batch_change(changes)
    
    def apply_change(self, line_idx: int, new_line: str, bug_type='', description='', comment='') -> VerilogChange:
        if comment:
            new_line = comment_verilog_line(new_line, comment)
        change = VerilogChange(line_idx, self.get_line(line_idx), new_line, bug_type, description, self.name)
        self.apply_batch_change([change])
        return change
    
    def apply_batch_change(self, changes: list[VerilogChange]):
        for change in changes:
            self.set_line(change.line_idx, change.new_line)
            self.history.add_change(change)
    
    def set_line(self, line_idx: int, new_line: str, preserve_whitespace=True):
        if preserve_whitespace:
            old_line = self.get_line(line_idx)
            leading_whitespace = old_line[:len(old_line) - len(old_line.lstrip())]
            new_line = leading_whitespace + new_line.strip()
            
        diff = line_idx - self.start_line
        # if diff < 0 or diff >= len(self.lines):
        #     diff = -1
        
        print(f'Changing line {line_idx} in ({self.start_line}-{self.end_line}) -- diff = {diff}')

        self.lines[diff] = new_line
        self.content = '\n'.join(self.lines)

    def undo(self) -> bool:
        change = self.history.undo()
        if not change:
            return False
        self.set_line(change.line_idx, change.old_line)
        self.content = '\n'.join(self.lines)
        return True

    def redo(self) -> bool:
        change = self.history.redo()
        if not change:
            return False
        self.set_line(change.line_idx, change.new_line)
        self.content = '\n'.join(self.lines)
        return True
    
    def set_description(self, description : str):
        self.description = description

    def get_content(self, lineate=False, extra_lines: int=0, include_eof=False) -> str:
        conditional_eof = f'\n{self.EOF_TOKEN}' if include_eof else ''
        if lineate:
            new_lines = self.lines.copy()
            for i in range(len(new_lines)):
                line_num = self.start_line + i
                is_extra = i < extra_lines or len(new_lines) - i <= extra_lines
                new_lines[i] = self.__lineate(new_lines[i], line_num, is_extra)
            return '\n'.join(new_lines) + conditional_eof
        else:
            return self.content + conditional_eof
    
    def get_line(self, line_idx: int, lineate=False) -> str:
        diff = line_idx - self.start_line
        diff = min(len(self.lines)-1, max(0, diff))
        line = self.lines[diff]
        if lineate:
            return self.__lineate(line, line_idx)
        else:
            return line

class VerilogPartition:
    def __init__(self, verilog: Verilog):
        self.full_verilog = verilog.copy()
        self.regions: list[Verilog] = []

    def add_region(self, start_line: int, end_line: int, description: str = ''):
        region = self.full_verilog.slice(start_line, end_line)
        region.set_description(description)
        self.regions.append(region)

    def __getitem__(self, idx: int) -> Verilog:
        return self.regions[idx]

    def __setitem__(self, idx: int, value: Verilog):
        assert isinstance(value, Verilog), "Assigned value must be a Verilog instance."
        self.regions[idx] = value

    def __delitem__(self, idx: int):
        del self.regions[idx]

    def __len__(self) -> int:
        return len(self.regions)

    def __iter__(self):
        return iter(self.regions)

    def get_full_verilog(self) -> Verilog:
        for region in self.regions:
            self.full_verilog.update(region)
        return self.full_verilog
    
    def get_full_verilog_content(self) -> str:
        return self.get_full_verilog().get_content()
    
    def get_regions(self) -> list[Verilog]:
        return self.regions

    def clear_regions(self):
        self.regions.clear()
