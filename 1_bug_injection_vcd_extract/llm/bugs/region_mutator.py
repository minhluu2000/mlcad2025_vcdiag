from vcd_extract.llm.models import LLMModel
from vcd_extract.llm.parsing.encoding import SimpleEncoder
from vcd_extract.llm.parsing.verilog import Verilog
from vcd_extract.llm.parsing.history import VerilogChange
from vcd_extract.llm.parsing.cache import VerilogCache
from vcd_extract.visualization.server import PipelineWebSocket
import vcd_extract.visualization.types as wstypes
from vcd_extract.evaluation import log_llm
from .mutation import Mutation, MutationList
from pydantic import BaseModel
from typing import Union
import os.path

class MutationSelection(BaseModel):
    rollback: bool
    justification: str
    line: int
    mutation: str

class LineMutation(BaseModel):
    justification: str
    mutated: str
    summary: str

def even_subset(lst, k):
    if k <= 0:
        return []
    if k >= len(lst):
        return lst[:]

    n = len(lst)
    indices = [round(i * (n - 1) / (k - 1)) for i in range(k)]
    return [lst[i] for i in indices]

class RegionMutator:
    def __init__(self, 
                 llm_model : LLMModel, 
                 prompt_dir : str, 
                 allowed_mutations : MutationList, 
                 debug=False):
        super().__init__()
        self.llm_model = llm_model
        self.debug = debug
        self.allowed_mutations = allowed_mutations
        self.prompt_dir = prompt_dir
        self.bug_num = 0
        self.initialize(prompt_dir)
    
    def debug_log(self, *args):
        if self.debug:
            print(*args)

    def initialize(self, prompt_dir : str):
        selection_prompt_file = os.path.join(prompt_dir, 'insertion', 'mutation_selection_prompt.txt')
        insertion_prompt_file = os.path.join(prompt_dir, 'insertion', 'mutation_insertion_prompt.txt')
        insertion_dep_prompt_file = os.path.join(prompt_dir, 'insertion', 'mutation_insertion_prompt_dependent.txt')
        with open(selection_prompt_file, 'r') as sf:
            self.sel_prompt = sf.read().strip()
        with open(insertion_prompt_file, 'r') as mf:
            self.ins_iso_prompt = mf.read().strip()
        with open(insertion_dep_prompt_file, 'r') as mf:
            self.ins_dep_prompt = mf.read().strip()
    
    def llm_select_mutation(self, 
                            verilog_region : Verilog, 
                            region_bugs : list[VerilogChange]) -> MutationSelection:
        previous_bugs_success = even_subset([bug.stringify() for bug in region_bugs if bug.valid], 6)
        # print('PREVIOUS SUCCESS REGION', previous_bugs_success)
        previous_bugs_failed = even_subset([bug.stringify() for bug in region_bugs if not bug.valid], 6)

        prompt = self.sel_prompt \
            .replace('{ALLOWED_MUTATIONS}', self.allowed_mutations.stringify()) \
            .replace('{PREVIOUS_BUGS_SUCCESS}', '\n\n'.join(previous_bugs_success)) \
            .replace('{PREVIOUS_BUGS_FAILED}', '\n\n'.join(previous_bugs_failed)) \
            .replace('{VERILOG_REGION}', verilog_region.get_content(lineate=True))
        
        llm_response = self.llm_model.call("You are a verilog bug inserter", prompt, output_schema=MutationSelection)
        log_llm(f'bug_{self.bug_num}', '2_select_mutation', prompt, llm_response)

        return MutationSelection(**llm_response)

    def llm_mutate_line(self, 
                        region : Verilog, 
                        line_num : int, 
                        mutation_class : Mutation, 
                        class_bugs : list[VerilogChange]) -> LineMutation:
        with open(mutation_class.instruction_file, 'r') as f:
            mutation_instructions = f.read()
        
        previous_bugs_success = even_subset([bug.stringify() for bug in class_bugs if bug.valid], 6)
        # print('PREVIOUS SUCCESS CLASS', previous_bugs_success)
        previous_bugs_failed = even_subset([bug.stringify() for bug in class_bugs if not bug.valid], 6)

        if mutation_class.isolated:
            prompt = self.ins_iso_prompt \
                .replace('{VERILOG_LINE}', region.get_line(line_num)) \
                .replace('{MUTATION_TYPE}', mutation_class.name) \
                .replace('{MUTATION_DESCRIPTION}', mutation_instructions) \
                .replace('{PREVIOUS_BUGS_SUCCESS}', '\n\n'.join(previous_bugs_success)) \
                .replace('{PREVIOUS_BUGS_FAILED}', '\n\n'.join(previous_bugs_failed))
        else:
            prompt = self.ins_dep_prompt \
                .replace('{VERILOG_LINE}', region.get_line(line_num)) \
                .replace('{VERILOG_REGION}', region.get_content(lineate=True)) \
                .replace('{LINE_NUMBER}', str(line_num)) \
                .replace('{MUTATION_TYPE}', mutation_class.name) \
                .replace('{MUTATION_DESCRIPTION}', mutation_instructions) \
                .replace('{PREVIOUS_BUGS_SUCCESS}', '\n\n'.join(previous_bugs_success)) \
                .replace('{PREVIOUS_BUGS_FAILED}', '\n\n'.join(previous_bugs_failed))
        
        llm_response = self.llm_model.call("You are a verilog bug inserter", prompt, output_schema=LineMutation)
        log_llm(f'bug_{self.bug_num}', '3_mutate_line', prompt, llm_response)

        return LineMutation(**llm_response)

    def mutate(self,
               region_idx: int,
               region: Verilog,
               cache: VerilogCache,
               bug_num: int = 0,
               ws_server: PipelineWebSocket=None) -> Union[VerilogChange, None]:
        self.bug_num = bug_num

        # select mutation and line number
        if ws_server:
            ws_server.set_current_process('Select Bug')
        
        region_bugs = cache.get_changes_in_region(region_idx, show_invalid=True)
        selection_output = self.llm_select_mutation(region, region_bugs)
        if selection_output.rollback:
            self.debug_log('Cannot apply mutation in given region. Rolling back...')
            return None
        line_num, mutation_type = selection_output.line, selection_output.mutation.strip()
        self.debug_log(f'Selected mutation {mutation_type} in Line {line_num}: {selection_output.justification}')
        if ws_server:
            ws_server.select_bug(
                bug=wstypes.Bug(
                    name=mutation_type, 
                    description=self.allowed_mutations.find_by_name(mutation_type).description
                ),
                line=wstypes.VerilogLine(
                    lineNumber=line_num,
                    before=region.get_line(line_num)
                )
            )

        # insert selected mutation into selected line
        if ws_server:
            ws_server.set_current_process('Mutate Line')
        class_bugs = cache.get_changes_by_type(mutation_type, show_invalid=True)
        mutation_output = self.llm_mutate_line(
            region, line_num, self.allowed_mutations.find_by_name(mutation_type), class_bugs)
        mutated_line, mutation_summary = mutation_output.mutated, mutation_output.summary
        if ws_server:
            ws_server.mutate_line(
                mutated_line=wstypes.VerilogLine(
                    lineNumber=line_num,
                    before=region.get_line(line_num),
                    after=mutated_line,
                    justification=mutation_summary,
                )
            )

        # mutate verilog and return change
        change = region.apply_change(line_num, mutated_line, mutation_type, mutation_summary,
                                     comment=f'BUG_{bug_num}: Inserted {mutation_type} bug')
        return change
