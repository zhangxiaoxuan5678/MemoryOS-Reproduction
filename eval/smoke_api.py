"""One explicitly authorized connectivity request; never builds memory."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-paid', action='store_true', help='Explicit authorization for ONE request, at most 128 output tokens')
    parser.add_argument('--disable-thinking', action='store_true', help='Explicitly disable thinking for compatible providers such as DeepSeek')
    args = parser.parse_args()
    if not args.allow_paid:
        parser.error('No request made. Obtain confirmation before using --allow-paid.')

    from utils import OpenAIClient
    root = Path(__file__).resolve().parent.parent
    runs = root / 'runs'
    runs.mkdir(exist_ok=True)
    run = runs / ('smoke-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(exist_ok=False)
    record = {'kind': 'connectivity_smoke_not_experiment', 'request_limit': 1, 'output_token_limit': 128, 'retries': 0, 'timeout_seconds': 30, 'status': 'preparing', 'started_utc': datetime.now(timezone.utc).isoformat(), 'messages': [{'role': 'user', 'content': 'Reply with OK only.'}]}
    record['thinking_mode'] = 'disabled' if args.disable_thinking else 'provider_default'
    record['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    record['working_tree_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
    log = run / 'result.json'
    def save():
        log.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    save()
    try:
        client = OpenAIClient()
        record['configured_model'] = client.model
        record['status'] = 'request_started'
        save()
        # Disable SDK retries so a logical request cannot silently become several.
        response = client.client.with_options(max_retries=0, timeout=30).chat.completions.create(model=client.model, messages=record['messages'], temperature=0, max_tokens=128, **({'extra_body': {'thinking': {'type': 'disabled'}}} if args.disable_thinking else {}))
        record.update(status='completed', response_id=response.id, returned_model=response.model, answer=response.choices[0].message.content, usage=response.usage.model_dump() if response.usage else None)
    except Exception as error:
        # Exception messages can contain endpoint details; retain only safe type.
        record.update(status='failed', error_type=type(error).__name__)
        print('Smoke failed; inspect status/error_type in the local log. No automatic retry.')
        raise SystemExit(1) from None
    finally:
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print('Local log:', log)


if __name__ == '__main__':
    main()
