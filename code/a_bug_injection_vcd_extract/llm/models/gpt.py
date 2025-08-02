import vcd_extract.llm.models.utils as mutils
import sys
from typing import Union
from pydantic import BaseModel
from openai import OpenAI

sys.modules.keys()

class GPT(mutils.LLMModel):
    def __init__(self, model_id='gpt-4o-mini'):
        super().__init__(model_id)

    def initialize(self):
        self.client = OpenAI(api_key=mutils.get_api_key('gpt'))
    
    def call(self, 
             role : str, 
             prompt : str, 
             output_schema: BaseModel = None,
             history: list[dict] = None) -> Union[str, dict]:
        response_format = output_schema if output_schema else {"type": "text"}

        if history:
            messages = [
                {"role": "system", "content": prompt}, 
                *history
            ]
        else:
            messages = [
                {"role": "system", "content": role},
                {"role": "user", "content": prompt},
            ]

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model_id,
                messages=messages,
                temperature=1,
                max_tokens=10000,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                response_format=response_format
            )
        except Exception as e:
            print(prompt)
            raise(e)


        if output_schema:
            return dict(response.choices[0].message.parsed)
        else:
            return response.choices[0].message.content