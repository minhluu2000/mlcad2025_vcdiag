import os
from typing import Union
import json

def log_llm(bug_name: str, prompt_name: str, prompt: str, response: Union[str, dict]):
    bug_dir = os.path.join('logs', 'llm', bug_name)
    os.makedirs(bug_dir, exist_ok=True)

    prompt_file = os.path.join(bug_dir, f'{prompt_name}.log')
    with open(prompt_file, 'w') as prompt_out:
        prompt_out.write(prompt)
    
    if isinstance(response, dict):
        response_file = os.path.join(bug_dir, f'{prompt_name}_response.json')
        response = json.dumps(response, indent=4)
    else:
        response_file = os.path.join(bug_dir, f'{prompt_name}_response.log')
    with open(response_file, 'w') as response_out:
        response_out.write(response)