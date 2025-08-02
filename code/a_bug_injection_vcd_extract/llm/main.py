import os
import argparse
from vcd_extract.llm.models import *
from vcd_extract.llm.bugs import BugInserter
from vcd_extract.visualization.server import PipelineWebSocket
import vcd_extract.visualization.types as wstypes
import time
import random

def main():
    parser = argparse.ArgumentParser(description="Verilog Bug Injection with LLMs")
    parser.add_argument('--model', type=str, default=None, help="Model name (e.g., llama)")
    parser.add_argument('--size', type=str, default=None, help="Model size (e.g., 7b, 13b, 70b)")
    parser.add_argument('--design_dir', type=str, default="designs", help="Directory containing verilog design files")
    parser.add_argument('--design_path', type=str, help="Path to design file to insert bugs")
    parser.add_argument('--out_dir', type=str, default="out", help="Directory containing output files")
    parser.add_argument('--cache_dir', type=str, default="cache", help="Directory containing cache files")
    parser.add_argument('--prompt_dir', type=str, default="prompts", help="Directory containing all required prompt files")
    parser.add_argument('--num_bugs', type=int, default=1, help="Number of bugs to insert")
    parser.add_argument('--debug', action='store_true', help="Debug mode (include more detailed logs)")

    args = parser.parse_args()

    models = {
        "llama": [
            "7b",
            "13b",
            "30b",
            "70b",
        ],
        "bert": [
            "uncased",
        ],
        "gpt": [
            "gpt-4o-mini",
            "gpt-3.5-turbo",
        ]
    }
    
    if args.model is None:
        print("Available models:")
        for i, model in enumerate(models.keys()):
            print(f'({i+1}) {model}')
        model_id = int(input("Please select a model: ")) - 1
        model_name = list(models.keys())[model_id]
    else:
        model_name = args.model

    if args.size is None:
        print(f"Available architectures for {model_name}")
        for i, model_arch in enumerate(models[model_name]):
            print(f'({i+1}) {model_arch}')
        model_arch_id = int(input("Please select the model architecture: ")) - 1
        model_size = models[model_name][model_arch_id]
    else:
        model_size = args.size
    
    gpt = GPT(model_id=model_size)
    gpt.initialize()

    pipeline_ws = PipelineWebSocket()
    print('Waiting for client to connect')
    if True:
        print('Client connected')
        time.sleep(5)
        print('Starting pipeline')
        bug_inserter = BugInserter(llm_model=gpt, 
                                   prompt_dir=args.prompt_dir, 
                                   debug=args.debug, 
                                   ws_server=pipeline_ws, 
                                   mutation_log_path=os.path.join(args.out_dir, 'mutation_log.csv'))
        
        num_bugs = args.num_bugs

        # design_files = [f for f in os.listdir(args.design_dir) if f.endswith(".v") or f.endswith(".sv")]
        # for design_file in design_files:
        #     design_path = os.path.join(args.design_dir, design_file)
        #     design_name = design_file.split('.v')[0].split('.sv')[0]
        #     print(f'Loading {design_name}')

        design_file = args.design_path
        design_name = design_file.split('.v')[0].split('.sv')[0].split('/')[-1]
        design_extension = design_file.split('.')[-1]
        cache_file = os.path.join(args.cache_dir, f'{design_name}.pkl')
        bug_inserter.load_verilog(args.design_path, cache_file_path=cache_file)

        success_prob = 0.6
        for i in range(num_bugs):
            out_path = str(os.path.join(args.out_dir, design_name + f'_mutated_b{i+1}.{design_extension}'))
            _, mutation_desc = bug_inserter.insert_bug(out_file=out_path)
            pipeline_ws.set_current_process('Evaluate')
            time.sleep(2.5)

            if random.random() < success_prob:
                pipeline_ws.evaluate(
                    wstypes.EvaluationResult(
                        status='success'
                    )
                )
            else:
                pipeline_ws.evaluate(
                    wstypes.EvaluationResult(
                        status='failure',
                        error='Failed to produce mutation. We will now roll back'
                    )
                )
                time.sleep(2.5)
                bug_inserter.undo_mutation()
            time.sleep(2.5)
            
            print(f'-- Inserted bug {i+1}/{num_bugs} -> {mutation_desc}')
        
        bug_inserter.save_cache(cache_file)
        pipeline_ws.shutdown()

if __name__ == "__main__":
    main()
