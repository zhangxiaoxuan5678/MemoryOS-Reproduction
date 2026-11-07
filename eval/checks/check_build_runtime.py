"""Fault-injection checks with fake SDK/embeddings; all artifacts are temporary."""
import contextlib
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
from build_runtime import (BuildStop, LedgerClient, atomic_json, coverage,
                           validate_themes, verify_checkpoint)
from build_study import build_pages, publish_snapshot


class FakeSDK:
    def __init__(self, fail=False):
        self.chat = self.completions = self
        self.calls, self.fail = 0, fail

    def create(self, **request):
        self.calls += 1
        if self.fail:
            raise TimeoutError('FAKE ONLY')
        system = request['messages'][0]['content'].lower()
        if 'continuity detector' in system:
            answer = 'false'
        elif 'meta-summary updater' in system:
            answer = 'mock meta'
        elif 'analyzing dialogue topics' in system:
            answer = '[{"theme":"mock","content":"mock topic","keywords":["mock"]}]'
        elif 'keyword extraction expert' in system:
            answer = 'mock'
        elif 'personality and user data analysis engine' in system:
            answer = '【User Profile】\nmock profile\n【User Data】\n- None'
        elif 'assistant knowledge extraction engine' in system:
            answer = '【Assistant Knowledge】\nNone'
        elif 'profile integration system' in system:
            answer = 'mock profile'
        else:
            answer = 'mock response'
        return SimpleNamespace(id='fake', model='fake', usage=SimpleNamespace(model_dump=lambda: dict(prompt_tokens=3, completion_tokens=3, total_tokens=6)), choices=[SimpleNamespace(message=SimpleNamespace(content=answer), finish_reason='stop')])


def pages(count=2):
    return [{'user_input': f'turn {i}', 'agent_response': 'response', 'timestamp': '2023-01-01 10:00:00', 'session_key': 'session_1', 'source_turns': [{'index': i, 'speaker': 'A', 'dia_id': str(i)}]} for i in range(count)]


class BuildChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_budget_replay_and_failed_request(self):
        sdk = FakeSDK()
        client = LedgerClient(self.directory, 'fake', sdk, 1)
        client.begin_page(0)
        client.chat_completion([{'content': 'fake'}])
        restored = LedgerClient(self.directory, 'fake', sdk, 1)
        restored.begin_page(0)
        restored.chat_completion([{'content': 'fake'}])
        self.assertEqual(sdk.calls, 1)
        with self.assertRaises(BuildStop):
            restored.chat_completion([{'content': 'new'}])
        self.assertEqual(sdk.calls, 1)
        self.assertEqual(restored.totals()['known_usage']['total_tokens'], 6)
        restored.begin_page(0)
        with self.assertRaises(BuildStop):
            restored.chat_completion([{'content': 'changed'}])
        fail_dir = self.directory / 'failure'
        fail_dir.mkdir()
        sdk = FakeSDK(fail=True)
        client = LedgerClient(fail_dir, 'fake', sdk, 10)
        client.begin_page(0)
        with self.assertRaises(BuildStop):
            client.chat_completion([{'content': 'fake'}])
        restored = LedgerClient(fail_dir, 'fake', sdk, 10)
        restored.begin_page(0)
        with self.assertRaises(BuildStop):
            restored.chat_completion([{'content': 'fake'}])
        self.assertEqual(sdk.calls, 1)
        self.assertEqual(restored.totals()['requests_with_unknown_usage'], 1)

    def test_missing_response_and_corrupt_ledger(self):
        client = LedgerClient(self.directory, 'fake', FakeSDK(), 10)
        # Interrupt before SDK response: never retry the ambiguous operation.
        client.append({'event': 'started', 'index': 1, 'operation': 'page:0:call:1', 'fingerprint': 'unknown', 'model': 'fake'})
        restored = LedgerClient(self.directory, 'fake', FakeSDK(), 10)
        self.assertEqual(restored.count, 1)
        self.assertEqual(restored.totals()['requests_with_unknown_usage'], 1)
        with (self.directory / 'calls.jsonl').open('a') as f:
            f.write('{broken')
        with self.assertRaises(json.JSONDecodeError):
            LedgerClient(self.directory, 'fake', FakeSDK(), 10)

    def test_money_reservation_and_restore(self):
        sdk = FakeSDK()
        client = LedgerClient(self.directory, 'fake', sdk, 1200, budget_cny='2.113160')
        client.begin_page(0)
        client.chat_completion([{'content': 'fake'}])
        self.assertEqual(client.totals()['estimated_peak_cny'], '0.000030')
        with self.assertRaises(BuildStop):
            client.chat_completion([{'content': 'new'}])
        self.assertEqual(sdk.calls, 1)
        restored = LedgerClient(self.directory, 'fake', sdk, 1200, budget_cny='2.113160')
        restored.begin_page(0)
        restored.chat_completion([{'content': 'fake'}])
        with self.assertRaises(BuildStop):
            restored.chat_completion([{'content': 'new'}])
        self.assertEqual(sdk.calls, 1)
        empty = self.directory / 'too-small'; empty.mkdir()
        tiny = LedgerClient(empty, 'fake', sdk, 1200, budget_cny='2')
        tiny.begin_page(0)
        with self.assertRaises(BuildStop):
            tiny.chat_completion([{'content': 'fake'}])
        self.assertEqual(tiny.count, 0)
        failure = self.directory / 'unknown'; failure.mkdir()
        unknown = LedgerClient(failure, 'fake', FakeSDK(fail=True), 1200, budget_cny='10')
        unknown.begin_page(0)
        with self.assertRaises(BuildStop):
            unknown.chat_completion([{'content': 'fake'}])
        self.assertEqual(unknown.totals()['unsettled_reserved_cny'], '2.113152')

    def test_explicit_truncated_retry_is_once_and_cumulative(self):
        import hashlib
        for truncate_again in (False, True):
            directory = self.directory / str(truncate_again); directory.mkdir()
            class TruncatingSDK(FakeSDK):
                def create(self, **request):
                    response = super().create(**request)
                    if self.calls == 1 or truncate_again:
                        response.choices[0].finish_reason = 'length'
                    return response
            sdk = TruncatingSDK()
            original = LedgerClient(directory, 'fake', sdk, 1200, budget_cny=10)
            original.begin_page(67)
            with self.assertRaises(BuildStop):
                original.chat_completion([{'content': 'fake'}], max_tokens=100)
            retry = LedgerClient(directory, 'fake', sdk, 1200, budget_cny=10)
            retry.begin_page(67)
            with self.assertRaises(BuildStop):
                retry.chat_completion([{'content': 'fake'}], max_tokens=300)
            request = dict(model='fake', messages=[{'content':'fake'}], temperature=0.7, max_tokens=300, thinking='disabled')
            fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            atomic_json(directory / 'retry-authorizations.json', [{'retry_of':1,'operation':'page:67:call:1','new_fingerprint':fingerprint}])
            retry.begin_page(67)
            if truncate_again:
                with self.assertRaises(BuildStop):
                    retry.chat_completion([{'content':'fake'}], max_tokens=300)
            else:
                retry.chat_completion([{'content':'fake'}], max_tokens=300)
            self.assertEqual(sdk.calls, 2)
            restored = LedgerClient(directory, 'fake', sdk, 1200, budget_cny=10)
            self.assertEqual(restored.totals()['known_usage']['total_tokens'], 12)
            restored.begin_page(67)
            if truncate_again:
                with self.assertRaises(BuildStop):
                    restored.chat_completion([{'content':'fake'}], max_tokens=300)
            else:
                restored.chat_completion([{'content':'fake'}], max_tokens=300)
            self.assertEqual(sdk.calls, 2)

    def test_profile4000_scope_and_reservation(self):
        sdk = FakeSDK()
        messages = [{'role':'system','content':'You are a profile integration system. Your rules:'}]
        tiny = LedgerClient(self.directory, 'fake', sdk, 1200, budget_cny='2.12')
        tiny.begin_page(77)
        with self.assertRaises(BuildStop):
            tiny.chat_completion(messages, max_tokens=4000)
        self.assertEqual(sdk.calls, 0)
        client = LedgerClient(self.directory, 'fake', sdk, 1200, budget_cny=10)
        client.begin_page(77)
        with self.assertRaises(BuildStop):
            client.chat_completion([{'content':'Other task'}], max_tokens=4000)
        client.begin_page(77)
        client.chat_completion(messages, max_tokens=4000)
        start = next(e for e in client.events if e['event']=='started')
        self.assertEqual(start['reserved_output_tokens'], 4000)
        self.assertEqual(start['reserved_cost_micro_cny'], 2129152)
        self.assertEqual(client.count, 1)

    def test_profile16000_reservation_and_one_time_retry(self):
        import hashlib
        messages=[{'role':'system','content':'You are a profile integration system. Your rules:'}]
        class OnceTruncated(FakeSDK):
            def create(self, **request):
                response=super().create(**request)
                if self.calls==1: response.choices[0].finish_reason='length'
                return response
        sdk=OnceTruncated()
        client=LedgerClient(self.directory,'fake',sdk,1200,budget_cny=10)
        client.begin_page(141)
        with self.assertRaises(BuildStop): client.chat_completion(messages,max_tokens=4000)
        restored=LedgerClient(self.directory,'fake',sdk,1200,budget_cny=10)
        restored.begin_page(141)
        with self.assertRaises(BuildStop): restored.chat_completion(messages,max_tokens=16000)
        request=dict(model='fake',messages=messages,temperature=0.7,max_tokens=16000,thinking='disabled')
        fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        atomic_json(self.directory/'retry-authorizations.json',[{'retry_of':1,'operation':'page:141:call:1','new_fingerprint':fingerprint}])
        restored.begin_page(141); restored.chat_completion(messages,max_tokens=16000)
        last=[e for e in restored.events if e['event']=='started'][-1]
        self.assertEqual(last['reserved_output_tokens'],16000)
        self.assertEqual(last['reserved_cost_micro_cny'],2225152)
        self.assertEqual(restored.count,2)
        self.assertEqual(restored.totals()['known_usage']['total_tokens'],12)
        again=LedgerClient(self.directory,'fake',sdk,1200,budget_cny=10)
        again.begin_page(141); again.chat_completion(messages,max_tokens=16000)
        self.assertEqual(sdk.calls,2)
        too_small=self.directory/'too-small'; too_small.mkdir()
        limited=LedgerClient(too_small,'fake',sdk,1200,budget_cny='2.2')
        limited.begin_page(0)
        with self.assertRaises(BuildStop): limited.chat_completion(messages,max_tokens=16000)
        self.assertEqual(limited.count,0)

    def test_theme_validation(self):
        for bad in ({'summaries': []}, {'summaries': [{}]}, {'summaries': [dict(theme='x', content='x', keywords=[])]}):
            with self.assertRaises(BuildStop):
                validate_themes(bad)

    def test_crash_after_paid_response_then_resume(self):
        sdk = FakeSDK()
        class Interrupt(LedgerClient):
            def chat_completion(self, *a, **k):
                answer = super().chat_completion(*a, **k)
                if self.count == 3:
                    raise OSError('Injected interruption after durable response')
                return answer
        client = Interrupt(self.directory, 'fake', sdk, 100)
        with self.assertRaises(OSError):
            build_pages(self.directory, pages(), client, 'test')
        state = json.loads((self.directory / 'checkpoint.json').read_text())
        self.assertEqual(state['completed_pages'], 0)
        resumed = LedgerClient(self.directory, 'fake', sdk, 100)
        final = build_pages(self.directory, pages(), resumed, 'test', state)
        # Page 1 = meta + themes + 2 keywords; page 2 = continuity + meta + themes.
        self.assertEqual(sdk.calls, 7)
        self.assertEqual(resumed.count, 7)
        self.assertEqual(final['completed_pages'], 2)
        self.assertEqual(final['coverage']['unique_pages'], 2)
        publish_snapshot(self.directory, final, {'fake': True})
        publish_snapshot(self.directory, final, {'fake': True})
        snapshot = self.directory / 'snapshot'
        (snapshot / 'short.json').chmod(0o644)
        (snapshot / 'short.json').write_text('["tampered"]')
        with self.assertRaises(BuildStop):
            publish_snapshot(self.directory, final, {'fake': True})
        snapshot.chmod(0o755)
        for p in snapshot.iterdir():
            p.chmod(0o644)

    def test_orphaned_checkpoint_recovery_uses_no_new_requests(self):
        sdk = FakeSDK()
        client = LedgerClient(self.directory, 'fake', sdk, 100)
        build_pages(self.directory, pages(), client, 'test')
        initial = self.directory / 'checkpoints/page-0000'
        from build_runtime import MEMORY_FILES, digest
        state = {'completed_pages': 0, 'checkpoint': 'checkpoints/page-0000', 'files_sha256': {n: digest(initial / n) for n in MEMORY_FILES}}
        atomic_json(self.directory / 'checkpoint.json', state)
        restored = LedgerClient(self.directory, 'fake', sdk, 100)
        result = build_pages(self.directory, pages(), restored, 'test', state)
        self.assertEqual(result['completed_pages'], 2)
        self.assertEqual(sdk.calls, 7)
        self.assertEqual(len(list((self.directory / 'abandoned').iterdir())), 2)

    def test_budget_stop_is_not_a_complete_page(self):
        sdk = FakeSDK()
        client = LedgerClient(self.directory, 'fake', sdk, 2)
        with self.assertRaises(BuildStop):
            build_pages(self.directory, pages(), client, 'test')
        state = json.loads((self.directory / 'checkpoint.json').read_text())
        self.assertEqual(state['completed_pages'], 0)
        self.assertEqual(sdk.calls, 2)
        self.assertFalse((self.directory / 'snapshot').exists())
        cp = verify_checkpoint(self.directory, state)
        (cp / 'short.json').write_text('["tampered"]')
        with self.assertRaises(BuildStop):
            verify_checkpoint(self.directory, state)

    def test_profile_checkpoint_and_full_coverage(self):
        sdk = FakeSDK()
        client = LedgerClient(self.directory, 'fake', sdk, 100)
        state = build_pages(self.directory, pages(8), client, 'test')
        cp = verify_checkpoint(self.directory, state)
        self.assertTrue(json.loads((cp / 'long.json').read_text())['user_profiles'])
        data = json.loads((cp / 'mid.json').read_text())
        self.assertEqual(coverage(data, pages(8))['unique_pages'], 8)
        with self.assertRaises(BuildStop):
            coverage(data, pages(7))


def forbidden(*a, **k):
    raise AssertionError('Network forbidden in build checks')


if __name__ == '__main__':
    import numpy as np
    import utils, mid_term_memory, long_term_memory
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect', forbidden))
        stack.enter_context(patch.object(socket, 'create_connection', forbidden))
        for module in (utils, mid_term_memory, long_term_memory):
            stack.enter_context(patch.object(module, 'get_embedding', lambda *a, **k: np.array([1., 0.], dtype=np.float32)))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        unittest.main(verbosity=2)
