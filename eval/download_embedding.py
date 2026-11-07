"""Download only the original sentence-transformers embedding snapshot."""
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent

def main():
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    from huggingface_hub import snapshot_download
    path = Path(snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2', revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41', cache_dir=ROOT / 'runs' / 'model-cache', token=False, allow_patterns=['*.json', '*.txt', 'model.safetensors'], ignore_patterns=['onnx/*', 'openvino/*'], max_workers=2))
    files = {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
    if 'model.safetensors' not in files:
        raise RuntimeError('Original model weights are missing')
    record = {'repo_id': 'sentence-transformers/all-MiniLM-L6-v2', 'revision': path.name, 'snapshot_path': str(path), 'downloaded_utc': datetime.now(timezone.utc).isoformat(), 'files_sha256': files}
    (ROOT / 'runs' / 'embedding-download.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Original embedding downloaded; revision:', path.name)
    print('Metadata:', ROOT / 'runs' / 'embedding-download.json')

if __name__ == '__main__':
    main()
