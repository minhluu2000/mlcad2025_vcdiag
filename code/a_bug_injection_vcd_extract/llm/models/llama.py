import torch
import transformers
import vcd_extract.llm.models.utils as mutils

class LLAMA(mutils.LLMModel):
    def __init__(self, model_id='meta-llama/Meta-Llama-3-8B'):
        super().__init__(model_id)
        self.model = None
        self.tokenizer = None
        self.pipe = None

    def initialize(
        self,
        dtype=torch.bfloat16,
        quantize=False
    ):
        hf_token = mutils.get_api_key('huggingface')

        if quantize:
            bnb_config = transformers.BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=dtype,
            )
        else:
            bnb_config = None
        
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            self.model_id,
            device_map="auto",
            quantization_config=bnb_config,
            low_cpu_mem_usage=True,
            token=hf_token,
        )

        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            self.model_id, 
            token=hf_token,
        )

        self.pipe = transformers.pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            pad_token_id=self.tokenizer.eos_token_id,
        )

    def call(self, role : str, prompt : str):
        full_prompt = role + '\n\n' + prompt

        output = self.pipe(
            full_prompt,
            max_new_tokens=4800,
            # do_sample=True, 
            # temperature=0.7
        )
        
        return output[0]['generated_text']