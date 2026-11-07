"""Verify published evidence and recompute original F1; stdlib only, no API/config."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    # Refuse even accidental networking in imported scoring code.
    def blocked(*args, **kwargs):
        raise RuntimeError('Network disabled during submission verification')
    socket.socket.connect = blocked
    socket.create_connection = blocked
    from score_evaluation import aggregate
    evidence = ROOT / 'evidence'
    manifest = json.loads((evidence / 'manifest.json').read_text())
    for name, expected in manifest['files_sha256'].items():
        require(hashlib.sha256((evidence / name).read_bytes()).hexdigest() == expected,
                'Evidence hash mismatch: ' + name)
    questions = json.loads((evidence / 'questions.json').read_text())
    selection = json.loads((evidence / 'selection-manifest.json').read_text())
    require(hashlib.sha256((ROOT / 'eval/locomo10.json').read_bytes()).hexdigest()
            == selection['dataset_sha256'], 'Source dataset mismatch')
    sample = next(s for s in json.loads((ROOT / 'eval/locomo10.json').read_text())
                  if s['sample_id'] == 'conv-26')
    indices = sorted(i for c, n in ((1, 6), (2, 6), (3, 6), (4, 7))
                     for i in [i for i, q in enumerate(sample['qa']) if q['category'] == c][:n])
    expected_questions = [{'question_id': f'conv-26:qa:{i}', 'question': sample['qa'][i]['question']}
                          for i in indices]
    require(questions == expected_questions, 'Question selection mismatch')
    require(hashlib.sha256((evidence / 'questions.json').read_bytes()).hexdigest()
            == selection['files_sha256']['questions.json'], 'Question hash mismatch')
    refs_path = evidence / 'scoring_only/references.json'
    require(hashlib.sha256(refs_path.read_bytes()).hexdigest()
            == selection['files_sha256']['scoring_only/references.json'], 'Reference hash mismatch')
    refs = {r['question_id']: r for r in json.loads(refs_path.read_text())}
    with zipfile.ZipFile(evidence / 'snapshot.zip') as z:
        pointer = json.loads((ROOT / 'STUDY_SNAPSHOT.json').read_text())
        data = z.read('snapshot/manifest.json')
        require(hashlib.sha256(data).hexdigest() == pointer['manifest_sha256'], 'Snapshot manifest mismatch')
        snap = json.loads(data)
        require(snap['coverage'] == {'unique_pages': 215, 'source_turns': 419}, 'Snapshot coverage mismatch')
        for name, expected in {**snap['files_sha256'], **snap['provenance_sha256']}.items():
            require(hashlib.sha256(z.read('snapshot/' + name)).hexdigest() == expected,
                    'Snapshot file mismatch: ' + name)
    with zipfile.ZipFile(evidence / 'evaluation-raw.zip') as z:
        names = sorted(n for n in z.namelist()
                       if __import__('re').fullmatch(r'eval-results-conv26-v1/k\d+-r\d+/q\d+\.json', n))
        rows = [json.loads(z.read(n)) for n in names]
        require(len(rows) == 225 and all(r.get('valid_answer') is True for r in rows), 'Invalid answer set')
        calls = [json.loads(line) for line in z.read('eval-results-conv26-v1/calls.jsonl').splitlines()]
        started = [r for r in calls if r['event'] == 'started']
        responses = [r for r in calls if r['event'] == 'response']
        require(len(started) == len(responses) == 450, 'Request count mismatch')
        require(len({r['operation'] for r in started}) == 450, 'Request operations reused')
        for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            total = sum(r['usage_including_keywords'][name] for r in rows)
            recorded = json.loads((evidence / 'verification.json').read_text())['usage'][name]
            require(total == recorded, 'Token total mismatch: ' + name)
    result = aggregate(rows, refs)
    require(result == json.loads((evidence / 'scores.json').read_text()), 'Recomputed scores differ')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional new offline scores JSON; refuses overwrite')
    args = parser.parse_args()
    scores = verify()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as f:
            json.dump(scores, f, ensure_ascii=False, indent=2)
            f.write('\n')
    print('PASS: evidence hashes, frozen questions, 215-page snapshot, 225 valid answers, 450 requests, token totals and exact original F1.')
    for capacity, group in scores['groups'].items():
        print(f"capacity={capacity}: mean={group['mean_f1']:.8f}, sample_sd={group['sample_std_across_3_run_means']:.8f}")


if __name__ == '__main__':
    main()
