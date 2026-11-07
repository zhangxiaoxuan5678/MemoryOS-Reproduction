"""Temporary fake-only evaluation checks. No real answers or API calls."""
import contextlib
import io
import json
from pathlib import Path
import socket
import statistics
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'eval'))
from evaluation_common import (verified_snapshot, verified_questions, audit_selection,
                               clone_memory, check_memory_files, retrieval_metrics, fixed_spec)
from run_evaluation import EvaluationClient, execute_trials
from score_evaluation import aggregate
from build_runtime import BuildStop


class FakeSDK:
    def __init__(self): self.chat=self.completions=self;self.calls=0
    def create(self,**request):
        self.calls+=1
        return SimpleNamespace(id=f'fake-{self.calls}',model='fake',usage=SimpleNamespace(model_dump=lambda:dict(prompt_tokens=1,completion_tokens=1,total_tokens=2)),choices=[SimpleNamespace(message=SimpleNamespace(content='FAKE TEST ONLY'),finish_reason='stop')])


class EvaluationChecks(unittest.TestCase):
    def setUp(self):
        # Exercise the real reservation arithmetic without requiring downloaded
        # tokenizer files. Official-tokenizer audits remain archived evidence.
        class FakeTokenizer:
            def apply_chat_template(self, messages, **kwargs):
                if kwargs.get('truncation') is not False:
                    raise AssertionError('Offline check must preserve full input')
                return list(json.dumps(messages, ensure_ascii=False).encode())
        loader = patch('transformers.AutoTokenizer.from_pretrained', return_value=FakeTokenizer())
        loader.start()
        self.addCleanup(loader.stop)

    def test_frozen_selection_and_copies(self):
        questions,manifest=verified_questions(); indices=audit_selection()
        self.assertEqual(len(questions),25)
        self.assertEqual(indices,manifest['selected_qa_indices_zero_based'])
        snapshot,meta,_=verified_snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            clone_memory(snapshot,a,meta);clone_memory(snapshot,b,meta)
            (a/'short.json').write_text('["changed only this copy"]')
            check_memory_files(b,meta);verified_snapshot()
            with self.assertRaises(BuildStop):check_memory_files(a,meta)

    def test_exactly450_fresh_requests_and_no_memory_write(self):
        questions,_=verified_questions(); spec=fixed_spec(); sdk=FakeSDK()
        snapshot,manifest,_=verified_snapshot()
        class EmptyShort:
            def get_all(self): return []
        class FakeRetrieval:
            def __init__(self,client):self.client=client
            def retrieve(self,question,**kw):
                self.client.chat_completion([{'role':'user','content':'keyword '+question}])
                p={'page_id':'same-id','user_input':'public dialogue','agent_response':'public reply','timestamp':'date','meta_info':'meta'}
                return {'retrieval_queue':[p,p],'long_term_knowledge':[]}
        def load(path,k,client):return EmptyShort(),object(),object(),FakeRetrieval(client)
        def generate(question,short,long,pages,knowledge,client,sample,a,b,metadata):
            self.assertEqual(metadata,{})
            answer=client.chat_completion([{'role':'user','content':'answer '+question}])
            return answer,'system prompt without references','question only'
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);client=EvaluationClient(directory,'fake',sdk,450,budget_cny=20)
            with patch('run_evaluation.load_trial',side_effect=load),patch('main_loco_parse.generate_system_response_with_meta',side_effect=generate),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(execute_trials(directory,None,spec,questions,client),225)
            self.assertEqual(sdk.calls,450)
            starts=[e for e in client.events if e['event']=='started']
            self.assertEqual(len({e['operation'] for e in starts}),450)
            for repeat,expected in ((1,[5,5,10,10,20,20]),(2,[10,10,20,20,5,5]),(3,[20,20,5,5,10,10])):
                self.assertEqual([e['capacity'] for e in starts[(repeat-1)*150:(repeat-1)*150+6]],expected)
            self.assertEqual(sum(e['stage']=='answer' for e in starts),225)
            self.assertEqual(sum(e['stage']=='retrieval_keywords' for e in starts),225)
            rows=[json.loads(p.read_text()) for p in directory.glob('k*-r*/q*.json')]
            self.assertEqual(len(rows),225)
            self.assertTrue(all(r['retrieval']['actual_pages']==2 and r['retrieval']['unique_page_ids']==1 for r in rows))
            self.assertTrue(all('original_answer' not in r and 'evidence' not in r for r in rows))
            for job in directory.glob('k*-r*'):check_memory_files(job/'memory',manifest)
            client.begin_page(225)
            with self.assertRaises(BuildStop):client.chat_completion([{'role':'user','content':'exceeds budget'}])
            self.assertEqual(sdk.calls,450)

    def test_score_std_is_across3_trials_and_upstream_f1(self):
        questions,_=verified_questions(); categories=[1]*6+[2]*6+[3]*6+[4]*7
        refs={q['question_id']:{'answer':'a b','category':c} for q,c in zip(questions,categories)}
        rows=[]
        for k in (5,10,20):
            for repeat in (1,2,3):
                for q in questions:
                    rows.append({'capacity':k,'repeat':repeat,'question_id':q['question_id'],'system_answer':{1:'',2:'a',3:'a b'}[repeat],'usage_including_keywords':dict(prompt_tokens=1,completion_tokens=1,total_tokens=2),'elapsed_seconds':1,'retrieval':{'actual_pages':k,'unique_page_ids':k}})
        result=aggregate(rows,refs)
        expected=[0,2/3,1]
        for group in result['groups'].values():
            self.assertAlmostEqual(group['mean_f1'],statistics.mean(expected))
            self.assertAlmostEqual(group['sample_std_across_3_run_means'],statistics.stdev(expected))
            self.assertEqual(len(group['categories']),4)
        with self.assertRaises(BuildStop):aggregate(rows[:-1],refs)
        with self.assertRaises(BuildStop):aggregate(rows[:-1]+[rows[0]],refs)

    def test_full_input_reservation_and_money_stop(self):
        from evaluation_budget import InputReservation
        counter=InputReservation()
        messages=[{'role':'system','content':'system'},{'role':'user','content':('full untrimmed content '*3000)+'TAIL_MUST_REMAIN'}]
        before=json.dumps(messages)
        estimate=counter.estimate('fake',messages,.7,2000)
        self.assertEqual(json.dumps(messages),before)
        self.assertGreater(estimate['full_request_utf8_bytes'],len(messages[1]['content']))
        self.assertGreaterEqual(estimate['reserved_input_tokens'],estimate['full_request_utf8_bytes']+1024)
        self.assertEqual(estimate['reserved_cost_micro_cny'],estimate['reserved_input_tokens']*2+2000*8)
        short=[{'role':'user','content':'short'}]
        short_estimate=counter.estimate('fake',short,.7,2000)
        with tempfile.TemporaryDirectory() as tmp:
            sdk=FakeSDK(); budget=f"{short_estimate['reserved_cost_micro_cny']/1000000:.6f}"
            client=EvaluationClient(Path(tmp),'fake',sdk,450,budget_cny=budget)
            client.begin_page(0);client.chat_completion(short)
            client.begin_page(1)
            with self.assertRaises(BuildStop):client.chat_completion(short)
            self.assertEqual(sdk.calls,1)

    def test_truncation_is_explicit_failed_question(self):
        class TruncatedSDK(FakeSDK):
            def create(self,**request):
                response=super().create(**request)
                response.choices[0].finish_reason='length'
                return response
        class Short:
            def get_all(self):return []
        class Retriever:
            def __init__(self,c):self.c=c
            def retrieve(self,*a,**k):self.c.chat_completion([{'role':'user','content':'keyword'}])
        questions,_=verified_questions();spec=fixed_spec()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);sdk=TruncatedSDK();client=EvaluationClient(directory,'fake',sdk,450,budget_cny=20)
            with patch('run_evaluation.load_trial',side_effect=lambda path,k,c:(Short(),None,None,Retriever(c))),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(BuildStop):execute_trials(directory,None,spec,questions,client)
            failed=list(directory.glob('k*-r*/q*.failed.json'))
            self.assertEqual(len(failed),1)
            row=json.loads(failed[0].read_text())
            self.assertFalse(row['valid_answer']);self.assertEqual(row['failure_kind'],'truncated')
            self.assertEqual(sdk.calls,1)
            self.assertFalse(list(directory.glob('k*-r*/q00.json')))

    def test_preview_never_constructs_client_or_run_directory(self):
        from run_evaluation import main
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'must-not-exist'
            args=['run_evaluation.py','--prepared',str(ROOT/'runs/eval-prepared-conv26-v1'),'--run-dir',str(target)]
            with patch('sys.argv',args),patch('utils.OpenAIClient',side_effect=AssertionError('No client in preview')),contextlib.redirect_stdout(io.StringIO()) as text:
                main()
            self.assertEqual(json.loads(text.getvalue())['mode'],'preview_no_api')
            self.assertFalse(target.exists())


def forbidden(*a,**k):raise AssertionError('No network in offline evaluation checks')


if __name__=='__main__':
    with patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden):
        unittest.main(verbosity=2)
