"""Run existing checks with UTF-8 and disposable, workspace-local test state."""
from pathlib import Path
import argparse, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--python-only', action='store_true')
    mode.add_argument('--frontend-only', action='store_true')
    args = parser.parse_args()
    temp = ROOT / '.cache/temp'
    temp.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
           'TEMP': str(temp), 'TMP': str(temp), 'TMPDIR': str(temp),
           'GOUXU_PROJECT_ROOT': str(ROOT), 'GOUXU_DATA_ROOT': str(ROOT / '.cache/empty-data')}
    if not args.frontend_only:
        for folder in ('tests', 'services/api/tests'):
            subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest',
                            'discover', '-s', folder, '-v'], cwd=ROOT, env=env, check=True)
    if not args.python_only:
        npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
        if not npm:
            raise SystemExit('Node.js 24 / npm is required; install dependencies with npm ci.')
        for script in ('test', 'build'):
            subprocess.run([npm, 'run', script], cwd=ROOT / 'apps/web', env=env, check=True)

if __name__ == '__main__':
    main()
