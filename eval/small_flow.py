"""Authorized bounded connectivity + one-page real MemoryOS smoke. Not an evaluation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import contextlib
import fcntl

ROOT = Path(__file__).resolve().parent.parent

class RequestLimit(RuntimeError):
    pass

class BudgetClient:
    def __init__(self, directory):
        from utils import OpenAIClient
        configured = OpenAIClient()
        self.model = configured.model
        self.sdk = configured.client.with_options(max_retries=0, timeout=30)
        self.directory = directory
        self.count = 0
        self.stage = 'connectivity'
        self.tokens = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        self.unknown_usage = 0
        log = directory / 'calls.jsonl'
        events = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        started = [e for e in events if e['event'] == 'request_started']
        if started and any(e['model'] != self.model for e in started):
            raise ValueError('Resume requires the same configured model')
        self.count = len(started)
        assert [e['index'] for e in started] == list(range(1, self.count + 1)), 'Invalid request ledger'
        responses = {e['index']: e for e in events if e['event'] == 'response'}
        for event in started:
            usage = responses.get(event['index'], {}).get('usage')
            if usage:
                for key in self.tokens:
                    self.tokens[key] += usage.get(key, 0) or 0
            else:
                self.unknown_usage += 1

    def event(self, data):
        with (self.directory / 'calls.jsonl').open('a') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def chat_completion(self, messages, temperature=0.7, max_tokens=2000):
        if self.count >= 10:
            raise RequestLimit('Shared limit of 10 requests reached')
        self.count += 1
        index = self.count
        self.event({'event': 'request_started', 'index': index, 'stage': self.stage, 'utc': datetime.now(timezone.utc).isoformat(), 'model': self.model, 'temperature': temperature, 'max_tokens': max_tokens, 'thinking': 'disabled', 'messages': messages})
        try:
            result = self.sdk.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens, extra_body={'thinking': {'type': 'disabled'}})
        except Exception as error:
            self.unknown_usage += 1
            self.event({'event': 'request_failed', 'index': index, 'error_type': type(error).__name__, 'http_status': getattr(error, 'status_code', None), 'usage': None})
            raise RuntimeError('API request failed; safe error details in calls.jsonl') from None
        usage = result.usage.model_dump() if result.usage else None
        if usage:
            for key in self.tokens:
                self.tokens[key] += usage.get(key, 0) or 0
        else:
            self.unknown_usage += 1
        answer = result.choices[0].message.content
        self.event({'event': 'response', 'index': index, 'response_id': result.id, 'returned_model': result.model, 'finish_reason': result.choices[0].finish_reason, 'answer': answer, 'usage': usage})
        if not answer or result.choices[0].finish_reason == 'length':
            raise RuntimeError('Empty or truncated response; no automatic retry')
        return answer.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid', action='store_true')
    parser.add_argument('--resume-dir', type=Path)
    parser.add_argument('--embedding-path', type=Path, help='Downloaded original model snapshot; loaded locally only')
    args = parser.parse_args()
    if not args.allow_paid:
        parser.error('Explicit authorization required; no request made')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    previous = {}
    if args.resume_dir:
        directory = args.resume_dir.resolve()
        if directory.parent != (ROOT / 'runs').resolve():
            parser.error('Resume directory must be a direct child of repository runs/')
        lock = (directory / '.run.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        previous = json.loads((directory / 'summary.json').read_text())
        if previous.get('status') != 'stopped' or previous.get('stopped_stage') not in ('local_embedding_preflight', 'one_question_retrieval'):
            parser.error('This checkpoint cannot be resumed safely')
        if previous['stopped_stage'] == 'local_embedding_preflight' and any((directory / name).exists() for name in ('short.json', 'mid.json', 'long.json')):
            parser.error('Refusing to append to existing memory')
        if previous['stopped_stage'] == 'one_question_retrieval' and not (directory / 'mid.json').exists():
            parser.error('Retrieval resume requires saved mid-term memory')
        (directory / ('summary-before-resume-' + stamp + '.json')).write_text(json.dumps(previous, ensure_ascii=False, indent=2) + '\n')
    else:
        directory = ROOT / 'runs' / ('small-flow-' + stamp)
        directory.mkdir(parents=True, exist_ok=False)
        lock = (directory / '.run.lock').open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    summary = {'kind': 'small_flow_not_experiment', 'request_limit_including_connectivity': 10, 'sdk_retries': 0, 'max_tokens_per_pipeline_request': 2000, 'embedding_downloads': False, 'status': 'preparing', 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'eval').rglob('*.py')}}
    if args.embedding_path:
        summary['embedding_snapshot'] = str(args.embedding_path.resolve())
    client = None
    try:
        client = BudgetClient(directory)
        summary['configured_model'] = client.model
        summary['connectivity_answer'] = previous.get('connectivity_answer') or client.chat_completion([{'role': 'user', 'content': 'Reply with OK only.'}], temperature=0, max_tokens=128)
        print('Connectivity reused' if previous.get('connectivity_answer') else 'Connectivity completed', '; cumulative requests:', client.count, flush=True)
        import utils
        # Preserve the embedding model/encoding, but never fetch missing files.
        original_factory = utils.SentenceTransformer
        utils.SentenceTransformer = lambda name: original_factory(str(args.embedding_path.resolve()) if args.embedding_path else name, local_files_only=True)
        utils._get_embedding_model.cache_clear()
        client.stage = 'local_embedding_preflight'
        utils.get_embedding('offline cache check')
        from main_loco_parse import process_conversation, update_user_profile_from_top_segment, generate_system_response_with_meta
        from short_term_memory import ShortTermMemory
        from mid_term_memory import MidTermMemory
        from long_term_memory import LongTermMemory
        from dynamic_update import DynamicUpdate
        from retrieval_and_answer import RetrievalAndAnswer
        sample = next(s for s in json.loads((ROOT / 'eval/locomo10.json').read_text()) if s['sample_id'] == 'conv-26')
        page = next(p for p in process_conversation(sample['conversation']) if p['user_input'] and p['agent_response'])
        summary['scope'] = 'First eligible conversation page only; one question derived from this page, not benchmark QA'
        short = ShortTermMemory(max_capacity=1, file_path=str(directory / 'short.json'))
        mid = MidTermMemory(max_capacity=2000, file_path=str(directory / 'mid.json'), client=client)
        long = LongTermMemory(file_path=str(directory / 'long.json'))
        updater = DynamicUpdate(short, mid, long, topic_similarity_threshold=0.6, client=client)
        retriever = RetrievalAndAnswer(short, mid, long, updater, queue_capacity=10)
        client.stage = 'one_page_build'
        with (directory / 'flow.log').open('a') as output, contextlib.redirect_stdout(output):
            print('Resume checkpoint:', previous.get('stopped_stage', 'fresh'))
            if previous.get('stopped_stage') != 'one_question_retrieval':
                short.add_qa_pair(page)
                updater.bulk_evict_and_update_mid_term()
                update_user_profile_from_top_segment(mid, long, sample['sample_id'], client)
            if not mid.sessions:
                raise RuntimeError('No sessions built; inspect raw theme response')
            client.stage = 'one_question_retrieval'
            question = 'What did ' + sample['conversation']['speaker_a'] + ' say in this conversation?'
            retrieved = retriever.retrieve(question, segment_threshold=0.1, page_threshold=0.1, knowledge_threshold=0.1, client=client)
            summary['retrieved_pages'] = len(retrieved['retrieval_queue'])
            client.stage = 'one_question_answer'
            answer, system, user = generate_system_response_with_meta(question, short, long, retrieved['retrieval_queue'], retrieved['long_term_knowledge'], client, sample['sample_id'], sample['conversation']['speaker_a'], sample['conversation']['speaker_b'], {})
            (directory / 'answer.json').write_text(json.dumps({'question': question, 'answer': answer, 'system_prompt': system, 'user_prompt': user, 'benchmark_score': None}, ensure_ascii=False, indent=2))
        summary['status'] = 'completed'
    except Exception as error:
        summary.update(status='stopped', error_type=type(error).__name__, stopped_stage=client.stage if client else 'configuration')
        # Never print/store SDK exception strings or credential values.
    finally:
        if client:
            summary.update(requests_started=client.count, known_token_usage=client.tokens, requests_with_unknown_usage=client.unknown_usage)
        (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        print('Summary:', directory / 'summary.json', flush=True)
        print(json.dumps({k:v for k,v in summary.items() if k not in ['source_sha256']},ensure_ascii=False),flush=True)

if __name__ == '__main__':
    main()
