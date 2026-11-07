"""Frozen evaluation inputs and unmodified retrieval wiring. No API construction."""
import hashlib
import json
from pathlib import Path
import shutil
from build_runtime import BuildStop, digest

ROOT = Path(__file__).resolve().parent.parent
MEMORIES = ('short.json', 'mid.json', 'long.json', 'updater.json')
CAPACITIES = (5, 10, 20)
REPEATS = (1, 2, 3)
PREPARED = ROOT / 'runs/study-preparation-conv26-v1'


def verified_snapshot():
    pointer = json.loads((ROOT / 'STUDY_SNAPSHOT.json').read_text())
    snapshot = ROOT / pointer['snapshot_path']
    if digest(snapshot / 'manifest.json') != pointer['manifest_sha256']:
        raise BuildStop('Published snapshot manifest mismatch')
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    if manifest['coverage'] != pointer['required_coverage']:
        raise BuildStop('Snapshot coverage mismatch')
    for name, checksum in {**manifest['files_sha256'], **manifest['provenance_sha256']}.items():
        path = snapshot / name
        if digest(path) != checksum or path.stat().st_mode & 0o222:
            raise BuildStop('Snapshot modified or writable')
    return snapshot, manifest, pointer


def verified_questions():
    manifest = json.loads((PREPARED / 'manifest.json').read_text())
    if digest(PREPARED / 'questions.json') != manifest['files_sha256']['questions.json']:
        raise BuildStop('Frozen question list mismatch')
    questions = json.loads((PREPARED / 'questions.json').read_text())
    if len(questions) != 25 or any(set(q) != {'question_id', 'question'} for q in questions):
        raise BuildStop('Invalid generation input; references must be separate')
    if len({q['question_id'] for q in questions}) != 25:
        raise BuildStop('Duplicate question IDs')
    return questions, manifest


def audit_selection():
    """Offline preparation only. Never used in the model execution path."""
    questions, manifest = verified_questions()
    if digest(ROOT / 'eval/locomo10.json') != manifest['dataset_sha256']:
        raise BuildStop('Dataset changed')
    sample = next(s for s in json.loads((ROOT / 'eval/locomo10.json').read_text()) if s['sample_id'] == 'conv-26')
    indices = sorted(i for category, n in ((1, 6), (2, 6), (3, 6), (4, 7)) for i in [i for i,q in enumerate(sample['qa']) if q['category'] == category][:n])
    expected = [{'question_id': f'conv-26:qa:{i}', 'question': sample['qa'][i]['question']} for i in indices]
    if questions != expected or indices != manifest['selected_qa_indices_zero_based']:
        raise BuildStop('Question selection does not match declared original-order rule')
    if digest(PREPARED / 'scoring_only/references.json') != manifest['files_sha256']['scoring_only/references.json']:
        raise BuildStop('Scoring references changed')
    return indices


def clone_memory(snapshot, destination, manifest):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name in MEMORIES:
        shutil.copyfile(snapshot / name, destination / name)
        (destination / name).chmod(0o600)
    check_memory_files(destination, manifest)


def check_memory_files(directory, manifest):
    for name in MEMORIES:
        if digest(Path(directory) / name) != manifest['files_sha256'][name]:
            raise BuildStop('Trial memory files were modified')


def load_trial(directory, capacity, client):
    # Import utils/Torch before FAISS, matching the upstream import sequence.
    import utils
    from short_term_memory import ShortTermMemory
    from mid_term_memory import MidTermMemory
    from long_term_memory import LongTermMemory
    from retrieval_and_answer import RetrievalAndAnswer
    short = ShortTermMemory(max_capacity=1, file_path=str(Path(directory) / 'short.json'))
    mid = MidTermMemory(max_capacity=2000, file_path=str(Path(directory) / 'mid.json'), client=client)
    long = LongTermMemory(file_path=str(Path(directory) / 'long.json'))
    return short, mid, long, RetrievalAndAnswer(short, mid, long, None, queue_capacity=capacity)


def content_hash(page):
    used = {k: page.get(k, '') for k in ('user_input', 'agent_response', 'timestamp', 'meta_info')}
    return hashlib.sha256(json.dumps(used, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def retrieval_metrics(result):
    pages = result['retrieval_queue']
    ids = [p['page_id'] for p in pages]
    hashes = [content_hash(p) for p in pages]
    return {'actual_pages': len(pages), 'unique_page_ids': len(set(ids)), 'unique_contents': len(set(hashes)), 'page_ids_in_order': ids, 'content_hashes_in_order': hashes, 'long_term_items': len(result['long_term_knowledge'])}


def fixed_spec():
    snapshot, manifest, pointer = verified_snapshot()
    questions, frozen = verified_questions()
    conversation = json.loads((PREPARED / 'build_input/conversation.json').read_text())
    return {'snapshot_manifest_sha256': pointer['manifest_sha256'], 'memory_files_sha256': manifest['files_sha256'], 'questions_sha256': frozen['files_sha256']['questions.json'], 'references_sha256_for_scorer_only': frozen['files_sha256']['scoring_only/references.json'], 'question_indices_zero_based': frozen['selected_qa_indices_zero_based'], 'sample_id': 'conv-26', 'speaker_a': conversation['speaker_a'], 'speaker_b': conversation['speaker_b'], 'model': pointer['requested_model'], 'capacities': list(CAPACITIES), 'baseline_capacity': 10, 'repeats': list(REPEATS), 'questions_per_trial': 25, 'total_answers': 225, 'auxiliary_keyword_requests': 225, 'total_requests_if_complete': 450, 'temperature': 0.7, 'answer_max_tokens': 2000, 'keyword_max_tokens': 2000, 'thinking': 'disabled', 'segment_top_k': 5, 'segment_threshold': 0.1, 'page_threshold': 0.1, 'knowledge_threshold': 0.1, 'long_term_top_k': 10, 'short_capacity': 1, 'mid_capacity': 2000, 'retrieval_algorithm': 'unmodified upstream heap and id(page) tie handling; duplicates retained', 'evaluation_writes_to_memory': False, 'answer_reuse_across_trials': False, 'faiss_threads': 1, 'price_input_cny_per_million': 2, 'price_output_cny_per_million': 8, 'proposed_request_budget': 450, 'proposed_cost_budget_cny': '20', 'budget_authorized': False}


def verified_preparation(path):
    path = Path(path)
    spec = fixed_spec()
    saved = json.loads((path / 'spec.json').read_text())
    if saved != spec:
        raise BuildStop('Evaluation preparation differs from fixed specification')
    if digest(path / 'questions.json') != spec['questions_sha256']:
        raise BuildStop('Prepared questions changed')
    return spec, json.loads((path / 'questions.json').read_text())
