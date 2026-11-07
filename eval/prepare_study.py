"""Offline preparation only. Never constructs a memory module or API client."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from collections import Counter
from study_data import process_conversation

ROOT = Path(__file__).resolve().parent.parent


def prepare(directory):
    source = ROOT / 'eval/locomo10.json'
    sample = next(s for s in json.loads(source.read_text()) if s['sample_id'] == 'conv-26')
    conversation = sample['conversation']
    pages = process_conversation(conversation)
    expected = [(session, i, turn['speaker'], turn['text'] + (f" (image description: {turn['blip_caption']})" if turn.get('blip_caption') else ''), conversation.get(session + '_date_time', '')) for session in sorted((k for k in conversation if k.startswith('session_') and not k.endswith('_date_time')), key=lambda k: int(k.split('_')[1])) for i, turn in enumerate(conversation[session])]
    recovered = [(p['session_key'], t['index'], t['speaker'], p['user_input'] if t['speaker'] == conversation['speaker_a'] else p['agent_response'], p['timestamp']) for p in pages for t in p['source_turns']]
    if recovered != expected:
        raise ValueError('Lossless conversion audit failed')
    if any(not (p['user_input'] or p['agent_response']) for p in pages):
        raise ValueError('Empty pages need explicit handling')
    # Select by original index and category only; never rank using answers/evidence.
    selected = []
    for category, count in ((1, 6), (2, 6), (3, 6), (4, 7)):
        candidates = [i for i, qa in enumerate(sample['qa']) if qa['category'] == category]
        if len(candidates) < count:
            raise ValueError('Not enough questions in category')
        selected.extend(candidates[:count])
    selected.sort()
    questions = [{'question_id': f'conv-26:qa:{i}', 'question': sample['qa'][i]['question']} for i in selected]
    references = [{'question_id': f'conv-26:qa:{i}', 'qa_index_zero_based': i, 'category': sample['qa'][i]['category'], 'answer': sample['qa'][i].get('answer', ''), 'evidence': sample['qa'][i].get('evidence', [])} for i in selected]
    files = {'build_input/conversation.json': conversation, 'build_input/pages.json': pages, 'questions.json': questions, 'scoring_only/references.json': references}
    directory.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, value in files.items():
        p = directory / name
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {'kind': 'offline_preparation_not_memory_build', 'sample_id': 'conv-26', 'dataset_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'converter_sha256': hashlib.sha256((ROOT / 'eval/study_data.py').read_bytes()).hexdigest(), 'source_turns': len(expected), 'pages': len(pages), 'single_sided_pages': sum(not p['user_input'] or not p['agent_response'] for p in pages), 'question_count': len(questions), 'categories': dict(Counter(q['category'] for q in references)), 'selected_qa_indices_zero_based': selected, 'selection': 'First 6 questions in each category 1-3 and first 7 in category 4, then original index order; category 5 excluded', 'files_sha256': hashes}
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
