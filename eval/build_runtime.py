"""Durable budget ledger and atomic checkpoints. No model imports at import time."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


class BuildStop(RuntimeError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


class LedgerClient:
    """Single-process owner must hold the run lock. Successes replay on page rollback."""
    def __init__(self, directory, model, sdk, limit, budget_cny=None):
        if limit < 1:
            raise BuildStop('Positive request limit required')
        from decimal import Decimal
        self.budget_micro = int(Decimal(str(budget_cny)) * 1_000_000) if budget_cny is not None else None
        if self.budget_micro is not None and self.budget_micro <= 0:
            raise BuildStop('Positive CNY budget required')
        self.path = Path(directory) / 'calls.jsonl'
        self.model, self.sdk, self.limit = model, sdk, limit
        self.events = [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []
        starts = [e for e in self.events if e['event'] == 'started']
        if [e['index'] for e in starts] != list(range(1, len(starts) + 1)):
            raise BuildStop('Invalid request ledger')
        if any(e['model'] != model for e in starts):
            raise BuildStop('Configured model differs from ledger')
        self.count = len(starts)
        self.page, self.ordinal = None, 0

    def begin_page(self, number):
        self.page, self.ordinal = number, 0

    def append(self, event):
        with self.path.open('a') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
            f.flush()
            os.fsync(f.fileno())
        self.events.append(event)

    def money(self):
        responses = {e['index']: e for e in self.events if e['event'] == 'response'}
        settled, reserved = 0, 0
        for start in (e for e in self.events if e['event'] == 'started'):
            usage = responses.get(start['index'], {}).get('usage')
            if usage is not None and all(isinstance(usage.get(k), int) and usage[k] >= 0 for k in ('prompt_tokens', 'completion_tokens')):
                settled += usage['prompt_tokens'] * 2 + usage['completion_tokens'] * 8
            else:
                reserved += start.get('reserved_cost_micro_cny', 2_113_152)
        return settled, reserved

    def totals(self):
        responses = {e['index']: e for e in self.events if e['event'] == 'response'}
        sums = dict(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        unknown = 0
        for start in (e for e in self.events if e['event'] == 'started'):
            usage = responses.get(start['index'], {}).get('usage')
            if usage is None:
                unknown += 1
            else:
                for key in sums:
                    sums[key] += usage.get(key, 0) or 0
        settled, reserved = self.money()
        return {'requests_started': self.count, 'known_usage': sums, 'requests_with_unknown_usage': unknown, 'estimated_peak_cny': f'{settled / 1000000:.6f}', 'unsettled_reserved_cny': f'{reserved / 1000000:.6f}', 'budget_cny': f'{self.budget_micro / 1000000:.6f}' if self.budget_micro is not None else None}

    def chat_completion(self, messages, temperature=0.7, max_tokens=2000):
        if self.page is None or not 0 < max_tokens <= 16000:
            raise BuildStop('Invalid request scope or output limit')
        if max_tokens > 2000 and not (messages and messages[0].get('content', '').startswith('You are a profile integration system.')):
            raise BuildStop('Only long-term profile merge is allowed 16000 tokens')
        self.ordinal += 1
        operation = f'page:{self.page}:call:{self.ordinal}'
        request = {'model': self.model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens, 'thinking': 'disabled'}
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        previous = [e for e in self.events if e['event'] == 'started' and e['operation'] == operation]
        retry_of = None
        if previous:
            start = previous[-1]
            response = next((e for e in self.events if e['event'] == 'response' and e['index'] == start['index']), None)
            if start['fingerprint'] == fingerprint:
                if response is None:
                    raise BuildStop('Prior request failed or outcome unknown; no automatic retry')
                return self.checked_answer(response)
            auth_path = self.path.parent / 'retry-authorizations.json'
            authorizations = json.loads(auth_path.read_text()) if auth_path.exists() else []
            allowed = next((a for a in authorizations if a['retry_of'] == start['index'] and a['operation'] == operation and a['new_fingerprint'] == fingerprint), None)
            used = any(e.get('retry_of') == start['index'] for e in self.events if e['event'] == 'started')
            if not allowed or used or response is None or response['finish_reason'] != 'length':
                raise BuildStop('Request changed without unused explicit truncated-response authorization')
            retry_of = start['index']
        if self.count >= self.limit:
            raise BuildStop('Request budget exhausted before sending')
        # DeepSeek documents 1M context. Reserve 2^20 input tokens to cover
        # either decimal/binary interpretation, plus 2000 output tokens.
        output_reservation = max(2000, max_tokens)
        reservation = 1_048_576 * 2 + output_reservation * 8
        settled, reserved = self.money()
        if self.budget_micro is not None and settled + reserved + reservation > self.budget_micro:
            raise BuildStop('CNY budget insufficient for conservative next-request reservation')
        if reserved:
            raise BuildStop('Unsettled request exists; no automatic retry or further spending')
        self.count += 1
        self.append({'event': 'started', 'index': self.count, 'operation': operation, 'retry_of': retry_of, 'fingerprint': fingerprint, 'reserved_cost_micro_cny': reservation, 'reserved_input_tokens': 1_048_576, 'reserved_output_tokens': output_reservation, 'input_text_utf8_bytes': sum(len(m['content'].encode()) for m in messages), 'utc': datetime.now(timezone.utc).isoformat(), **request})
        try:
            result = self.sdk.chat.completions.create(model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens, extra_body={'thinking': {'type': 'disabled'}})
        except Exception as error:
            self.append({'event': 'failed', 'index': self.count, 'error_type': type(error).__name__, 'http_status': getattr(error, 'status_code', None)})
            raise BuildStop('API failed; safe metadata retained, no retry') from None
        response = {'event': 'response', 'index': self.count, 'response_id': result.id, 'returned_model': result.model, 'usage': result.usage.model_dump() if result.usage else None, 'answer': result.choices[0].message.content, 'finish_reason': result.choices[0].finish_reason}
        self.append(response)
        if response['usage'] is None:
            raise BuildStop('Usage missing; full reservation retained, stopping')
        if response['usage'].get('prompt_tokens', 1_048_577) > 1_048_576 or response['usage'].get('completion_tokens', output_reservation + 1) > output_reservation:
            raise BuildStop('Provider usage exceeded documented reservation; stop')
        return self.checked_answer(response)

    @staticmethod
    def checked_answer(response):
        answer = response['answer']
        if not isinstance(answer, str) or not answer.strip() or response['finish_reason'] != 'stop':
            raise BuildStop('Empty/incomplete response; no retry')
        return answer.strip()


def validate_themes(result):
    themes = result.get('summaries') if isinstance(result, dict) else None
    if not isinstance(themes, list) or not 1 <= len(themes) <= 2:
        raise BuildStop('Expected one or two valid themes; page not committed')
    for theme in themes:
        if not isinstance(theme, dict) or not all(isinstance(theme.get(k), str) and theme[k].strip() for k in ('theme', 'content')):
            raise BuildStop('Invalid theme fields')
        if not isinstance(theme.get('keywords'), list) or not theme['keywords'] or not all(isinstance(k, str) and k.strip() for k in theme['keywords']):
            raise BuildStop('Invalid theme keywords')
    return result


def coverage(mid_data, pages):
    """Validate unique page content, source-turn identities, and page count."""
    expected = {json.dumps([p['session_key'], p['source_turns']], sort_keys=True): p for p in pages}
    if len(expected) != len(pages):
        raise BuildStop('Input source identities are not unique')
    seen, ids = set(), {}
    for session in mid_data['sessions'].values():
        for page in session['details']:
            key = json.dumps([page.get('session_key'), page.get('source_turns')], sort_keys=True)
            if key not in expected:
                raise BuildStop('Unexpected source page')
            original = expected[key]
            if any(page.get(k) != original[k] for k in ('user_input', 'agent_response', 'timestamp')):
                raise BuildStop('Stored page text or timestamp differs from input')
            if page['page_id'] in ids and ids[page['page_id']] != key:
                raise BuildStop('Page ID collision')
            ids[page['page_id']] = key
            seen.add(key)
    if seen != set(expected) or len(ids) != len(pages):
        raise BuildStop('Incomplete or duplicate unique-page coverage')
    return {'unique_pages': len(ids), 'source_turns': sum(len(p['source_turns']) for p in pages)}


MEMORY_FILES = ('short.json', 'mid.json', 'long.json', 'updater.json')


def verify_checkpoint(directory, state):
    checkpoint = Path(directory) / state['checkpoint']
    if checkpoint.parent != Path(directory) / 'checkpoints':
        raise BuildStop('Invalid checkpoint path')
    for name in MEMORY_FILES:
        if digest(checkpoint / name) != state['files_sha256'][name]:
            raise BuildStop('Checkpoint hash mismatch')
        json.loads((checkpoint / name).read_text())
    return checkpoint


def commit_checkpoint(directory, work, completed, audit, client):
    directory, work = Path(directory), Path(work)
    final = directory / 'checkpoints' / f'page-{completed:04d}'
    if final.exists():
        raise BuildStop('Checkpoint exists; refusing overwrite')
    # Flush complete memory files before publication on the same filesystem.
    for name in MEMORY_FILES:
        with (work / name).open('rb') as f:
            os.fsync(f.fileno())
    os.replace(work, final)
    state = {'completed_pages': completed, 'checkpoint': str(final.relative_to(directory)), 'files_sha256': {name: digest(final / name) for name in MEMORY_FILES}, 'coverage': audit, 'usage': client.totals()}
    atomic_json(directory / 'checkpoint.json', state)
    return state


def apply_meta300_correction(directory, new_config, retry_index):
    """One explicit migration. Preserve original config/logs and budget totals."""
    directory = Path(directory)
    old = json.loads((directory / 'config.json').read_text())
    path = directory / 'config-meta300.json'
    if path.exists():
        if json.loads(path.read_text()) != new_config:
            raise BuildStop('Correction config changed')
        return
    if retry_index != 333:
        raise BuildStop('Only explicitly approved request 333 may be retried')
    for key, value in old.items():
        if key not in ('source_sha256', 'git_commit') and new_config.get(key) != value:
            raise BuildStop('Correction attempted to change unrelated config/budget')
    if new_config.get('meta_summary_max_tokens') != 300:
        raise BuildStop('Correction must set meta summary limit to 300')
    for name, checksum in old['source_sha256'].items():
        if name not in ('build_runtime.py', 'build_study.py', 'dynamic_update.py') and new_config['source_sha256'].get(name) != checksum:
            raise BuildStop('Unrelated source changed during correction')
    state = json.loads((directory / 'checkpoint.json').read_text())
    if state['completed_pages'] != 67:
        raise BuildStop('Correction must resume the audited 67-page checkpoint')
    verify_checkpoint(directory, state)
    events = [json.loads(l) for l in (directory / 'calls.jsonl').read_text().splitlines()]
    starts = [e for e in events if e['event'] == 'started']
    if len(starts) != 333:
        raise BuildStop('Unexpected ledger state for correction')
    start = starts[-1]
    response = next((e for e in events if e['event'] == 'response' and e['index'] == retry_index), None)
    if start['index'] != retry_index or start['operation'] != 'page:67:call:2' or start['max_tokens'] != 100 or response is None or response['finish_reason'] != 'length':
        raise BuildStop('Authorized truncated operation mismatch')
    request = {k: start[k] for k in ('model', 'messages', 'temperature', 'max_tokens', 'thinking')}
    request['max_tokens'] = 300
    new_fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    auth = [{'retry_of': retry_index, 'operation': start['operation'], 'new_fingerprint': new_fingerprint, 'reason': 'Explicit user authorization: meta summary 100 to 300; shared runtime correction, not experimental variable'}]
    atomic_json(directory / 'retry-authorizations.json', auth)
    atomic_json(directory / 'status-before-meta300.json', json.loads((directory / 'status.json').read_text()))
    atomic_json(directory / 'correction-meta300.json', {'old_config_sha256': digest(directory / 'config.json'), 'original_calls_sha256': digest(directory / 'calls.jsonl'), 'original_call_count': 333, 'from_meta_tokens': 100, 'to_meta_tokens': 300, 'scope': 'all experimental groups share corrected runtime', 'old_git_commit': old['git_commit'], 'new_git_commit': new_config['git_commit'], 'authorized_retry': auth[0], 'recorded_utc': datetime.now(timezone.utc).isoformat()})
    atomic_json(path, new_config)


def apply_profile4000_correction(directory, new_config):
    """User-authorized single retry 408, without changing algorithm or prompts."""
    directory = Path(directory)
    old_path = directory / 'config-meta300.json'
    old = json.loads(old_path.read_text())
    path = directory / 'config-profile4000.json'
    if path.exists():
        if json.loads(path.read_text()) != new_config:
            raise BuildStop('Profile correction config changed')
        return
    for key, value in old.items():
        if key not in ('source_sha256', 'git_commit') and new_config.get(key) != value:
            raise BuildStop('Profile correction changed unrelated config/budget')
    if new_config.get('profile_merge_max_tokens') != 4000:
        raise BuildStop('Only profile merge limit 4000 is authorized')
    for name, checksum in old['source_sha256'].items():
        if name not in ('build_runtime.py', 'build_study.py', 'utils.py') and new_config['source_sha256'].get(name) != checksum:
            raise BuildStop('Unrelated source changed during profile correction')
    state = json.loads((directory / 'checkpoint.json').read_text())
    if state['completed_pages'] != 77:
        raise BuildStop('Profile correction requires audited page-77 checkpoint')
    verify_checkpoint(directory, state)
    events = [json.loads(l) for l in (directory / 'calls.jsonl').read_text().splitlines()]
    starts = [e for e in events if e['event'] == 'started']
    if len(starts) != 408:
        raise BuildStop('Profile correction requires 408-request ledger')
    start = starts[-1]
    response = next((e for e in events if e['event'] == 'response' and e['index'] == 408), None)
    if start['index'] != 408 or start['operation'] != 'page:77:call:8' or start['max_tokens'] != 2000 or response is None or response['finish_reason'] != 'length':
        raise BuildStop('Authorized profile operation mismatch')
    if not start['messages'][0]['content'].startswith('You are a profile integration system.'):
        raise BuildStop('Authorized operation is not profile merge')
    request = {k: start[k] for k in ('model', 'messages', 'temperature', 'max_tokens', 'thinking')}
    request['max_tokens'] = 4000
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    auth_path = directory / 'retry-authorizations.json'
    old_auth = json.loads(auth_path.read_text())
    auth = {'retry_of': 408, 'operation': start['operation'], 'new_fingerprint': fingerprint, 'reason': 'Explicit user authorization: profile merge limit 2000 to 4000 only; preserve prompts, algorithm and redundancy evidence'}
    atomic_json(directory / 'retry-authorizations-before-profile4000.json', old_auth)
    atomic_json(auth_path, old_auth + [auth])
    atomic_json(directory / 'status-before-profile4000.json', json.loads((directory / 'status.json').read_text()))
    atomic_json(directory / 'correction-profile4000.json', {'previous_config_sha256': digest(old_path), 'original_calls_sha256': digest(directory / 'calls.jsonl'), 'original_calls_bytes': (directory / 'calls.jsonl').stat().st_size, 'original_call_count': 408, 'from_profile_tokens': 2000, 'to_profile_tokens': 4000, 'scope': 'shared runtime correction; redundancy remains unresolved', 'old_git_commit': old['git_commit'], 'new_git_commit': new_config['git_commit'], 'authorized_retry': auth, 'recorded_utc': datetime.now(timezone.utc).isoformat()})
    atomic_json(path, new_config)


def apply_profile16000_correction(directory, new_config):
    """User-authorized single retry 697, without changing algorithm or prompts."""
    directory = Path(directory)
    old_path = directory / 'config-profile4000.json'
    old = json.loads(old_path.read_text())
    path = directory / 'config-profile16000.json'
    if path.exists():
        if json.loads(path.read_text()) != new_config:
            raise BuildStop('Profile correction config changed')
        return
    for key, value in old.items():
        if key not in ('source_sha256', 'git_commit', 'profile_merge_max_tokens') and new_config.get(key) != value:
            raise BuildStop('Profile correction changed unrelated config/budget')
    if new_config.get('profile_merge_max_tokens') != 16000:
        raise BuildStop('Only profile merge limit 16000 is authorized')
    for name, checksum in old['source_sha256'].items():
        if name not in ('build_runtime.py', 'build_study.py', 'utils.py') and new_config['source_sha256'].get(name) != checksum:
            raise BuildStop('Unrelated source changed during profile correction')
    state = json.loads((directory / 'checkpoint.json').read_text())
    if state['completed_pages'] != 141:
        raise BuildStop('Profile correction requires audited page-141 checkpoint')
    verify_checkpoint(directory, state)
    events = [json.loads(l) for l in (directory / 'calls.jsonl').read_text().splitlines()]
    starts = [e for e in events if e['event'] == 'started']
    if len(starts) != 697:
        raise BuildStop('Profile correction requires 697-request ledger')
    start = starts[-1]
    response = next((e for e in events if e['event'] == 'response' and e['index'] == 697), None)
    if start['index'] != 697 or start['operation'] != 'page:141:call:8' or start['max_tokens'] != 4000 or response is None or response['finish_reason'] != 'length':
        raise BuildStop('Authorized profile operation mismatch')
    if not start['messages'][0]['content'].startswith('You are a profile integration system.'):
        raise BuildStop('Authorized operation is not profile merge')
    request = {k: start[k] for k in ('model', 'messages', 'temperature', 'max_tokens', 'thinking')}
    request['max_tokens'] = 16000
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    auth_path = directory / 'retry-authorizations.json'
    old_auth = json.loads(auth_path.read_text())
    auth = {'retry_of': 697, 'operation': start['operation'], 'new_fingerprint': fingerprint, 'reason': 'Explicit user authorization: profile merge limit 4000 to 16000 only; preserve prompts, algorithm and redundancy evidence'}
    atomic_json(directory / 'retry-authorizations-before-profile16000.json', old_auth)
    atomic_json(auth_path, old_auth + [auth])
    atomic_json(directory / 'status-before-profile16000.json', json.loads((directory / 'status.json').read_text()))
    atomic_json(directory / 'correction-profile16000.json', {'previous_config_sha256': digest(old_path), 'original_calls_sha256': digest(directory / 'calls.jsonl'), 'original_calls_bytes': (directory / 'calls.jsonl').stat().st_size, 'original_call_count': 697, 'from_profile_tokens': 4000, 'to_profile_tokens': 16000, 'scope': 'shared runtime correction; redundancy remains unresolved', 'old_git_commit': old['git_commit'], 'new_git_commit': new_config['git_commit'], 'authorized_retry': auth, 'recorded_utc': datetime.now(timezone.utc).isoformat()})
    atomic_json(path, new_config)
