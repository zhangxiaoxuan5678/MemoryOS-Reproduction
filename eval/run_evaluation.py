"""Preview only unless explicitly authorized. Nine trials, no memory updates."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import urlparse
from build_runtime import BuildStop, LedgerClient, atomic_json, digest
from evaluation_common import (ROOT, CAPACITIES, REPEATS, clone_memory, check_memory_files,
                               load_trial, retrieval_metrics, verified_preparation, verified_snapshot)


class EvaluationClient(LedgerClient):
    def __init__(self,*a,**k):
        super().__init__(*a,**k)
        from evaluation_budget import InputReservation
        self.input_counter=InputReservation()
        self.context={}

    def append(self,event):
        super().append({**event,**self.context})

    def chat_completion(self,messages,temperature=0.7,max_tokens=2000):
        if max_tokens!=2000 or self.page is None:
            raise BuildStop('Evaluation output limit must remain 2000')
        self.ordinal+=1
        operation=f'page:{self.page}:call:{self.ordinal}'
        if any(e['event']=='started' and e['operation']==operation for e in self.events):
            raise BuildStop('Evaluation must not reuse generated answers or retry operations')
        estimate=self.input_counter.estimate(self.model,messages,temperature,max_tokens)
        settled,unsettled=self.money()
        if self.count>=self.limit:
            raise BuildStop('Request budget exhausted before sending')
        if unsettled:
            raise BuildStop('Prior request usage unknown; stop without retry')
        if self.budget_micro is not None and settled+unsettled+estimate['reserved_cost_micro_cny']>self.budget_micro:
            raise BuildStop('CNY budget insufficient for full-input plus maximum-output reservation')
        self.count+=1
        self.append({'event':'started','index':self.count,'operation':operation,'utc':datetime.now(timezone.utc).isoformat(),'model':self.model,'messages':messages,'temperature':temperature,'max_tokens':max_tokens,'thinking':'disabled',**estimate})
        try:
            result=self.sdk.chat.completions.create(model=self.model,messages=messages,temperature=temperature,max_tokens=max_tokens,extra_body={'thinking':{'type':'disabled'}})
        except Exception as error:
            self.append({'event':'failed','index':self.count,'error_type':type(error).__name__,'http_status':getattr(error,'status_code',None)})
            raise BuildStop('API failure; no retry; reservation retained') from None
        answer=result.choices[0].message.content
        finish=result.choices[0].finish_reason
        usage=result.usage.model_dump() if result.usage else None
        valid=isinstance(answer,str) and bool(answer.strip()) and finish=='stop'
        self.append({'event':'response','index':self.count,'response_id':result.id,'returned_model':result.model,'usage':usage,'answer':answer,'finish_reason':finish,'valid_answer':valid,'failure_kind':'truncated' if finish=='length' else ('invalid_response' if not valid else None)})
        if usage is None:
            raise BuildStop('Usage missing; reservation retained, stop')
        if usage.get('prompt_tokens',1048577)>estimate['reserved_input_tokens'] or usage.get('completion_tokens',2001)>max_tokens:
            raise BuildStop('Usage exceeded reservation; stop and audit')
        return self.checked_answer({'answer':answer,'finish_reason':finish})


def per_question_usage(client, after_index):
    responses = [e for e in client.events if e['event']=='response' and e['index']>after_index]
    return {key:sum((e.get('usage') or {}).get(key,0) or 0 for e in responses) for key in ('prompt_tokens','completion_tokens','total_tokens')}


def execute_trials(directory,prepared,spec,questions,client):
    snapshot,manifest,_=verified_snapshot()
    from main_loco_parse import generate_system_response_with_meta
    total_rows=0
    for repeat in REPEATS:
        trials={}
        for k in CAPACITIES:
            job=directory/f'k{k:02d}-r{repeat}'
            clone_memory(snapshot,job/'memory',manifest)
            trials[k]={'job':job,'modules':load_trial(job/'memory',k,client),'started':time.monotonic(),'active_seconds':0}
        # Round-robin by question. Rotate the first capacity between repeats.
        offset=repeat-1
        order=CAPACITIES[offset:]+CAPACITIES[:offset]
        for qi,question in enumerate(questions):
            for k in order:
                trial=trials[k];job=trial['job']
                short,mid,long,retriever=trial['modules']
                global_index=((CAPACITIES.index(k)*3)+(repeat-1))*25+qi
                client.begin_page(global_index)
                client.context={'capacity':k,'repeat':repeat,'question_id':question['question_id'],'stage':'retrieval_keywords'}
                before=client.count;started=time.monotonic()
                metrics=None
                try:
                    result=retriever.retrieve(question['question'],segment_threshold=.1,page_threshold=.1,knowledge_threshold=.1,client=client)
                    retrieved_time=time.monotonic()-started
                    metrics=retrieval_metrics(result)
                    if short.get_all():raise BuildStop('Unexpected evaluation conversation history')
                    client.context['stage']='answer';answer_start=time.monotonic()
                    answer,system_prompt,user_prompt=generate_system_response_with_meta(question['question'],short,long,result['retrieval_queue'],result['long_term_knowledge'],client,spec['sample_id'],spec['speaker_a'],spec['speaker_b'],{})
                    answer_time=time.monotonic()-answer_start
                    if client.count-before!=2:raise BuildStop('Expected one keyword and one answer call')
                    elapsed=time.monotonic()-started;trial['active_seconds']+=elapsed
                    row={'valid_answer':True,'capacity':k,'repeat':repeat,'question_id':question['question_id'],'question':question['question'],'system_answer':answer,'retrieval':metrics,'usage_including_keywords':per_question_usage(client,before),'retrieval_seconds':retrieved_time,'answer_seconds':answer_time,'elapsed_seconds':elapsed,'prompt_sha256':__import__('hashlib').sha256((system_prompt+'\n'+user_prompt).encode()).hexdigest(),'request_indices':list(range(before+1,client.count+1))}
                    atomic_json(job/f'q{qi:02d}.json',row);total_rows+=1
                    print(f'Saved {total_rows}/225 k={k} r={repeat} q={qi}',flush=True)
                except Exception as error:
                    last=next((e for e in reversed(client.events) if e['event'] in ('response','failed') and e['index']>before),{})
                    failure={'valid_answer':False,'capacity':k,'repeat':repeat,'question_id':question['question_id'],'stage':client.context['stage'],'error_type':type(error).__name__,'finish_reason':last.get('finish_reason'),'failure_kind':'truncated' if last.get('finish_reason')=='length' else 'failed_or_budget_stop','partial_response_not_for_scoring':last.get('answer'),'retrieval':metrics,'usage_including_keywords':per_question_usage(client,before),'request_indices':list(range(before+1,client.count+1))}
                    atomic_json(job/f'q{qi:02d}.failed.json',failure)
                    raise
        for k,trial in trials.items():
            check_memory_files(trial['job']/'memory',manifest)
            atomic_json(trial['job']/'completed.json',{'capacity':k,'repeat':repeat,'questions':25,'elapsed_seconds':time.monotonic()-trial['started'],'active_question_seconds':trial['active_seconds'],'elapsed_includes_interleaved_wait':True,'memory_files_unchanged':True})
    verified_snapshot()
    return total_rows


def main():
    os.environ['OMP_NUM_THREADS']='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--max-requests',type=int,default=450)
    parser.add_argument('--max-cost-cny',default='20')
    parser.add_argument('--allow-paid',action='store_true')
    args=parser.parse_args()
    spec,questions=verified_preparation(args.prepared)
    if not args.allow_paid:
        print(json.dumps({'mode':'preview_no_api','total_trials':9,'questions_per_trial':25,'answers':225,'keyword_calls':225,'planned_total_requests':450,'proposed_request_cap':args.max_requests,'proposed_cny_cap':args.max_cost_cny,'budget_authorized':False,'snapshot_manifest_sha256':spec['snapshot_manifest_sha256'],'questions_sha256':spec['questions_sha256']},indent=2))
        return
    from decimal import Decimal
    if not 0<Decimal(args.max_cost_cny)<=20:
        raise BuildStop('Authorized evaluation monetary cap is at most CNY20')
    if not 1<=args.max_requests<=450:
        raise BuildStop('Evaluation request budget must not exceed planned 450')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise BuildStop('Commit reviewed implementation before paid evaluation')
    directory=args.run_dir.resolve()
    if directory.parent!=(ROOT/'runs').resolve() or directory==args.prepared.resolve():
        raise BuildStop('Use a separate evaluation output directory under runs/')
    # Refuse existing output: no silent restarts or cross-trial answer reuse.
    directory.mkdir(exist_ok=False)
    from utils import OpenAIClient
    configured=OpenAIClient()
    if configured.model!=spec['model'] or urlparse(str(configured.client.base_url)).hostname!='api.deepseek.com':
        raise BuildStop('Evaluation model/provider differs from approved snapshot plan')
    client=EvaluationClient(directory,configured.model,configured.client.with_options(max_retries=0,timeout=60),args.max_requests,budget_cny=args.max_cost_cny)
    config={**spec,'actual_request_budget':args.max_requests,'actual_cny_budget':args.max_cost_cny,'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_sha256':{p.name:digest(p) for p in (ROOT/'eval').glob('*.py')},'sdk_retries':0,'timeout_seconds':60,'budget_authorized_by_operator_flag':True,'budget_authorized':True,'omp_threads':1,'schedule':'question_round_robin_capacity_first_rotates_by_repeat','input_reservation_policy':'official_full_chat_tokenizer_25pct_plus512_with_full_UTF8_request_plus1024_floor','tokenizer':__import__('evaluation_budget').tokenizer_provenance()}
    atomic_json(directory/'config.json',config)
    start=time.monotonic()
    try:
        # Same embedding model and encoding settings; local files only.
        os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
        import utils
        import faiss
        faiss.omp_set_num_threads(1)
        metadata=json.loads((ROOT/'runs/embedding-download.json').read_text())
        snapshot,manifest,_=verified_snapshot()
        if metadata['revision']!=manifest['build_config']['embedding_revision']:
            raise BuildStop('Embedding revision mismatch')
        for name,checksum in manifest['build_config']['embedding_files_sha256'].items():
            if digest(Path(metadata['snapshot_path'])/name)!=checksum:
                raise BuildStop('Embedding weights changed')
        factory=utils.SentenceTransformer
        with patch.object(utils,'SentenceTransformer',lambda name:factory(metadata['snapshot_path'],local_files_only=True)):
            utils._get_embedding_model.cache_clear()
            # Local-only warmup outside all trial/question timing windows.
            utils.get_embedding('local evaluation warmup')
            with (directory/'evaluation.log').open('a') as output,contextlib.redirect_stdout(output):
                answers=execute_trials(directory,args.prepared,spec,questions,client)
            utils._get_embedding_model.cache_clear()
        if answers!=225 or client.count!=450:
            raise BuildStop('Incomplete evaluation; cannot declare success')
        status={'status':'completed','answers':answers,**client.totals()}
    except Exception as error:
        status={'status':'stopped','completed_answer_files':len([p for p in directory.glob('k*-r*/q*.json') if not p.name.endswith('.failed.json')]),'error_type':type(error).__name__,**client.totals()}
        if isinstance(error,BuildStop): status['reason']=str(error)
        status['elapsed_seconds']=time.monotonic()-start
        atomic_json(directory/'status.json',status)
        print(json.dumps(status)); raise SystemExit(1) from None
    status['elapsed_seconds']=time.monotonic()-start
    atomic_json(directory/'status.json',status)
    print(json.dumps(status))


if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status':'preflight_stopped','error_type':type(error).__name__}))
        raise SystemExit(1) from None
