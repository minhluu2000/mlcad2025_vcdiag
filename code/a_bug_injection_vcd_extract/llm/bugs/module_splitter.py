from vcd_extract.llm.models import LLMModel
from vcd_extract.llm.parsing.encoding import ModuleDivisionEncoder
from vcd_extract.llm.parsing.verilog import Verilog, VerilogPartition
from .mutation import load_mutations
from pydantic import BaseModel
import re
import os.path

class LModuleRegion(BaseModel):
    start_line: int
    end_line: int
    region_description: str

class LModuleSplit(BaseModel):
    split: list[LModuleRegion]

class LRegionDescription(BaseModel):
    summary: str
    mutation_classes: list[str]

class LRegionDescriptionList(BaseModel):
    descriptions: list[LRegionDescription]

class ModuleSplitter:
    AVG_TOKENS_PER_WORD = 3

    def __init__(self, llm_model : LLMModel, prompt_dir : str, debug=False):
        super().__init__()
        self.llm_model = llm_model
        self.debug = debug
        self.encoder = ModuleDivisionEncoder()
        self.allowed_mutations = load_mutations(os.path.join(prompt_dir, 'mutations'))
        self.initialize(prompt_dir)
    
    def debug_log(self, *args):
        if self.debug:
            print(*args)

    def initialize(
        self,
        prompt_dir : str
    ):
        division_prompt_file = os.path.join(prompt_dir, 'division_prompt.txt')
        with open(division_prompt_file, 'r') as f:
            self.division_prompt = f.read().strip()
        
        label_prompt_file = os.path.join(prompt_dir, 'label_regions_prompt.txt')
        with open(label_prompt_file, 'r') as f:
            self.label_prompt = f.read().strip()
    
    def llm_split_module(self, verilog_chunk : str) -> LModuleSplit:
        chunk_prompt = self.division_prompt \
            .replace('{VERILOG_CHUNK}', verilog_chunk)
        
        llm_output = self.llm_model.call("You are a verilog file splitter", chunk_prompt, LModuleSplit)
        return LModuleSplit(**llm_output)
    
    def llm_label_regions(self, partition: VerilogPartition):
        regions_str = '\n\n'.join([
            f'Region {i}:\n```\n{region.get_content()}\n```' 
            for i, region in enumerate(partition)
        ])

        prompt = self.label_prompt \
            .replace('{REGIONS}', regions_str) \
            .replace('{ALLOWED_MUTATIONS}', self.allowed_mutations.stringify())
        llm_output = self.llm_model.call("Your task is to label verilog code regions",
                                         prompt, LRegionDescriptionList)
        
        descriptions = LRegionDescriptionList(**llm_output).descriptions
        for i, description in enumerate(descriptions):
            partition[i].set_description(
                f'- Summary: {description.summary} \n- Applicable Mutations: {description.mutation_classes or "None"}')
    
    def split_into_chunks(self, full_verilog : Verilog, max_tokens: int) -> list[Verilog]:
        current_token_count = 0
        chunks = []
        
        for line_num in range(full_verilog.start_line, full_verilog.end_line+1):
            line = full_verilog.get_line(line_num)
            line_token_estimate = int(len(re.findall(r'\S+', line)) * self.AVG_TOKENS_PER_WORD)
            
            if current_token_count + line_token_estimate > max_tokens or line_num == full_verilog.end_line:
                chunks.append(full_verilog.slice(slice_end=line_num))
                current_token_count = line_token_estimate
            else:
                current_token_count += line_token_estimate

        return chunks

    def split_verilog(
        self,
        full_verilog: Verilog,
        regions: list[tuple[int, int]] = None,
        max_tokens=48000,
        extra_lines=10,
    ) -> VerilogPartition:
        partition = VerilogPartition(full_verilog)

        if not regions:
            chunks = self.split_into_chunks(full_verilog, max_tokens)
            self.debug_log(f'-- Split into {len(chunks)} chunks')

            for i, chunk in enumerate(chunks):
                self.debug_log(f'---- Parsing Chunk {i+1} / {len(chunks)}')
                llm_output = self.llm_split_module(chunk.get_content(
                    lineate=True, extra_lines=extra_lines, include_eof=i == len(chunks)-1
                ))
                region_specs = llm_output.split
                for region_spec in region_specs:
                    partition.add_region(region_spec.start_line, region_spec.end_line, region_spec.region_description)
            
        else:
            for region_spec in regions:
                partition.add_region(region_spec[0], region_spec[1])
            self.llm_label_regions(partition)
        
        return partition