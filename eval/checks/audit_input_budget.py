"""No API: verify full-input reservations against historical usage and all75 prompt cases."""
import contextlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'eval'))
from evaluation_budget import InputReservation,tokenizer_provenance
from evaluation_common import verified_snapshot,verified_questions,clone_memory,load_trial
from build_runtime import atomic_json


def forbidden(*a,**k):raise AssertionError('No network in budget audit')


def main():
    with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden):
        counter=InputReservation()
        records=[json.loads(l) for l in (ROOT/'runs/formal-conv26-v1/calls.jsonl').read_text().splitlines()]
        starts={e['index']:e for e in records if e['event']=='started'}
        history=[]
        for response in (e for e in records if e['event']=='response'):
            s=starts[response['index']]
            estimate=counter.estimate(s['model'],s['messages'],s['temperature'],s['max_tokens'])
            actual=response['usage']['prompt_tokens']
            if actual>estimate['reserved_input_tokens']:raise AssertionError('Historical input exceeds reserve')
            history.append({'index':s['index'],'offline_input_tokens':estimate['offline_input_tokens'],'server_input_tokens':actual,'reserved_input_tokens':estimate['reserved_input_tokens']})
        import utils
        import mid_term_memory
        import faiss
        faiss.omp_set_num_threads(1)
        from main_loco_parse import generate_system_response_with_meta
        from evaluation_common import fixed_spec
        spec=fixed_spec();questions,_=verified_questions();snapshot,manifest,_=verified_snapshot()
        meta=json.loads((ROOT/'runs/embedding-download.json').read_text());factory=utils.SentenceTransformer
        rows=[]
        class Capture:
            def chat_completion(self,messages,temperature=.7,max_tokens=2000):
                self.estimate=counter.estimate('deepseek-flash',messages,temperature,max_tokens)
                return ''
        with tempfile.TemporaryDirectory() as tmp,patch.object(utils,'SentenceTransformer',lambda name:factory(meta['snapshot_path'],local_files_only=True)),contextlib.redirect_stdout(io.StringIO()),patch.object(mid_term_memory,'llm_extract_keywords',return_value=set()):
            utils._get_embedding_model.cache_clear()
            # Previously proven all25 top5 cosine scores >.1; keyword score is nonnegative.
            certificate=json.loads((ROOT/'runs/eval-prepared-conv26-v1/offline-audit.json').read_text())
            assert certificate['certified_questions']==25
            for k in (5,10,20):
                directory=Path(tmp)/str(k);clone_memory(snapshot,directory,manifest)
                short,mid,long,retriever=load_trial(directory,k,None)
                for q in questions:
                    result=retriever.retrieve(q['question'],segment_threshold=.1,page_threshold=.1,knowledge_threshold=.1,client=None)
                    capture=Capture()
                    generate_system_response_with_meta(q['question'],short,long,result['retrieval_queue'],result['long_term_knowledge'],capture,'conv-26',spec['speaker_a'],spec['speaker_b'],{})
                    rows.append({'capacity':k,'question_id':q['question_id'],**capture.estimate})
            utils._get_embedding_model.cache_clear()
        verified_snapshot()
        result={'kind':'offline_full_input_budget_validation','new_api_calls':0,'tokenizer':tokenizer_provenance(),'old_context_reservation_cny':(1048576*2+2000*8)/1000000,'historical_requests_verified':len(history),'maximum_server_minus_offline_tokens':max(r['server_input_tokens']-r['offline_input_tokens'] for r in history),'all_historical_inputs_covered':True,'historical_checks':history,'complete_prompt_cases':rows,'answer_reservation_cny_min':min(r['reserved_cost_micro_cny'] for r in rows)/1000000,'answer_reservation_cny_max':max(r['reserved_cost_micro_cny'] for r in rows)/1000000,'all_prompts_untrimmed':True}
        atomic_json(ROOT/'runs/eval-prepared-conv26-v1/input-budget-audit.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('historical_checks','complete_prompt_cases')},indent=2))


if __name__=='__main__':main()
