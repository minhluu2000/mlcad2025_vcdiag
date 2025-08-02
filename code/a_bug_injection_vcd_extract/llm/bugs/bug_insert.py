from vcd_extract.llm.models import LLMModel
from vcd_extract.llm.parsing.verilog import Verilog, VerilogPartition
from vcd_extract.llm.parsing.cache import *
from vcd_extract.llm.parsing.encoding import extract_llm_output
from vcd_extract.visualization.server import PipelineWebSocket
import vcd_extract.visualization.types as wstypes
from vcd_extract.evaluation import MutationRecord, MutationLogger, log_llm
from .module_splitter import ModuleSplitter
from .region_mutator import RegionMutator
from .mutation import load_mutations
from . import logging
from pydantic import BaseModel
import os.path
from datetime import datetime
import time
import json

class RegionSelection(BaseModel):
    justification: str
    region_idx: int

class BugInserter:
    def __init__(self, 
                 llm_model : LLMModel, 
                 prompt_dir : str, 
                 ws_server: PipelineWebSocket=None, 
                 debug=False, 
                 clear_cache=True,
                 mutation_log_path='mutation_log.csv'):
        super().__init__()
        self.debug = debug
        self.prompt_dir = prompt_dir

        self.llm_model = llm_model
        self.allowed_mutations = load_mutations(os.path.join(prompt_dir, 'mutations'))
        self.module_splitter = ModuleSplitter(llm_model, prompt_dir, debug)
        self.region_mutator = RegionMutator(llm_model, prompt_dir, self.allowed_mutations, debug)

        self.region_selection_history = []
        self.prev_mut_region = []
        self.partition : VerilogPartition = None
        self.num_attempts = 0

        self.ws_server = ws_server
        self.verilog_cache : VerilogCache = None
        self.clear_cache = clear_cache

        self.logger = MutationLogger(mutation_log_path)        
    
    def debug_log(self, *args):
        if self.debug:
            print(*args)
    
    def stringify_regions(self) -> str:
        region_str = ''
        for i, region in enumerate(self.partition):
            region_str += f"""Region {i} \t {region.start_line}-{region.end_line}: \n{region.description or 'No Description'}\n\n"""
        return region_str
    
    def is_file_loaded(self) -> bool:
        return len(self.partition) > 0
    
    def ws_send_regions(self):
        if self.ws_server:
            self.ws_server.split_file([
                wstypes.Region(
                    name=f'Region {i}', 
                    description=region.description, 
                    totalLines=region.num_lines,
                    buggyLines=len(region.history.undo_stack)
                )
                for i, region in enumerate(self.partition)
            ])
    
    def ws_update_stats(self):
        mutation_frequencies = {
            mutation.name: 0 for mutation in self.allowed_mutations
        }
        for region in self.partition:
            for change in region.history.undo_stack:
                mutation_frequencies[change.bug_type] += 1
        bug_stats = [
            wstypes.BugFrequency(name=name, amount=amount) for name, amount in mutation_frequencies.items()
        ]
        num_successes = sum([len(region.history.undo_stack) for region in self.partition])
        if self.ws_server:
            self.ws_server.update_stats(
                wstypes.Stats(
                    bugStats=bug_stats,
                    successes=num_successes,
                    totalAttempts=self.num_attempts
                )
            )

    def load_verilog(self, 
                     verilog_file_path : str, 
                     cache_file_path : str = None, 
                     rois: list[tuple[int, int]] = None):
        if self.ws_server:
            self.ws_server.set_current_process('Split File')
        
        self.debug_log(f'Loading verilog file: {verilog_file_path}')

        full_verilog = Verilog(name=os.path.basename(verilog_file_path), 
                                    file=verilog_file_path)
        
        if self.clear_cache and cache_file_path and os.path.exists(cache_file_path):
            os.remove(cache_file_path)
            # Clear the cache only once
            self.clear_cache = False
            self.debug_log(f'Cleared verilog cache at {cache_file_path} due to clear_cache flag set to True')
        
        if cache_file_path and os.path.exists(cache_file_path):
            self.verilog_cache = load_verilog_cache(cache_file_path)
            self.partition = self.verilog_cache.extract_regions(full_verilog)
            self.debug_log(f'Loaded verilog cache from {cache_file_path}')
        else:
            self.partition = self.module_splitter.split_verilog(full_verilog, regions=rois)
            self.verilog_cache = VerilogCache(partition=self.partition)
        
        self.debug_log(self.stringify_regions())
        self.bugs_per_region = [0 for _ in range(len(self.partition))]
        self.num_regions = len(self.partition)
        self.num_attempts = 0

        self.ws_update_stats()
        self.ws_send_regions()
    
    def llm_select_region(self) -> int:
        if self.ws_server:
            self.ws_server.set_current_process('Select Region')
        
        selection_history = []
        for i in range(self.num_regions):
            all_region_changes = self.verilog_cache.get_changes_in_region(i, show_invalid=True)
            successful_region_changes = [change for change in all_region_changes if change.valid]
            selection_history.append({
                'region_idx': i,
                'description': self.partition[i].description,
                'region_length': self.partition[i].num_lines,
                'num_mutations_attempted': len(all_region_changes),
                'num_mutations_successful': len(successful_region_changes), 
            })
        
        prompt_file = os.path.join(self.prompt_dir, 'insertion', 'region_selection_prompt.txt')
        with open(prompt_file, 'r') as f:
            prompt = f.read() \
                .replace('{REGION_DESCRIPTIONS}', self.stringify_regions()) \
                .replace('{ALLOWED_MUTATIONS}', self.allowed_mutations.stringify()) \
                .replace('{REGION_SELECTION_HISTORY}', json.dumps(selection_history, indent=4))
        
        llm_output = self.llm_model.call('You are a verification engineer', prompt, RegionSelection)
        log_llm(f'bug_{self.num_attempts+1}', '1_select_region', prompt, llm_output)

        region_idx = llm_output['region_idx']
        justification = llm_output['justification']
        
        self.debug_log(f'Selected Region {region_idx}: {justification}')

        if self.ws_server:
            self.ws_server.select_region(region_idx)

        self.region_selection_history.append(f'Region {region_idx}')
        
        self.debug_log(f'Region selection history: \n{json.dumps(selection_history, indent=4)}')
        
        return region_idx
    
    def insert_bug(self, out_file : str = '', mut_rec: MutationRecord = None) -> tuple[str, str]:
        self.ws_send_regions()
        self.ws_update_stats()

        t0 = time.time()

        while True:
            region_idx = self.llm_select_region()
            
            self.debug_log(f'Inserting bug into region {region_idx}')
            region = self.partition[region_idx]
            region_start_str = region.get_content()

            self.num_attempts += 1

            # Start timing
            change = self.region_mutator.mutate(
                region_idx=region_idx,
                region=region, 
                cache=self.verilog_cache, 
                bug_num=self.num_attempts,
                ws_server=self.ws_server)

            if change is None:
                continue

            t1 = time.time()

            mutation_desc = change.stringify()
            self.debug_log(f'Mutation description: {mutation_desc}')
            self.debug_log(f'Recent change: {change}')

            self.verilog_cache.add_changes([change])
            self.prev_mut_region.append(region_idx)

            region_mut_str = region.get_content()
            logging.print_diff(region_start_str, region_mut_str)

            # Log mutation
            timestamp_now = datetime.now()
            if mut_rec:
                mut_rec.mutation_class = change.bug_type
                mut_rec.line_number = change.line_idx
                mut_rec.original_line = change.old_line
                mut_rec.mutated_line = change.new_line

                gen_time_ms = (t1 - t0) * 1000
                mut_rec.generation_time_ms += gen_time_ms
                if mut_rec.num_retries > 0:
                    mut_rec.rollback_time_ms += gen_time_ms

            # self.logger.log_mutation(mutation_record)
            # self.logger.save_to_csv()

            full_verilog_content = self.partition.get_full_verilog_content()

            if out_file:
                with open(out_file, 'w') as out_writer:
                    out_writer.write(full_verilog_content)
                return '', mutation_desc

            return full_verilog_content, mutation_desc

    def undo_mutation(self):
        if len(self.prev_mut_region) == 0:
            self.debug_log('No mutations to undo')
            return
        current_prev_mut_region = self.prev_mut_region.pop()
        self.debug_log(f'Undoing Mutation in Region {current_prev_mut_region}')
        self.partition[current_prev_mut_region].undo()
        self.verilog_cache.invalidate_last_change()
        
        self.ws_send_regions()
        self.ws_update_stats()
    
    def save_cache(self, cache_file : str):
        dump_verilog_cache(self.verilog_cache, cache_file)