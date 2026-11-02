#!/usr/bin/env python3
"""Deterministic user-hash subset. Reads all source rows, never takes a head slice."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from domain import FIELDS, id_set, id_string, validate_request, metrics, category_flows
from download_data import sha256
ROOT=Path(__file__).resolve().parents[1]

def chosen(user: str, seed: str, percent: float) -> bool:
    digest=hashlib.sha256((seed+'|'+user).encode()).digest()
    return int.from_bytes(digest[:8],'big') / 2**64 < percent/100

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--percent',type=float,default=1.0);p.add_argument('--seed',default='gouxu-search-v2')
    p.add_argument('--output',type=Path,default=ROOT/'data/processed/kuaisearch_subset.json')
    p.add_argument('--force',action='store_true');a=p.parse_args()
    if not 0<a.percent<=5:p.error('Reference builder supports 0 < percent <= 5; use production pipeline for larger data.')
    if a.output.exists() and not a.force:p.error('Output exists; choose another --output or explicitly --force.')
    lock=json.loads((ROOT/'contracts/source.lock.json').read_text(encoding='utf-8'))
    base=ROOT/'data/raw'/lock['revision']
    for spec in lock['files']:
        path=base/spec['path']
        if not path.is_file() or sha256(path)!=spec['sha256']:p.error('Missing or unverified raw source: '+str(path))
    requests=[];wanted=set();seen={};raw_count=0;invalid=0;dup_exact=0;key_conflicts=[];users=set()
    recall=base/'recall_lite/train.jsonl'
    with recall.open(encoding='utf-8') as f:
        for line_no,line in enumerate(f,1):
            raw_count+=1
            try:
                row=json.loads(line);validate_request(row);user=id_string(row['user_id']);session=id_string(row['session_id'])
            except (ValueError,KeyError,TypeError): invalid+=1;continue
            if not chosen(user,a.seed,a.percent):continue
            # Include split and time where available; reject ambiguous repeated request keys.
            key=(user,session,str(row.get('time_index')),str(row.get('split')))
            fingerprint=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if key in seen:
                if seen[key]==fingerprint:dup_exact+=1
                else:key_conflicts.append(line_no)
                continue
            seen[key]=fingerprint;users.add(user)
            ids={x:sorted(id_set(row[x])) for x in FIELDS}
            wanted.update(set().union(*(set(v) for v in ids.values())))
            requests.append({'request_id':f'KSL-{line_no}','query':row['query'],**ids,
                'source_line':line_no,'split':row.get('split'),'time_index':row.get('time_index'),
                'source_file':'recall_lite/train.jsonl'})
    if invalid or dup_exact or key_conflicts:
        p.error(f'Source needs review: invalid={invalid}, duplicate_keys_same={dup_exact}, conflicting_keys={len(key_conflicts)}. No silent dedup; production rules must resolve explicitly.')
    items=[];metadata_count=0;item_conflicts=[];seen_items=set()
    with (base/'items_lite/train.jsonl').open(encoding='utf-8') as f:
        for line_no,line in enumerate(f,1):
            metadata_count+=1;row=json.loads(line);iid=id_string(row['item_id'])
            if iid not in wanted:continue
            if iid in seen_items:item_conflicts.append(line_no);continue
            seen_items.add(iid)
            items.append({'item_id':iid,'item_title':row['item_title'],
                'category_level1_id':str(row.get('category_level1_id') if row.get('category_level1_id') is not None else 'UNKNOWN'),
                'category_level1_name':row.get('category_level1_name') or 'UNKNOWN',
                'category_level2_name':row.get('category_level2_name','UNKNOWN'),
                'category_level3_name':row.get('category_level3_name','UNKNOWN'),
                'source_line':line_no,'source_file':'items_lite/train.jsonl'})
    if item_conflicts:p.error('Duplicate item IDs require review before join.')
    result={'mode':'public_real_subset','snapshot_id':'ksl-'+lock['revision'][:12]+'-'+hashlib.sha256((a.seed+str(a.percent)).encode()).hexdigest()[:10],
        'source':{'repo':lock['repo_id'],'revision':lock['revision'],'raw_files_sha256':{e['path']:e['sha256'] for e in lock['files']},
        'nature':'public historical dataset; deterministic user-hash subset',
        'collection_note':'Full source window: two months starting 2025-06-01. Lite: continuous one-month subset; exact month not disclosed here.',
        'sampling':{'unit':'user','seed':a.seed,'percent':a.percent,'retained_complete_user_records':True},
        'counts':{'raw_recall_rows_scanned':raw_count,'raw_item_rows_scanned':metadata_count,'sample_users':len(users)},
        'missing_item_ids_count':len(wanted-seen_items)},'items':items,'requests':requests}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    summary={'mode':result['mode'],'metrics':metrics(requests),'flow':category_flows(requests,items),'output_sha256':sha256(a.output)}
    a.output.with_suffix('.audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Wrote {len(requests)} complete requests, {len(items)} item metadata rows. This is a subset, not the full platform.')
if __name__=='__main__':main()
