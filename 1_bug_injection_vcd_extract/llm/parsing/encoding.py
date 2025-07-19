import json
from typing_extensions import override

def extract_llm_output(output : str, start_token : str, end_token : str) -> str:
    if start_token not in output:
        return ''
    
    after_start = output.split(start_token)[1]
    if end_token not in after_start:
        return ''
    
    return after_start.split(end_token)[0]

class SimpleEncoder:
    def __init__(self, output_sections : list[str]):
        self.output_sections = output_sections

    def parse_output(self, output : str):
        parsed = {}
        for section in self.output_sections:
            parsed[section] = extract_llm_output(output, f'<{section}>', f'</{section}>')
        return parsed

class ChunkedEncoder:
    def __init__(self):
        pass

    def get_default(self) -> str:
        return ''

    def extract_output(self, llm_response : str):
        return None
    
    def merge(self, lhs, rhs):
        return lhs + rhs
    
class ModuleDivisionEncoder(ChunkedEncoder):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    @override
    def get_default(self) -> list[dict]:
        return []
    
    @override
    def extract_output(self, llm_response : str) -> list[dict]:
        json_terms = [
            ('```json', '```'),
            ('```', '```'),
            ('<json>', '</json>'),
        ]
        output_json_str = '[]'
        for start_token, end_token in json_terms:
            if extracted := extract_llm_output(llm_response, start_token, end_token):
                output_json_str = extracted
                break
        
        try:
            output_json = json.loads(output_json_str)
        except:
            return self.get_default()
        
        if isinstance(output_json, list):
            return output_json
        else:
            return self.get_default()

    @override
    def merge(self, lhs: list[dict], rhs: list[dict]) -> list[dict]:
        return lhs + rhs