"""Stream the two pinned Lite files into a separate, audited full-month snapshot.

Run inside the existing API image, with no network and a private output mount.
Never modifies the raw sources, the 1% subset, the database, or a live snapshot.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/api'))
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from app.analytics import safe_text, query_key, ceil_domain
from app.domain.metrics import id_string, id_set
from app.config import VERSION, PALETTE

FIELDS = ('impressed_item_ids', 'clicked_item_ids', 'purchased_item_ids')
SCHEMAS = {
 'requests': pa.schema([('request_id',pa.string()),('query_key',pa.string()),('query_display',pa.string()),('query_raw',pa.string()),('split_raw',pa.string()),('time_index_raw',pa.string()),('source_line',pa.int64()),('source_file',pa.string()),('feedback_input',pa.string()),('duplicate_list_entries',pa.int64())]),
 'pairs': pa.schema([('request_id',pa.string()),('item_id',pa.string()),('impressed',pa.bool_()),('clicked',pa.bool_()),('purchased',pa.bool_())]),
 'items': pa.schema([('item_id',pa.string()),('title_raw',pa.string()),('title',pa.string()),('category_id',pa.string()),('category_name',pa.string()),('stable_index',pa.int64()),('source_line',pa.int64()),('source_file',pa.string())])}


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    temp.replace(path)


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class Batches:
    def __init__(self, folder, name, size=8192):
        self.schema, self.rows, self.size = SCHEMAS[name], [], size
        self.writer = pq.ParquetWriter(folder / (name + '.parquet'), self.schema, compression='zstd')

    def add(self, row):
        self.rows.append(row)
        if len(self.rows) >= self.size:
            self.flush()

    def flush(self):
        if self.rows:
            self.writer.write_table(pa.Table.from_pylist(self.rows, schema=self.schema))
            self.rows.clear()

    def close(self):
        self.flush()
        self.writer.close()


def build(raw_root, lock_path, output, reports, memory='384MB', synthetic_test=False):
    started = time.monotonic()
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    names = {f['path']: f['sha256'] for f in lock['files']}
    if set(names) != {'recall_lite/train.jsonl', 'items_lite/train.jsonl'}:
        raise ValueError('Only the two locked Lite files are accepted')
    if not synthetic_test and lock['repo_id'] != 'benchen4395/KuaiSearch':
        raise ValueError('Unexpected source repository')
    sid = ('synthetic-full-lite-' if synthetic_test else 'ksl-full-') + lock['revision'][:12] + '-v1'
    target = output / sid
    staging = output / ('staging-' + sid)
    if target.exists() or staging.exists():
        raise ValueError('Snapshot/staging exists; never overwrite an existing build')
    os.umask(0o077)
    staging.mkdir(parents=True)
    reports.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()

    def progress(phase):
        save(reports / 'progress.json', {'status':'running', 'phase':phase, 'counts':dict(counts), 'elapsed_seconds':round(time.monotonic()-started, 1)})

    try:
        progress('source_hashes')
        raw_files = []
        for name, expected in names.items():
            path = raw_root / lock['revision'] / name
            actual = fingerprint(path)
            if actual != expected:
                raise ValueError('Locked source hash mismatch')
            raw_files.append({'path':name, 'bytes':path.stat().st_size, 'sha256':actual, 'match':True})
        save(reports / 'source-verification.json', {'revision':lock['revision'], 'files':raw_files, 'sampling_percent':100})

        keys = sqlite3.connect(staging / 'audit-keys.sqlite')
        keys.execute('CREATE TABLE request_keys(key BLOB PRIMARY KEY) WITHOUT ROWID')
        users, splits = set(), set()
        writers = {n:Batches(staging,n) for n in SCHEMAS}
        with (raw_root / lock['revision'] / 'recall_lite/train.jsonl').open(encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                row = json.loads(line)
                if not isinstance(row.get('query'),str) or not isinstance(row.get('split'),str):
                    raise ValueError('Unsupported query/split schema')
                if not isinstance(row.get('time_index'),int) or isinstance(row['time_index'],bool):
                    raise ValueError('Unsupported relative time index')
                user, session = id_string(row['user_id']), id_string(row['session_id'])
                key = hashlib.sha256(json.dumps([user,session,row['time_index'],row['split']],separators=(',',':')).encode()).digest()
                keys.execute('INSERT INTO request_keys VALUES (?)',(key,))
                users.add(hashlib.sha256(user.encode()).digest())
                i,c,p = (id_set(row[k]) for k in FIELDS)
                duplicates = sum(len(row[k])-len(values) for k,values in zip(FIELDS,(i,c,p)))
                counts.update(requests=1, exposed_pairs=len(i), clicked_pairs=len(i&c), purchased_pairs=len(i&p),
                              orphan_click_pairs=len(c-i), orphan_purchase_pairs=len(p-i), purchase_without_click_pairs=len((p&i)-c),
                              clicked_requests=int(bool(i&c)), purchased_requests=int(bool(i&p)),
                              empty_exposure_requests=int(not i), empty_query_requests=int(not row['query'].strip()),
                              duplicate_list_entries=duplicates)
                rid = 'KSL-' + str(line_no)
                original = {k:row[k] for k in FIELDS}; original['__basis__']='provided_source_lists'
                writers['requests'].add({'request_id':rid, 'query_key':query_key(row['query']), 'query_raw':row['query'],
                    'query_display':safe_text(row['query']), 'split_raw':row['split'], 'time_index_raw':str(row['time_index']),
                    'source_line':line_no, 'source_file':'recall_lite/train.jsonl',
                    'feedback_input':json.dumps(original,ensure_ascii=False,separators=(',',':')), 'duplicate_list_entries':duplicates})
                for iid in sorted(i|c|p):
                    writers['pairs'].add({'request_id':rid,'item_id':iid,'impressed':iid in i,'clicked':iid in c,'purchased':iid in p})
                splits.add(row['split'])
                if line_no % 10000 == 0:
                    keys.commit();progress('requests_and_pairs')
        keys.commit();keys.close()
        writers['requests'].close();writers['pairs'].close()

        categories = {}
        with (raw_root / lock['revision'] / 'items_lite/train.jsonl').open(encoding='utf-8') as f:
            for line_no, line in enumerate(f,1):
                row = json.loads(line)
                if not isinstance(row.get('item_title'),str):
                    raise ValueError('Unsupported item title schema')
                iid = id_string(row['item_id'])
                name = row.get('category_level1_name')
                cid = id_string(row['category_level1_id']) if row.get('category_level1_id') is not None else 'UNKNOWN'
                if cid in ('0','UNKNOWN') or not isinstance(name,str) or not name.strip():
                    cid,name='UNKNOWN','未匹配类目'
                if cid in categories and categories[cid] != name:
                    raise ValueError('Conflicting category identity')
                categories[cid] = name
                writers['items'].add({'item_id':iid,'title_raw':row['item_title'],'title':safe_text(row['item_title']),
                    'category_id':cid,'category_name':name,'stable_index':line_no,
                    'source_line':line_no,'source_file':'items_lite/train.jsonl'})
                counts['metadata_rows'] += 1
                if line_no % 100000 == 0:
                    progress('items')
        writers['items'].close()
        temp = staging / 'duckdb-temp'; temp.mkdir()
        db = duckdb.connect(config={'threads':1,'memory_limit':memory,'temp_directory':str(temp),'max_temp_directory_size':'5GB','preserve_insertion_order':False})
        for n in SCHEMAS:
            db.from_parquet(str(staging/(n+'.parquet'))).create_view(n)
        progress('uniqueness_and_sort')
        duplicates = db.execute('SELECT count(*)-count(DISTINCT item_id) FROM items').fetchone()[0]
        if duplicates:
            raise ValueError('Duplicate source item identity')
        for n,column in [('items','item_id'),('requests','query_key,request_id')]:
            ordered = staging / (n+'-ordered.parquet')
            db.execute('COPY (SELECT * FROM '+n+' ORDER BY '+column+') TO ? (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 16384)',[str(ordered)])
            ordered.replace(staging/(n+'.parquet'))
        db.execute('COPY (SELECT query_key,max(query_display) AS query,count(*) AS requests FROM requests GROUP BY query_key ORDER BY requests DESC,query_key) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)',[str(staging/'queries.parquet')])
        progress('full_item_aggregates')
        db.execute('COPY (SELECT item_id AS id,count(*) FILTER(WHERE impressed) AS E,count(*) FILTER(WHERE impressed AND clicked) AS C,count(*) FILTER(WHERE impressed AND purchased) AS P FROM pairs GROUP BY item_id) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)',[str(staging/'pair-stats.parquet')])
        db.from_parquet(str(staging/'pair-stats.parquet')).create_view('pair_stats')
        db.execute('''COPY (SELECT s.id,coalesce(i.title,s.id) AS title,coalesce(i.category_id,'UNKNOWN') AS categoryId,
            coalesce(i.stable_index,0) AS index,s.E,s.C,s.P,i.item_id IS NOT NULL AS metadata_matched
            FROM pair_stats s LEFT JOIN items i ON s.id=i.item_id ORDER BY s.E DESC,s.id)
            TO ? (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 16384)''',[str(staging/'item_stats.parquet')])
        db.from_parquet(str(staging/'item_stats.parquet')).create_view('item_stats')
        progress('query_sorted_facts')
        db.execute('''COPY (SELECT p.*,r.query_key,r.split_raw,i.title,coalesce(i.category_id,'UNKNOWN') AS category_id,
            coalesce(i.stable_index,0) AS stable_index,i.item_id IS NOT NULL AS metadata_matched
            FROM pairs p JOIN requests r USING(request_id) LEFT JOIN items i USING(item_id)
            ORDER BY r.query_key,p.request_id,p.item_id)
            TO ? (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 16384)''',[str(staging/'facts.parquet')])
        db.from_parquet(str(staging/'facts.parquet')).create_view('facts')
        progress('independent_sql_validation')
        totals = db.execute('''SELECT count(*) FILTER(WHERE impressed),count(*) FILTER(WHERE impressed AND clicked),
            count(*) FILTER(WHERE impressed AND purchased),count(*) FILTER(WHERE NOT impressed AND clicked),
            count(*) FILTER(WHERE NOT impressed AND purchased),count(*) FILTER(WHERE impressed AND purchased AND NOT clicked)
            FROM facts''').fetchone()
        metric_names = ['E','C','P','orphanC','orphanP','purchaseWithoutClick']
        metric_keys = ['exposed_pairs','clicked_pairs','purchased_pairs','orphan_click_pairs','orphan_purchase_pairs','purchase_without_click_pairs']
        if list(totals) != [counts[k] for k in metric_keys]:
            raise ValueError('Raw-source and derived SQL metrics disagree')
        sums = db.execute('SELECT sum(E),sum(C),sum(P) FROM item_stats').fetchone()
        if tuple(sums) != tuple(totals[:3]):
            raise ValueError('Item totals do not conserve full-scope counts')
        raw_categories = [dict(zip(['id','E','C','P'],row)) for row in db.execute('SELECT categoryId,sum(E),sum(C),sum(P) FROM item_stats WHERE E>0 GROUP BY categoryId ORDER BY sum(E) DESC,categoryId').fetchall()]
        keep = [c['id'] for c in raw_categories if c['id']!='UNKNOWN'][:7]
        registry = {cid:{'id':cid,'name':categories[cid],'color':PALETTE[n][0],'textColor':PALETTE[n][1]} for n,cid in enumerate(keep)}
        registry['OTHER']={'id':'OTHER','name':'其他类目','color':'#a4b794','textColor':'#596d46'}
        registry['UNKNOWN']={'id':'UNKNOWN','name':'未匹配类目','color':'#a3ada6','textColor':'#536257'}
        other = [c for c in raw_categories if c['id'] not in keep and c['id']!='UNKNOWN']
        by_id = {c['id']:c for c in raw_categories}
        shown = [{**registry[cid],**{k:by_id[cid][k] for k in ('E','C','P')}} for cid in keep]
        if other:
            shown.append({**registry['OTHER'],**{k:sum(c[k] for c in other) for k in ('E','C','P')}})
        if 'UNKNOWN' in by_id:
            shown.append({**registry['UNKNOWN'],**{k:by_id['UNKNOWN'][k] for k in ('E','C','P')}})
        if sum(c['E'] for c in shown) != totals[0]:
            raise ValueError('Category totals do not conserve full-scope exposures')
        exposed,matched = db.execute('SELECT count(*) FILTER(WHERE E>0),count(*) FILTER(WHERE E>0 AND metadata_matched) FROM item_stats').fetchone()
        max_item = db.execute('SELECT max(E) FROM item_stats').fetchone()[0] or 1
        query_count = db.execute('SELECT count(*) FROM read_parquet(?)',[str(staging/'queries.parquet')]).fetchone()[0]
        source = {'repo':lock['repo_id'],'revision':lock['revision'],'hashes':names,
            'sampling':{'unit':'user','percent':100,'complete_user_requests':True,'selection':'all Lite users; no sampling'},
            'window':'2025历史窗口；Lite连续一个月，具体月份未明确','license_status':lock['license_verification']}
        if synthetic_test:
            source['nature']='SYNTHETIC full-Lite structure test only; not real business data'
        scale = {'search_max':ceil_domain(max(c['E'] for c in shown)), 'item_max':ceil_domain(max_item)}
        ratio = lambda n,d:n/d if d else None
        metrics_out = {**dict(zip(metric_names,totals)), 'requests':counts['requests'],
            'clicked_requests':counts['clicked_requests'],'purchased_requests':counts['purchased_requests'],
            'exposed_items':exposed,'metadata_items':matched,'duplicate_list_entries':counts['duplicate_list_entries'],
            'pair_click_rate':ratio(totals[1],totals[0]),'pair_purchase_feedback_rate':ratio(totals[2],totals[0]),
            'request_click_rate':ratio(counts['clicked_requests'],counts['requests']),
            'request_purchase_feedback_rate':ratio(counts['purchased_requests'],counts['requests'])}
        coverage = {'metadata_pairs':ratio(totals[0]-by_id.get('UNKNOWN',{}).get('E',0),totals[0]),
            'metadata_items':ratio(matched,exposed),'matched_items':matched,'exposed_items':exposed}
        global_model = {'metric_version':VERSION,'data_mode':'synthetic' if synthetic_test else 'public_real_subset',
            'unit':'request_item_pair','denominator':totals[0],'metrics':metrics_out,'warnings':[],
            'requests':counts['requests'],**dict(zip(metric_names,totals)),'categories':shown,'products':[],
            'other_categories':[{'id':c['id'],'name':categories.get(c['id'],c['id']),'E':c['E']} for c in other],
            'scale_spec':scale,'coverage':coverage}
        quality = {'normalization':'validated','full_scan':True,'status':'passed_local_semantics',
            'source_rows':{'recall':counts['requests'],'items':counts['metadata_rows']},
            'metrics':dict(counts),'independent_sql_totals':dict(zip(metric_names,totals)),
            'coverage':coverage,'source_users':len(users),'duplicate_request_keys':0,'duplicate_item_ids':0,
            'source_duplicate_list_entries':counts['duplicate_list_entries']}
        metadata = {'schema_version':2,'prepared_full_lite':True,'snapshot_id':sid,
            'data_mode':'synthetic' if synthetic_test else 'public_real_subset','metric_version':VERSION,
            'file_hash':hashlib.sha256(json.dumps({'revision':lock['revision'],'hashes':names,'percent':100,'format':'full-lite-parquet-v1'},sort_keys=True).encode()).hexdigest(),
            'registry':registry,'keep':keep,'all_category_names':categories,'scale_spec':scale,
            'source':source,'quality':quality,'counts':{'requests':counts['requests'],'items':counts['metadata_rows'],'queries':query_count},
            'splits':sorted(splits),'title':'合成全量结构测试' if synthetic_test else 'KuaiSearch-Lite · 全量（100%）',
            'global_model':global_model}
        db.close()
        for name in ('audit-keys.sqlite','pair-stats.parquet'):
            (staging/name).unlink()
        # DuckDB owns its spill directory; it is empty after close.
        if not any(temp.iterdir()):
            temp.rmdir()
        file_hashes = {p.name:{'sha256':fingerprint(p),'bytes':p.stat().st_size} for p in staging.glob('*.parquet')}
        metadata['prepared_files']=file_hashes
        save(staging/'metadata.json',metadata)
        save(reports/'full-quality.json',{'snapshot_id':sid,'source':source,'quality':quality,'counts':metadata['counts'],'prepared_files':file_hashes})
        staging.rename(target)
        receipt = {'status':'ready_offline_not_registered','snapshot_id':sid,'counts':metadata['counts'],
            'metrics':dict(zip(metric_names,totals)),'elapsed_seconds':round(time.monotonic()-started,1),
            'parquet_bytes':sum(x['bytes'] for x in file_hashes.values())}
        save(reports/'progress.json',receipt)
        print(json.dumps(receipt))
        return metadata
    except Exception as exc:
        save(reports/'progress.json',{'status':'failed_not_registered','error_type':type(exc).__name__,
             'counts':dict(counts),'elapsed_seconds':round(time.monotonic()-started,1)})
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root',type=Path,required=True)
    parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reports',type=Path,required=True)
    parser.add_argument('--memory',default='384MB')
    args=parser.parse_args()
    build(args.raw_root,args.lock,args.output,args.reports,args.memory)
