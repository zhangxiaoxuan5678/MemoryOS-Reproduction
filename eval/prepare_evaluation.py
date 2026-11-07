"""No API calls: freeze trial plan and nine independent memory copies."""
import argparse
import json
from pathlib import Path
from evaluation_common import (audit_selection, clone_memory, fixed_spec, verified_snapshot,
                               verified_questions, CAPACITIES, REPEATS)
from build_runtime import atomic_json, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    indices = audit_selection()
    snapshot, manifest, _ = verified_snapshot()
    questions, _ = verified_questions()
    args.output.mkdir(parents=True, exist_ok=False)
    atomic_json(args.output / 'spec.json', fixed_spec())
    atomic_json(args.output / 'questions.json', questions)
    for k in CAPACITIES:
        for repeat in REPEATS:
            clone_memory(snapshot, args.output / f'k{k:02d}-r{repeat}/memory', manifest)
    atomic_json(args.output / 'selection-audit.json', {'indices_zero_based': indices, 'questions_sha256': digest(args.output / 'questions.json'), 'category_counts': {'1':6,'2':6,'3':6,'4':7}, 'selection_uses_answers': False, 'references_in_generation_inputs': False})
    print('Prepared nine isolated trial copies, 25 fixed questions; no API calls.')


if __name__ == '__main__':
    main()
