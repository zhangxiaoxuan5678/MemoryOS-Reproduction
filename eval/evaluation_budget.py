"""Full, untrimmed input reservation using the official offline tokenizer."""
import hashlib
import json
import math
from pathlib import Path
from build_runtime import BuildStop, digest

ROOT=Path(__file__).resolve().parent.parent
TOKENIZER=ROOT/'runs/deepseek-v4-tokenizer/deepseek_v4_tokenizer'


class InputReservation:
    def __init__(self):
        from transformers import AutoTokenizer
        self.tokenizer=AutoTokenizer.from_pretrained(TOKENIZER,local_files_only=True,trust_remote_code=False,model_max_length=1048576)

    def estimate(self,model,messages,temperature,max_tokens):
        # Explicitly no truncation or padding: every message is counted in full.
        ids=self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,truncation=False)
        wire=json.dumps({'model':model,'messages':messages,'temperature':temperature,'max_tokens':max_tokens,'extra_body':{'thinking':{'type':'disabled'}}},ensure_ascii=False).encode()
        count=len(ids)
        # Tokenizer margin plus an independent, wider UTF8-byte envelope.
        # The byte envelope includes full request syntax and 1024 framing tokens.
        upper=max(math.ceil(count*1.25)+512,len(wire)+1024)
        if upper>1048576:
            raise BuildStop('Conservative full-input reservation exceeds context; no trimming')
        return {'offline_input_tokens':count,'input_safety_margin_policy':'max(ceil(official_chat_tokens*1.25)+512, full_request_utf8_bytes+1024)','full_request_utf8_bytes':len(wire),'reserved_input_tokens':upper,'reserved_output_tokens':max_tokens,'reserved_cost_micro_cny':upper*2+max_tokens*8,'full_request_sha256':hashlib.sha256(wire).hexdigest()}


def tokenizer_provenance():
    return {'source_document':'https://api-docs.deepseek.com/zh-cn/quick_start/token_usage/','download_url':'https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip','official_zip_sha256':digest(TOKENIZER.parent/'official.zip'),'files_sha256':{n:digest(TOKENIZER/n) for n in ('tokenizer.json','tokenizer_config.json')},'trust_remote_code':False,'truncation':False}
