"""Preview by default; paid build needs explicit authorization and request limit."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
import time
from datetime import datetime, timezone
from unittest.mock import patch
from build_runtime import (BuildStop, LedgerClient, MEMORY_FILES, atomic_json, commit_checkpoint,
                           coverage, digest, validate_themes, verify_checkpoint, apply_meta300_correction, apply_profile4000_correction, apply_profile16000_correction)

ROOT = Path(__file__).resolve().parent.parent
CORE = ('build_study.py', 'build_runtime.py', 'study_data.py', 'utils.py', 'dynamic_update.py',
        'main_loco_parse.py', 'short_term_memory.py', 'mid_term_memory.py', 'long_term_memory.py')


def inputs(prepared, model_metadata):
    prepared = Path(prepared).resolve()
    manifest = json.loads((prepared / 'manifest.json').read_text())
    # Deliberately never open questions.json or scoring_only/references.json.
    for name in ('build_input/pages.json', 'build_input/conversation.json'):
        if digest(prepared / name) != manifest['files_sha256'][name]:
            raise BuildStop('Frozen build input hash mismatch')
    if digest(ROOT / 'eval/study_data.py') != manifest['converter_sha256']:
        raise BuildStop('Converter changed after data freeze')
    pages = json.loads((prepared / 'build_input/pages.json').read_text())
    if manifest['sample_id'] != 'conv-26' or len(pages) != manifest['pages']:
        raise BuildStop('Invalid study scope')
    model = json.loads(Path(model_metadata).read_text())
    snapshot = Path(model['snapshot_path']).resolve()
    if model['repo_id'] != 'sentence-transformers/all-MiniLM-L6-v2' or snapshot.name != model['revision']:
        raise BuildStop('Unexpected embedding model')
    for name, checksum in model['files_sha256'].items():
        if digest(snapshot / name) != checksum:
            raise BuildStop('Embedding hash mismatch')
    return manifest, pages, model


def build_pages(directory, pages, client, sample_id, state=None):
    """Per-page transactions; abandoned work never becomes a checkpoint."""
    from short_term_memory import ShortTermMemory
    from mid_term_memory import MidTermMemory
    from long_term_memory import LongTermMemory
    import dynamic_update
    from main_loco_parse import update_user_profile_from_top_segment
    directory = Path(directory)
    (directory / 'checkpoints').mkdir(exist_ok=True)
    completed = state['completed_pages'] if state else 0
    # A crash after directory publication but before pointer publication leaves an orphan.
    for orphan in (directory / 'checkpoints').glob('page-*'):
        if int(orphan.name.split('-')[1]) > completed or (state is None and orphan.name == 'page-0000'):
            (directory / 'abandoned').mkdir(exist_ok=True)
            orphan.rename(directory / 'abandoned' / (orphan.name + '-' + uuid.uuid4().hex))
    previous = verify_checkpoint(directory, state) if state else None
    for number in range(completed, len(pages) + 1):
        if previous is not None and number == completed:
            continue
        work = directory / ('work-' + uuid.uuid4().hex)
        work.mkdir()
        if previous:
            for name in MEMORY_FILES:
                shutil.copy2(previous / name, work / name)
        short = ShortTermMemory(max_capacity=1, file_path=str(work / 'short.json'))
        mid = MidTermMemory(max_capacity=2000, file_path=str(work / 'mid.json'), client=client)
        long = LongTermMemory(file_path=str(work / 'long.json'))
        # JSON does not preserve shared object identities across topic segments.
        # Restore the original aliasing of duplicate references to the same page.
        canonical = {}
        for segment in mid.sessions.values():
            segment['details'] = [canonical.setdefault(p['page_id'], p) for p in segment['details']]
        updater = dynamic_update.DynamicUpdate(short, mid, long, topic_similarity_threshold=0.6, client=client)
        if previous:
            saved = json.loads((work / 'updater.json').read_text())
            if saved['last_page_id']:
                updater.last_evicted_page = mid.get_page_by_id(saved['last_page_id'])
                if updater.last_evicted_page is None:
                    raise BuildStop('Missing continuity checkpoint')
        if number > 0:
            client.begin_page(number - 1)
            page = pages[number - 1]
            short.add_qa_pair(dict(page))
            original = dynamic_update.gpt_generate_multi_summary
            def strict_themes(text, api):
                return validate_themes(original(text, api))
            with patch.object(dynamic_update, 'gpt_generate_multi_summary', strict_themes):
                updater.bulk_evict_and_update_mid_term()
            update_user_profile_from_top_segment(mid, long, sample_id, client)
        short.save()
        mid.save()
        long.save()
        atomic_json(work / 'updater.json', {'last_page_id': updater.last_evicted_page['page_id'] if updater.last_evicted_page else None})
        audit = coverage(json.loads((work / 'mid.json').read_text()), pages[:number])
        if short.get_all():
            raise BuildStop('Unexpected uncommitted short-term pages')
        state = commit_checkpoint(directory, work, number, audit, client)
        previous = verify_checkpoint(directory, state)
        print(f'Committed {number}/{len(pages)} pages; requests={client.count}', flush=True)
    return state


def publish_snapshot(directory, state, config):
    directory = Path(directory)
    checkpoint = verify_checkpoint(directory, state)
    final = directory / 'snapshot'
    if final.exists():
        manifest = json.loads((final / 'manifest.json').read_text())
        if manifest['files_sha256'] != state['files_sha256'] or manifest['build_config'] != config:
            raise BuildStop('Existing snapshot does not match checkpoint/config')
        for name, checksum in {**manifest['files_sha256'], **manifest.get('provenance_sha256', {})}.items():
            if digest(final / name) != checksum:
                raise BuildStop('Existing snapshot was modified')
        return
    temporary = directory / ('snapshot-' + uuid.uuid4().hex + '.tmp')
    temporary.mkdir()
    for name in MEMORY_FILES:
        shutil.copy2(checkpoint / name, temporary / name)
    provenance = {}
    for evidence in sorted(directory.glob('correction-*.json')) + sorted((directory / 'diagnostics').glob('request408-offline.*')):
        target = 'provenance-' + evidence.name
        shutil.copy2(evidence, temporary / target)
        provenance[target] = digest(temporary / target)
    atomic_json(temporary / 'manifest.json', {'provenance_sha256': provenance, 'kind': 'validated_memory_snapshot', 'coverage': state['coverage'], 'files_sha256': state['files_sha256'], 'build_config': config, 'usage': state['usage']})
    for path in temporary.iterdir():
        path.chmod(0o444)
    temporary.chmod(0o555)
    os.replace(temporary, final)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--model-metadata', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--max-requests', type=int, required=True)
    parser.add_argument('--max-cost-cny', type=str, default='10')
    parser.add_argument('--apply-profile16000-correction', action='store_true')
    parser.add_argument('--apply-profile4000-correction', action='store_true')
    parser.add_argument('--apply-meta300-correction', action='store_true')
    parser.add_argument('--allow-paid', action='store_true')
    args = parser.parse_args()
    manifest, pages, model = inputs(args.prepared, args.model_metadata)
    if args.max_requests < 1:
        raise BuildStop('Positive request limit required')
    directory = args.run_dir.resolve()
    if directory.parent != (ROOT / 'runs').resolve() or directory == args.prepared.resolve():
        raise BuildStop('Use a separate direct child of repository runs/')
    preview = {'mode': 'preview_no_api', 'pages': len(pages), 'source_turns': manifest['source_turns'], 'base_calls_if_successful': 3 * len(pages) - 1, 'additional_calls': 'keywords and profile updates depend on model output', 'request_limit': args.max_requests, 'output_limit_per_request': 16000, 'profile_merge_limit': 16000, 'other_output_limits_unchanged': True, 'sdk_retries': 0, 'thinking': 'disabled', 'downloads': False, 'max_cost_cny': args.max_cost_cny, 'pre_request_reserved_cny_profile_merge': '2.225152', 'pre_request_reserved_cny_other': '2.113152'}
    if not args.allow_paid:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise BuildStop('Commit reviewed code before paid build')
    directory.mkdir(exist_ok=True)
    with (directory / '.build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from utils import OpenAIClient
        configured = OpenAIClient()
        from urllib.parse import urlparse
        if configured.model != 'deepseek-flash' or urlparse(str(configured.client.base_url)).hostname != 'api.deepseek.com':
            raise BuildStop('CNY policy is verified only for official DeepSeek flash')
        import hashlib
        # Hash endpoint identity for resume checks; never log URL or credentials.
        endpoint_hash = hashlib.sha256(str(configured.client.base_url).encode()).hexdigest()
        config = {'sample_id': manifest['sample_id'], 'input_sha256': manifest['files_sha256']['build_input/pages.json'], 'model': configured.model, 'endpoint_sha256': endpoint_hash, 'embedding_revision': model['revision'], 'embedding_files_sha256': model['files_sha256'], 'request_limit': args.max_requests, 'max_output_tokens': 2000, 'max_cost_cny': args.max_cost_cny, 'price_input_micro_cny_per_token': 2, 'price_output_micro_cny_per_token': 8, 'input_reservation_tokens': 1048576, 'price_source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/', 'thinking': 'disabled', 'sdk_retries': 0, 'timeout_seconds': 60, 'short_capacity': 1, 'mid_capacity': 2000, 'topic_threshold': 0.6, 'heat_threshold': 5.0, 'meta_summary_max_tokens': 300, 'profile_merge_max_tokens': 16000, 'source_sha256': {n: digest(ROOT / 'eval' / n) for n in CORE}, 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
        if args.apply_meta300_correction:
            apply_meta300_correction(directory, config, 333)
        if args.apply_profile4000_correction:
            apply_profile4000_correction(directory, config)
        if args.apply_profile16000_correction:
            apply_profile16000_correction(directory, config)
        config_path = directory / ('config-profile16000.json' if (directory / 'config-profile16000.json').exists() else ('config-profile4000.json' if (directory / 'config-profile4000.json').exists() else ('config-meta300.json' if (directory / 'config-meta300.json').exists() else 'config.json')))
        if config_path.exists():
            if json.loads(config_path.read_text()) != config:
                raise BuildStop('Resume config/source/version changed; no request sent')
        else:
            if any(p.name != '.build.lock' for p in directory.iterdir()):
                raise BuildStop('Refusing to initialize nonempty directory')
            atomic_json(config_path, config)
        client = LedgerClient(directory, configured.model, configured.client.with_options(max_retries=0, timeout=60), args.max_requests, budget_cny=args.max_cost_cny)
        state = json.loads((directory / 'checkpoint.json').read_text()) if (directory / 'checkpoint.json').exists() else None
        if state:
            checkpoint = verify_checkpoint(directory, state)
            coverage(json.loads((checkpoint / 'mid.json').read_text()), pages[:state['completed_pages']])
        start_clock = time.monotonic()
        if not (directory / 'started.json').exists():
            atomic_json(directory / 'started.json', {'started_utc': datetime.now(timezone.utc).isoformat()})
        try:
            import utils
            original_factory = utils.SentenceTransformer
            with patch.object(utils, 'SentenceTransformer', lambda name: original_factory(model['snapshot_path'], local_files_only=True)):
                utils._get_embedding_model.cache_clear()
                utils.get_embedding('local embedding preflight')
                with (directory / 'build.log').open('a') as output, contextlib.redirect_stdout(output):
                    state = build_pages(directory, pages, client, manifest['sample_id'], state)
                utils._get_embedding_model.cache_clear()
            if state['completed_pages'] != len(pages):
                raise BuildStop('Incomplete build cannot publish snapshot')
            publish_snapshot(directory, state, config)
            status = {'status': 'completed', 'completed_pages': len(pages), **client.totals()}
        except Exception as error:
            checkpoint = directory / 'checkpoint.json'
            done = json.loads(checkpoint.read_text())['completed_pages'] if checkpoint.exists() else 0
            status = {'status': 'stopped', 'completed_pages': done, 'error_type': type(error).__name__, **client.totals()}
            # Only our own controlled error strings are safe to retain.
            if isinstance(error, BuildStop):
                status['reason'] = str(error)
            with (directory / 'errors.jsonl').open('a') as f:
                f.write(json.dumps(status) + '\n')
            status['session_elapsed_seconds'] = round(time.monotonic() - start_clock, 3)
            status['finished_utc'] = datetime.now(timezone.utc).isoformat()
            atomic_json(directory / 'status.json', status)
            print(json.dumps(status))
            raise SystemExit(1) from None
        status['session_elapsed_seconds'] = round(time.monotonic() - start_clock, 3)
        status['finished_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(directory / 'status.json', status)
        print(json.dumps(status))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'preflight_stopped', 'error_type': type(error).__name__, 'reason': str(error) if isinstance(error, BuildStop) else 'Check local configuration or file integrity; no automatic retry'}))
        raise SystemExit(1) from None
