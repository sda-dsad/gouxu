#!/usr/bin/env python3
"""Selective, revision-pinned KuaiSearch downloader. --plan needs only Python."""
from __future__ import annotations
import argparse, datetime, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'contracts/source.lock.json'

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--accept-source-license',action='store_true')
    parser.add_argument('--verify-local',action='store_true')
    parser.add_argument('--ack-license-discrepancy',action='store_true')
    args=parser.parse_args()
    cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
    print(json.dumps({'repo':cfg['repo_id'],'revision':cfg['revision'],
        'files':cfg['files'],'license_verification':cfg['license_verification'],'notice':'Only two Lite JSONL files (~3.05 GB); never entire repo.'},ensure_ascii=False,indent=2))
    if args.plan or not(args.download or args.verify_local): return 0
    if args.download and not args.accept_source_license:
        print('Read docs/03_DATA_SOURCES.md and license record first; then add --accept-source-license.',file=sys.stderr); return 2
    if args.download and 'CONFLICT' in cfg['license_verification'] and not args.ack_license_discrepancy:
        print('HF MIT metadata conflicts with paper CC BY 4.0. Read and retain both sources; add --ack-license-discrepancy only after reviewing intended use. This is not license clearance.',file=sys.stderr); return 2
    dest=ROOT/'data/raw'/cfg['revision']; dest.mkdir(parents=True,exist_ok=True)
    report={'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'revision':cfg['revision'],
        'status':'running','license_status':cfg['license_verification'],'files':[],'scope':'file integrity only; not semantic audit'}
    try:
        if args.download:
            from huggingface_hub import hf_hub_download
        for entry in cfg['files']:
            local=dest/entry['path']
            if args.download:
                local=Path(hf_hub_download(repo_id=cfg['repo_id'],repo_type='dataset',
                    filename=entry['path'],revision=cfg['revision'],local_dir=str(dest)))
            if not local.is_file(): raise FileNotFoundError(local)
            actual=sha256(local)
            record={'path':str(local.relative_to(ROOT)),'size_bytes':local.stat().st_size,
                    'sha256':actual,'expected_sha256':entry['sha256'],'match':actual==entry['sha256']}
            report['files'].append(record)
            if not record['match']: raise ValueError('Source hash mismatch: stop and audit; do not replace expected hash blindly.')
        report['status']='files_verified_semantics_not_yet_audited'
    except Exception as exc:
        report['status']='blocked_real_data'
        report['error']=f'{type(exc).__name__}: {exc}'
        print(report['error'],file=sys.stderr)
    (ROOT/'reports/source-download.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['status'].startswith('files_verified') else 1
if __name__=='__main__': raise SystemExit(main())
