"""Heuristic credential scan; reports locations only, never matched values or .env content."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FORMATS = re.compile(rb'\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b')
ASSIGN = re.compile(rb'''(?im)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[=:]\s*["']([^"'\r\n]{12,})["']''')
PRIVATE = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def placeholder(value):
    return bool(re.search(rb'(?i)your[_ -]|placeholder|dummy|fake|test[_ -]|example|xxxxx|<[^>]+>', value))


def prohibited(name):
    p = Path(name)
    return ((p.name == '.env' or p.name.startswith('.env.')) and p.name != '.env.example'
            or p.suffix in ('.pem', '.key', '.p12', '.pfx')
            or p.name in ('id_rsa', 'id_ed25519', 'credentials.json'))


def scan(data, name):
    findings = []
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                nested = name + '!' + entry.filename
                if prohibited(entry.filename):
                    findings.append({'path': nested, 'rule': 'credential_filename'})
                else:
                    findings.extend(scan(z.read(entry), nested))
        return findings
    for label, pattern in (('key_format', FORMATS), ('private_key', PRIVATE), ('secret_assignment', ASSIGN)):
        for match in pattern.finditer(data):
            value = match.group(1) if label == 'secret_assignment' else match.group()
            if not placeholder(value):
                findings.append({'path': name, 'line': data[:match.start()].count(b'\n') + 1, 'rule': label})
    return findings


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history', action='store_true', help='Also inspect all blobs reachable from HEAD')
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    names = sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')) - {''})
    findings = []
    for name in names:
        if prohibited(name):
            findings.append({'path': name, 'rule': 'credential_filename'})
            continue  # Never read .env even if accidentally tracked.
        file = ROOT / name
        if file.is_file():
            findings.extend(scan(file.read_bytes(), name))
    blobs = 0
    if args.history:
        for line in git('rev-list', '--objects', 'HEAD').decode().splitlines():
            oid, _, name = line.partition(' ')
            if git('cat-file', '-t', oid).strip() != b'blob':
                continue
            blobs += 1
            if prohibited(name):
                findings.append({'path': name, 'object': oid, 'rule': 'credential_filename'})
                continue
            for hit in scan(git('cat-file', 'blob', oid), name):
                findings.append({**hit, 'object': oid})
    ignored = subprocess.run(['git', 'check-ignore', '-q', '.env'], cwd=ROOT).returncode == 0
    tracked = bool(git('ls-files', '--', '.env').strip())
    report = {'status': 'pass' if not findings and ignored and not tracked else 'needs_review',
              'files_scanned': len(names), 'history_blobs_scanned': blobs,
              'env_ignored': ignored, 'env_tracked': tracked, 'env_content_read': False,
              'archive_members_scanned': True, 'findings_locations_only': findings,
              'limitations': 'Heuristic known-format and assignment scan; not proof of absence of every possible secret.'}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
