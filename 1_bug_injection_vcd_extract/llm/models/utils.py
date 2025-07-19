import os
import json
from pydantic import BaseModel
from typing import Union

def read_secrets() -> dict:
    filename = os.path.join('vcd_extract/llm/secrets.json')
    try:
        with open(filename, mode='r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        print('secrets.json not found')
        return {}

def get_api_key(api_name : str) -> str:
    try:
        return read_secrets()["api_keys"][api_name]
    except:
        return ''

class LLMModel:
    def __init__(self, model_id : str):
        self.model_id = model_id
        pass
    
    def initialize(self, **kwargs):
        pass
    
    def call(self, 
             role : str, 
             prompt : str, 
             output_schema: BaseModel = None, 
             history: list[dict] = None) -> Union[str, dict]:
        return ''
