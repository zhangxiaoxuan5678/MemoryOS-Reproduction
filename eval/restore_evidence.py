"""Restore published evidence into original local paths; no model, network or .env."""
import argparse
from pathlib import Path
import shutil
import zipfile
from verify_submission import ROOT, verify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--restore', action='store_true', help='Write new ignored runs directories; never overwrite')
    args = p.parse_args()
    if not args.restore:
        print('Preview only: --restore creates study-preparation, formal snapshot and evaluation results under runs/. No API.')
        return
    verify()
    targets = [ROOT / 'runs' / name for name in
               ('study-preparation-conv26-v1', 'formal-conv26-v1', 'eval-results-conv26-v1')]
    if any(t.exists() for t in targets):
        raise FileExistsError('A target already exists; refusing all writes. Use a fresh publication copy.')
    evidence = ROOT / 'evidence'
    prepared, build, results = targets
    prepared.mkdir(parents=True)
    for source, dest in [('selection-manifest.json', 'manifest.json'), ('questions.json', 'questions.json'),
                         ('scoring_only/references.json', 'scoring_only/references.json'),
                         ('build_input/conversation.json', 'build_input/conversation.json'),
                         ('build_input/pages.json', 'build_input/pages.json')]:
        path = prepared / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(evidence / source, path)
    with zipfile.ZipFile(evidence / 'snapshot.zip') as z:
        for entry in z.infolist():
            if entry.is_dir() or not entry.filename.startswith('snapshot/'):
                continue
            path = (build / entry.filename).resolve()
            if not path.is_relative_to(build.resolve()):
                raise ValueError('Unsafe archive path')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(entry))
            path.chmod(0o444)
    with zipfile.ZipFile(evidence / 'evaluation-raw.zip') as z:
        for entry in z.infolist():
            prefix = 'eval-results-conv26-v1/'
            if entry.is_dir() or not entry.filename.startswith(prefix):
                continue
            path = (results / entry.filename[len(prefix):]).resolve()
            if not path.is_relative_to(results.resolve()):
                raise ValueError('Unsafe archive path')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(entry))
    print('Restored original evidence paths. No new model responses, no build, no API requests.')


if __name__ == '__main__':
    main()
