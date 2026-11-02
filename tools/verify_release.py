"""Verify original release file hashes without reading private runtime directories."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]

def main():
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for name, info in manifest['files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            errors.append(name)
            continue
        # Git may normalize text line endings; binary assets remain byte-exact.
        content = path.read_bytes()
        if info['text']:
            content = content.replace(b'\r\n', b'\n')
        if hashlib.sha256(content).hexdigest() != info['sha256']:
            errors.append(name)
    if errors:
        raise SystemExit('Missing or changed files: ' + ', '.join(errors))
    print('PASS:', len(manifest['files']), 'release file hashes')

if __name__ == '__main__':
    main()
