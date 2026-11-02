#!/usr/bin/env python3
"""Streaming field audit. Does NOT mark an entire file audited after --limit."""
from __future__ import annotations
import argparse, collections, hashlib, json, sys
from pathlib import Path
from domain import validate_request, id_set, id_string, FIELDS

def audit(path: Path, kind: str, limit: int=0) -> dict:
    counts=collections.Counter(); fields=collections.Counter(); splits=collections.Counter()
    errors=[]; shapes=collections.Counter(); full=True
    with path.open('r',encoding='utf-8-sig') as f:
        for number,line in enumerate(f,1):
            if limit and number>limit: full=False; break
            counts['lines']+=1
            try:
                row=json.loads(line)
                if not isinstance(row,dict): raise ValueError('row not object')
                fields.update(row.keys())
                if kind=='recall':
                    validate_request(row)
                    for key in ('user_id','session_id'):
                        if key not in row: raise ValueError('missing '+key)
                        id_string(row[key])
                    i,c,p=(id_set(row[x]) for x in FIELDS)
                    counts.update(orphan_click_pairs=len(c-i),orphan_purchase_pairs=len(p-i),
                        purchase_without_click_pairs=len((p&i)-c),
                        duplicate_list_entries=sum(len(row[x])-len(id_set(row[x])) for x in FIELDS),
                        empty_exposure_requests=int(not i),missing_time_index=int('time_index' not in row),
                        empty_query_requests=int(not row['query'].strip()))
                    splits[str(row.get('split','<MISSING>'))]+=1
                    for key in FIELDS:
                        shapes.update([key+':'+type(value).__name__ for value in row[key]])
                else:
                    for key in ('item_id','item_title'):
                        if key not in row: raise ValueError('missing '+key)
                    counts['unknown_category_rows']+=int(row.get('category_level1_id') in (0,None,'0'))
                counts['valid_rows']+=1
            except (ValueError,TypeError,KeyError) as exc:
                counts['invalid_rows']+=1
                if len(errors)<20: errors.append({'source_line':number,'error':str(exc)})
    return {'file':str(path),'kind':kind,'full_scan':full,'counts':dict(counts),'field_presence':dict(fields),
        'splits':dict(splits),'list_shapes':dict(shapes),'errors':errors,
        'note':'Raw identifiers/queries omitted from log. Request-key uniqueness and joins still require separate audits.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--kind',choices=['recall','items'],required=True)
    p.add_argument('--limit',type=int,default=0);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.limit<0: p.error('--limit must be nonnegative')
    report=audit(a.file,a.kind,a.limit);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return int(report['counts'].get('invalid_rows',0)>0)
if __name__=='__main__':raise SystemExit(main())
