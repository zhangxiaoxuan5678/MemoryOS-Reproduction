"""Local embeddings + original retrieval, with a proven zero-keyword lower bound.
Never emits model answers. No API client is constructed.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import statistics
from unittest.mock import patch
from evaluation_common import (ROOT, verified_preparation, verified_snapshot, load_trial,
                               retrieval_metrics, check_memory_files, CAPACITIES, REPEATS)
from build_runtime import atomic_json, BuildStop


def forbidden(*a, **k):
    raise AssertionError('API/network forbidden during offline audit')


class CapturePrompt:
    def chat_completion(self, messages, **kwargs):
        self.messages = messages
        self.parameters = kwargs
        return ''  # No answer is generated or stored.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    spec, questions = verified_preparation(args.prepared)
    snapshot, manifest, _ = verified_snapshot()
    with patch.object(socket.socket, 'connect', forbidden), patch.object(socket, 'create_connection', forbidden):
        import utils
        import mid_term_memory
        import numpy as np
        import faiss
        faiss.omp_set_num_threads(1)
        original_factory = utils.SentenceTransformer
        embedding = json.loads((ROOT / 'runs/embedding-download.json').read_text())
        with patch.object(utils, 'SentenceTransformer', lambda name: original_factory(embedding['snapshot_path'], local_files_only=True)):
            utils._get_embedding_model.cache_clear()
            from main_loco_parse import generate_system_response_with_meta
            audit = []
            with contextlib.redirect_stdout(io.StringIO()):
                models = {k: load_trial(args.prepared / f'k{k:02d}-r1/memory', k, None) for k in CAPACITIES}
                first_mid = models[5][1]
                vectors = np.array([s['summary_embedding'] for s in first_mid.sessions.values()], dtype=np.float32)
                index = faiss.IndexFlatIP(vectors.shape[1]); index.add(vectors)
                for q in questions:
                    query = utils.normalize_vector(utils.get_embedding(q['question']))
                    scores, _ = index.search(np.array([query], dtype=np.float32), 5)
                    min_score = float(min(scores[0]))
                    certain = min_score >= spec['segment_threshold']
                    records = {}
                    # Zero keyword overlap is a mathematical lower bound, not LLM output.
                    # If every candidate cosine clears .1, any nonnegative keyword
                    # overlap gives identical segment membership. Original code runs.
                    with patch.object(mid_term_memory, 'llm_extract_keywords', return_value=set()):
                        for k in CAPACITIES:
                            short, mid, long, retriever = models[k]
                            result = retriever.retrieve(q['question'], segment_threshold=.1, page_threshold=.1, knowledge_threshold=.1, client=None)
                            metrics = retrieval_metrics(result)
                            capture = CapturePrompt()
                            generate_system_response_with_meta(q['question'], short, long, result['retrieval_queue'], result['long_term_knowledge'], capture, 'conv-26', spec['speaker_a'], spec['speaker_b'], {})
                            text = ''.join(m['content'] for m in capture.messages)
                            metrics.update(answer_prompt_chars=len(text), answer_prompt_utf8_bytes=len(text.encode()), answer_max_tokens=capture.parameters['max_tokens'])
                            records[str(k)] = metrics
                    comparisons = {}
                    for a,b in ((5,10),(10,20),(5,20)):
                        left,right=records[str(a)],records[str(b)]
                        comparisons[f'{a}_vs_{b}'] = {'ordered_content_equal':left['content_hashes_in_order']==right['content_hashes_in_order'], 'unique_content_sets_equal':set(left['content_hashes_in_order'])==set(right['content_hashes_in_order']), 'shared_unique_contents':len(set(left['content_hashes_in_order']) & set(right['content_hashes_in_order']))}
                    audit.append({'question_id':q['question_id'], 'minimum_top5_segment_cosine':min_score, 'segment_membership_independent_of_keywords':certain, 'interpretation':'original algorithm under zero-overlap bound; membership certified for all possible extracted keywords' if certain else 'lower-bound diagnostic only; true retrieval still requires model', 'capacities':records,'comparisons':comparisons})
            for k in CAPACITIES:
                for repeat in REPEATS:
                    check_memory_files(args.prepared / f'k{k:02d}-r{repeat}/memory', manifest)
            verified_snapshot()
            utils._get_embedding_model.cache_clear()
    # Calibrate length estimates from real saved requests; not an exact tokenizer.
    es=[json.loads(l) for l in (ROOT/'runs/formal-conv26-v1/calls.jsonl').read_text().splitlines()]
    starts={e['index']:e for e in es if e['event']=='started'}
    ratios=[]
    for e in es:
        if e['event']=='response' and e.get('usage'):
            text=''.join(m['content'] for m in starts[e['index']]['messages'])
            if len(text)>=3000:
                ratios.append(len(text)/e['usage']['prompt_tokens'])
    calibration={'method':'observed saved build input characters / server prompt_tokens for prompts >=3000 chars; approximation only', 'sample_count':len(ratios), 'chars_per_token_min':min(ratios),'chars_per_token_median':statistics.median(ratios),'chars_per_token_max':max(ratios)}
    summaries={}
    for k in CAPACITIES:
        rows=[q['capacities'][str(k)] for q in audit]
        summaries[str(k)]={key:{'min':min(r[key] for r in rows),'mean':statistics.mean(r[key] for r in rows),'max':max(r[key] for r in rows)} for key in ('actual_pages','unique_page_ids','unique_contents','answer_prompt_chars')}
    report={'kind':'offline_retrieval_certificate_not_paid_evaluation','api_requests':0,'model_answers_generated':0,'certified_questions':sum(q['segment_membership_independent_of_keywords'] for q in audit),'minimum_candidate_cosine':min(q['minimum_top5_segment_cosine'] for q in audit),'keywords_required_by_original_runtime':True,'formal_algorithm_modified':False,'deduplication_added':False,'calibration':calibration,'capacity_summaries':summaries,'questions':audit}
    atomic_json(args.prepared / 'offline-audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='questions'},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
