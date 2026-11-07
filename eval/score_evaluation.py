"""Score only after generation. Exact upstream simplified set-token F1."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
from build_runtime import BuildStop, atomic_json, digest
from evaluation_common import CAPACITIES, REPEATS, PREPARED, verified_questions
from evalution_loco import calculate_f1


def aggregate(rows, references):
    if len(rows)!=225:
        raise BuildStop('Need exactly 225 completed answers; partial runs are not final scores')
    by_trial=defaultdict(list)
    seen=set()
    for row in rows:
        if row.get('valid_answer',True) is not True:raise BuildStop('Invalid/truncated answer cannot be scored')
        key=(row['capacity'],row['repeat'],row['question_id'])
        if key in seen or row['capacity'] not in CAPACITIES or row['repeat'] not in REPEATS or row['question_id'] not in references:
            raise BuildStop('Duplicate or out-of-scope result')
        seen.add(key)
        ref=references[row['question_id']]
        entry={'question_id':row['question_id'],'category':ref['category'],'f1':calculate_f1(row['system_answer'],ref['answer'])}
        by_trial[(row['capacity'],row['repeat'])].append(entry)
    groups={}
    for k in CAPACITIES:
        run_means=[]; categories=defaultdict(list); trials=[]
        for repeat in REPEATS:
            entries=by_trial[(k,repeat)]
            if {e['question_id'] for e in entries}!=set(references): raise BuildStop('Trial has missing questions')
            mean=statistics.mean(e['f1'] for e in entries); run_means.append(mean)
            category_means={str(c):statistics.mean(e['f1'] for e in entries if e['category']==c) for c in (1,2,3,4)}
            for c,value in category_means.items(): categories[c].append(value)
            selected=[r for r in rows if r['capacity']==k and r['repeat']==repeat]
            trials.append({'repeat':repeat,'mean_f1':mean,'category_mean_f1':category_means,'usage_including_keywords':{name:sum(r['usage_including_keywords'][name] for r in selected) for name in ('prompt_tokens','completion_tokens','total_tokens')},'question_elapsed_seconds':sum(r['elapsed_seconds'] for r in selected),'mean_actual_pages':statistics.mean(r['retrieval']['actual_pages'] for r in selected),'mean_unique_pages':statistics.mean(r['retrieval']['unique_page_ids'] for r in selected),'per_question':entries})
        selected_group=[r for r in rows if r['capacity']==k]
        group_usage={name:sum(r['usage_including_keywords'][name] for r in selected_group) for name in ('prompt_tokens','completion_tokens','total_tokens')}
        groups[str(k)]={'usage_including_keywords':group_usage,'estimated_peak_cny':(group_usage['prompt_tokens']*2+group_usage['completion_tokens']*8)/1000000,'active_question_seconds':sum(r['elapsed_seconds'] for r in selected_group),'mean_actual_pages':statistics.mean(r['retrieval']['actual_pages'] for r in selected_group),'mean_unique_page_ids':statistics.mean(r['retrieval']['unique_page_ids'] for r in selected_group),'mean_f1':statistics.mean(run_means),'sample_std_across_3_run_means':statistics.stdev(run_means),'run_means':run_means,'categories':{c:{'mean_f1':statistics.mean(values),'sample_std_across_3_run_means':statistics.stdev(values)} for c,values in categories.items()},'trials':trials}
    return {'metric':'upstream simplified set-token F1, unmodified','standard_deviation':'sample std, ddof=1, across three independent 25-question run means','groups':groups,'limitations':['one conversation','25 fixed category-balanced questions, not full benchmark','DeepSeek replaces upstream gpt-4o-mini','shared dialogue/config/runtime corrections','original duplicates/id(page) ties retained','not directly comparable to full paper benchmark']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-dir',type=Path,required=True);args=parser.parse_args()
    questions,frozen=verified_questions()
    status=json.loads((args.run_dir/'status.json').read_text())
    if status.get('status')!='completed' or status.get('answers')!=225:
        raise BuildStop('Only a completed 225-answer evaluation may receive final scores')
    for k in CAPACITIES:
        for repeat in REPEATS:
            done=json.loads((args.run_dir/f'k{k:02d}-r{repeat}/completed.json').read_text())
            if done.get('questions')!=25 or not done.get('memory_files_unchanged'):
                raise BuildStop('Trial completion/memory verification missing')
    config=json.loads((args.run_dir/'config.json').read_text())
    if config['questions_sha256']!=frozen['files_sha256']['questions.json']: raise BuildStop('Run question list mismatch')
    path=PREPARED/'scoring_only/references.json'
    if digest(path)!=config['references_sha256_for_scorer_only']: raise BuildStop('Scorer references mismatch')
    refs={r['question_id']:r for r in json.loads(path.read_text())}
    if set(refs)!={q['question_id'] for q in questions}:raise BuildStop('Reference identity mismatch')
    rows=[json.loads(p.read_text()) for p in sorted(args.run_dir.glob('k*-r*/q*.json'))]
    if any(r.get('valid_answer') is not True for r in rows):raise BuildStop('Invalid or unmarked result cannot be scored')
    summary=aggregate(rows,refs);atomic_json(args.run_dir/'scores.json',summary)
    print(json.dumps({k:{'mean_f1':v['mean_f1'],'sample_std':v['sample_std_across_3_run_means']} for k,v in summary['groups'].items()},indent=2))


if __name__=='__main__':main()
