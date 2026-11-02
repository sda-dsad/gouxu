"""Parquet ingestion and parameterized read-only DuckDB scope queries."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,re,shutil,uuid,copy,threading
import duckdb,pyarrow as pa,pyarrow.parquet as pq
import jsonschema
from .config import ROOT,STATE,VERSION,PALETTE
from .domain.metrics import validate_request,id_set,id_string,metrics
from .state import job_cancelled,job_update,connection,now
from .query_cache import QueryResultCache
QUERY_SLOTS=threading.BoundedSemaphore(2)

def safe_text(value):
    value=str(value)
    value=re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[邮箱已隐藏]',value)
    return re.sub(r'(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)','[号码已隐藏]',value)
def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def verify_prepared_snapshot(folder:Path):
    meta=json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
    lock=json.loads((ROOT/'contracts/source.lock.json').read_text(encoding='utf-8'))
    sid=meta.get('snapshot_id','')
    expected={f['path']:f['sha256'] for f in lock['files']}
    if not re.fullmatch(r'ksl-full-[A-Za-z0-9_-]{1,80}',sid) or folder.name!=sid:
        raise ValueError('Invalid full-Lite snapshot identity')
    if not meta.get('prepared_full_lite') or meta.get('data_mode')!='public_real_subset' or meta.get('schema_version')!=2:
        raise ValueError('Full-Lite prepared format is not verified')
    if meta['source'].get('revision')!=lock['revision'] or meta['source'].get('hashes')!=expected or meta['source'].get('sampling',{}).get('percent')!=100:
        raise ValueError('Full-Lite source does not match the locked files')
    quality=meta['quality']
    if quality.get('status')!='passed_local_semantics' or not quality.get('full_scan'):
        raise ValueError('Full-source semantics not audited')
    files=meta.get('prepared_files',{})
    if set(files)!={'requests.parquet','pairs.parquet','items.parquet','queries.parquet','facts.parquet','item_stats.parquet'}:
        raise ValueError('Prepared tables are incomplete')
    for name,receipt in files.items():
        path=folder/name
        if path.stat().st_size!=receipt['bytes'] or fingerprint(path)!=receipt['sha256']:
            raise ValueError('Prepared file hash mismatch')
    for name,column in [('requests','requests'),('items','items'),('queries','queries')]:
        if pq.ParquetFile(folder/(name+'.parquet')).metadata.num_rows!=meta['counts'][column]:
            raise ValueError('Prepared row count mismatch')
    if pq.ParquetFile(folder/'pairs.parquet').metadata.num_rows!=pq.ParquetFile(folder/'facts.parquet').metadata.num_rows:
        raise ValueError('Prepared facts omit feedback pairs')
    if meta['global_model']['requests']!=meta['counts']['requests'] or any(meta['global_model'][k]!=quality['independent_sql_totals'][k] for k in ('E','C','P','orphanC','orphanP','purchaseWithoutClick')):
        raise ValueError('Cached full scope differs from verified metrics')
    return meta
def query_key(query):return hashlib.sha256(query.encode('utf-8')).hexdigest()[:24]
def rate(n,d):return n/d if d else None
def ceil_domain(maximum):
    maximum=max(1,maximum);quantum=10**max(1,len(str(maximum))-2)
    return math.ceil(maximum/quantum)*quantum

def feedback_input(row):
    fields=('impressed_item_ids','clicked_item_ids','purchased_item_ids')
    source=row.get('source_feedback_lists')
    if source is not None:
        if not isinstance(source,dict) or set(source)!=set(fields) or any(id_set(source[f])!=id_set(row[f]) for f in fields):raise ValueError('源列表与规范化集合不一致')
    original={f:(source or row)[f] for f in fields}
    duplicates=sum(len(original[f])-len(id_set(original[f])) for f in fields)
    original['__basis__']='provided_source_lists' if source is not None else 'normalized_input'
    return json.dumps(original,ensure_ascii=False),duplicates

class ImportCancelled(Exception):pass

def ingest(path:Path,owner:str|None=None,job:str|None=None,allow_real=False):
    data=json.loads(path.read_text(encoding='utf-8'))
    jsonschema.validate(data,json.loads((ROOT/'contracts/normalized.schema.json').read_text(encoding='utf-8')))
    if data['mode']=='public_real_subset' and not allow_real:
        raise ValueError('真实公开模式需要已核验的注册输入')
    if data['mode']=='public_real_subset':
        manifest=json.loads(path.with_name('manifest.json').read_text(encoding='utf-8'))
        lock=json.loads((ROOT/'contracts/source.lock.json').read_text(encoding='utf-8'))
        if manifest['quality']!='passed_local_semantics' or manifest['subset_sha256']!=fingerprint(path):
            raise ValueError('子集哈希或语义审查未通过')
        if manifest['source']['revision']!=lock['revision'] or manifest['source']['hashes']!={x['path']:x['sha256'] for x in lock['files']}:
            raise ValueError('真实来源版本与锁文件不符')
    sid=data['snapshot_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',sid):raise ValueError('无效快照ID')
    source_hash=fingerprint(path);target=STATE/'analytics'/sid
    if (target/'metadata.json').exists():
        old=json.loads((target/'metadata.json').read_text())
        if old['file_hash']!=source_hash:raise ValueError('同快照ID对应不同内容，禁止覆盖')
        if old.get('schema_version',1)<2:
            input_by_id={id_string(r['request_id']):r for r in data['requests']}
            records=pq.read_table(target/'requests.parquet').to_pylist()
            for r in records:r['feedback_input'],r['duplicate_list_entries']=feedback_input(input_by_id[r['request_id']])
            table=pa.Table.from_pylist(records)
            temporary=target/('requests-'+uuid.uuid4().hex+'.tmp.parquet')
            pq.write_table(table,temporary,compression='zstd')
            backup=target/'requests-schema-v1.parquet'
            if not backup.exists():shutil.copyfile(target/'requests.parquet',backup)
            temporary.replace(target/'requests.parquet');old['schema_version']=2
            old['quality']['metrics']['source_duplicate_list_entries']=sum(r['duplicate_list_entries'] for r in records)
            (target/'metadata.json').write_text(json.dumps(old,ensure_ascii=False),encoding='utf-8')
        register(old,owner,job)
        return old
    staging=STATE/'analytics'/('staging-'+uuid.uuid4().hex)
    staging.mkdir(parents=True)
    def cancelled():
        if job and job_cancelled(job):raise ImportCancelled()
    try:
        requests=[];pairs=[];items=[];seen_requests=set();seen_items=set();category_names={}
        for n,row in enumerate(data['requests']):
            validate_request(row);rid=id_string(row['request_id'])
            if rid in seen_requests:raise ValueError('重复请求ID')
            seen_requests.add(rid);i,c,p=(id_set(row[f]) for f in ('impressed_item_ids','clicked_item_ids','purchased_item_ids'))
            original,duplicates=feedback_input(row)
            requests.append({'request_id':rid,'query_key':query_key(row['query']),'query_display':safe_text(row['query']),'feedback_input':original,'duplicate_list_entries':duplicates,
                             'query_raw':row['query'],'split_raw':str(row.get('split') or '<MISSING>'),
                             'time_index_raw':str(row['time_index']) if row.get('time_index') is not None else None,
                             'source_line':row.get('source_line'),'source_file':row.get('source_file')})
            for iid in sorted(i|c|p):pairs.append({'request_id':rid,'item_id':iid,'impressed':iid in i,'clicked':iid in c,'purchased':iid in p})
            if n%200==0:
                cancelled()
                if job:job_update(job,'running',{'requests':n,'total':len(data['requests'])})
        for index,item in enumerate(data['items'],1):
            iid=id_string(item['item_id'])
            if iid in seen_items:raise ValueError('重复商品ID')
            seen_items.add(iid);cid=id_string(item['category_level1_id']);name=item['category_level1_name']
            if cid in ('0','UNKNOWN') or not name.strip():cid='UNKNOWN';name='未匹配类目'
            if cid in category_names and category_names[cid]!=name:raise ValueError('一级类目ID对应多个名称')
            category_names[cid]=name
            items.append({'item_id':iid,'title_raw':item['item_title'],'title':safe_text(item['item_title']),
                          'category_id':cid,'category_name':name,'stable_index':int(item.get('index',index)),
                          'source_line':item.get('source_line'),'source_file':item.get('source_file')})
        cancelled()
        schemas={
          'requests':pa.schema([('request_id',pa.string()),('query_key',pa.string()),('query_display',pa.string()),('query_raw',pa.string()),('split_raw',pa.string()),('time_index_raw',pa.string()),('source_line',pa.int64()),('source_file',pa.string()),('feedback_input',pa.string()),('duplicate_list_entries',pa.int64())]),
          'pairs':pa.schema([('request_id',pa.string()),('item_id',pa.string()),('impressed',pa.bool_()),('clicked',pa.bool_()),('purchased',pa.bool_())]),
          'items':pa.schema([('item_id',pa.string()),('title_raw',pa.string()),('title',pa.string()),('category_id',pa.string()),('category_name',pa.string()),('stable_index',pa.int64()),('source_line',pa.int64()),('source_file',pa.string())])}
        for name,rows in [('requests',requests),('pairs',pairs),('items',items)]:
            cancelled();pq.write_table(pa.Table.from_pylist(rows,schema=schemas[name]),staging/(name+'.parquet'),compression='zstd')
        # Derive the immutable category registry and scales from the entire snapshot.
        weights=Counter();lookup={x['item_id']:x for x in items};item_counts=Counter()
        for p in pairs:
            if p['impressed']:
                weights[lookup.get(p['item_id'],{}).get('category_id','UNKNOWN')]+=1;item_counts[p['item_id']]+=1
        if data['mode']=='synthetic' and data.get('categories'):
            keep=[c['id'] for c in data['categories']][:7]
            identities={c['id']:{'id':c['id'],'name':c['name'],'color':c['color'],'textColor':c['text_color']} for c in data['categories']}
        else:
            keep=[c for c,n in sorted(weights.items(),key=lambda x:(-x[1],x[0])) if c!='UNKNOWN'][:7]
            identities={cid:{'id':cid,'name':category_names[cid],'color':PALETTE[n][0],'textColor':PALETTE[n][1]} for n,cid in enumerate(keep)}
        identities['OTHER']={'id':'OTHER','name':'其他类目','color':'#a4b794','textColor':'#596d46'}
        identities['UNKNOWN']={'id':'UNKNOWN','name':'未匹配类目','color':'#a3ada6','textColor':'#536257'}
        other=sum(n for c,n in weights.items() if c not in keep and c!='UNKNOWN')
        raw_source=data['source']
        source={k:raw_source[k] for k in ('revision','sampling','license_status','nature','window','collection_note','repo') if k in raw_source}
        source['hashes']={k:v for k,v in raw_source.get('hashes',{}).items() if isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v)}
        source.setdefault('window',raw_source.get('collection_note','没有真实业务采集日期；自建合成样本。' if data['mode']=='synthetic' else '授权日志，时间含义以原字段审查为准。'))
        source.setdefault('license_status','自建合成样本，非真实业务数据。' if data['mode']=='synthetic' else '用户声明有权导入；实际使用与再分发条件需保留。')
        metadata={'schema_version':2,'snapshot_id':sid,'data_mode':data['mode'],'file_hash':source_hash,'metric_version':VERSION,'registry':identities,
                  'keep':keep,'all_category_names':category_names,
                  'scale_spec':{'search_max':ceil_domain(max([weights[c] for c in keep]+[other,weights['UNKNOWN'],1])),
                                'item_max':ceil_domain(max(item_counts.values(),default=1))},
                  'source':source,'quality':{'normalization':'validated','metrics':{**metrics(data['requests']),'source_duplicate_list_entries':sum(r['duplicate_list_entries'] for r in requests)}},
                  'counts':{'requests':len(requests),'items':len(items),'queries':len(set(x['query_key'] for x in requests))},
                  'splits':sorted(set(r['split_raw'] for r in requests)),'title':'合成演示样本' if data['mode']=='synthetic' else 'KuaiSearch-Lite · 1%用户子集' if data['mode']=='public_real_subset' else '授权导入日志'}
        (staging/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf-8')
        cancelled()
        # No live snapshot is registered until every Parquet file is complete.
        if target.exists():raise ValueError('快照目录已存在但未完成，需人工检查')
        with connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if job:
                row=db.execute('SELECT state FROM jobs WHERE job_id=?',(job,)).fetchone()
                if not row or row['state']=='cancelled':raise ImportCancelled()
            staging.rename(target)
            register_db(db,metadata,owner,job)
        return metadata
    except Exception:
        resolved=staging.resolve()
        if STATE.resolve() in resolved.parents and resolved.exists():shutil.rmtree(resolved)
        raise

def register_db(db,metadata,owner,job=None):
    if job:
        row=db.execute('SELECT state FROM jobs WHERE job_id=?',(job,)).fetchone()
        if not row or row['state']=='cancelled':raise ImportCancelled()
    db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?,?)',(metadata['snapshot_id'],metadata['data_mode'],metadata['source'].get('revision'),json.dumps(metadata,ensure_ascii=False),'ready',now()))
    db.execute('INSERT OR IGNORE INTO import_keys VALUES (?,?)',(metadata['file_hash'],metadata['snapshot_id']))
    if owner:db.execute('INSERT OR IGNORE INTO snapshot_owners VALUES (?,?)',(metadata['snapshot_id'],owner))
    if job:db.execute("UPDATE jobs SET state='succeeded',progress_json=?,finished_at=? WHERE job_id=?",(json.dumps({'snapshot_id':metadata['snapshot_id'],'requests':metadata['counts']['requests']}),now(),job))

def register(metadata,owner,job=None):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        register_db(db,metadata,owner,job)

class Analytics:
    def __init__(self,metadata):
        self.meta=metadata;self.folder=STATE/'analytics'/metadata['snapshot_id']
        self._query_results=QueryResultCache()
        self.scale_spec=copy.deepcopy(metadata['scale_spec'])
        global_model=metadata.get('global_model')
        if global_model:
            raw=[c for c in global_model['categories'] if c['id']!='OTHER']+global_model.get('other_categories',[])
            self.scale_spec['search_max']=ceil_domain(max((c['E'] for c in raw),default=1))
    def category_identity(self,cid):
        if cid in self.meta['registry'] and cid!='OTHER':return self.meta['registry'][cid]
        ordered=sorted(self.meta['all_category_names'])
        n=ordered.index(cid) if cid in ordered else 0
        color,text_color=PALETTE[n%len(PALETTE)]
        return {'id':cid,'name':self.meta['all_category_names'].get(cid,cid),'color':color,'textColor':text_color}
    def named_categories(self,rows):
        return [{**self.category_identity(c['id']),**c} for c in sorted(rows,key=lambda c:(-c['E'],c['id'])) if c['E']>0]
    def run(self,sql,params=()):
        return self._query_results.get_or_compute((sql,tuple(params)),lambda:self._execute(sql,params))
    def _execute(self,sql,params):
        with QUERY_SLOTS:
            temp=STATE/'duckdb-temp'/uuid.uuid4().hex;temp.mkdir(parents=True)
            try:
                with duckdb.connect(config={'threads':2,'memory_limit':'256MB','temp_directory':str(temp),'max_temp_directory_size':'2GB'}) as db:
                    for name in ('requests','pairs','items'):db.from_parquet(str(self.folder/(name+'.parquet'))).create_view(name)
                    for name in ('facts','item_stats','queries'):
                        if (self.folder/(name+'.parquet')).is_file():db.from_parquet(str(self.folder/(name+'.parquet'))).create_view(name)
                    result=db.execute(sql,params);columns=[c[0] for c in result.description]
                    return [dict(zip(columns,row)) for row in result.fetchall()]
            finally:
                if temp.exists() and STATE.resolve() in temp.resolve().parents and re.fullmatch('[0-9a-f]{32}',temp.name):shutil.rmtree(temp)
    def where(self,spec):
        conditions=['TRUE'];params=[]
        for column,values in [('query_key',spec.get('exact_query_keys',[])),('split_raw',spec['split_policy'])]:
            if values:conditions.append('r.'+column+' IN ('+','.join('?' for _ in values)+')');params.extend(values)
        return ' AND '.join(conditions),params
    def queries(self,search='',cursor=0,limit=200):
        names='SELECT query_key,query,requests FROM queries' if (self.folder/'queries.parquet').is_file() else 'SELECT query_key,max(query_display) AS query,count(*) AS requests FROM requests GROUP BY query_key'
        exposed='SELECT query_key,count(*) AS E FROM facts WHERE impressed GROUP BY query_key' if (self.folder/'facts.parquet').is_file() else 'SELECT r.query_key,count(*) FILTER(WHERE p.impressed) AS E FROM requests r LEFT JOIN pairs p USING(request_id) GROUP BY r.query_key'
        return self.run('WITH names AS ('+names+'),exposed AS ('+exposed+') SELECT n.query_key AS key,n.query,n.requests,coalesce(x.E,0) AS E FROM names n LEFT JOIN exposed x USING(query_key) WHERE contains(n.query,?) ORDER BY E DESC,n.requests DESC,n.query_key LIMIT ? OFFSET ?',(search,limit,cursor))
    def valid_keys(self,requested=None):
        if requested:
            return {x['query_key'] for x in self.run('SELECT DISTINCT query_key FROM requests WHERE query_key IN ('+','.join('?' for _ in requested)+')',requested)}
        return {x['query_key'] for x in self.run('SELECT DISTINCT query_key FROM requests')}
    def is_global(self,spec):
        return not spec.get('exact_query_keys') and (not spec.get('split_policy') or set(spec['split_policy'])==set(self.meta['splits']))
    def model(self,spec,scope_id):
        if self.is_global(spec) and self.meta.get('global_model'):
            value=copy.deepcopy(self.meta['global_model'])
            rows=self.run('SELECT categoryId AS id,sum(E) AS E,sum(C) AS C,sum(P) AS P FROM item_stats GROUP BY categoryId')
            value['categories']=self.named_categories(rows);value['other_categories']=[];value['scale_spec']=self.scale_spec
            assert all(sum(c[k] for c in value['categories'])==value[k] for k in ('E','C','P'))
            value.update(snapshot_id=self.meta['snapshot_id'],scope_id=scope_id,exact_queries=spec['exact_query_keys'],split_policy=spec['split_policy'])
            value['warnings']=(['synthetic_not_real_business_statistics'] if self.meta['data_mode']=='synthetic' else [])+(['zero_denominator'] if value['E']==0 else [])
            return value
        if (self.folder/'facts.parquet').is_file():return self.fact_model(spec,scope_id)
        where,params=self.where(spec)
        totals=self.run('''SELECT count(*) FILTER(WHERE p.impressed) AS E,
            count(*) FILTER(WHERE p.impressed AND p.clicked) AS C,
            count(*) FILTER(WHERE p.impressed AND p.purchased) AS P,
            count(*) FILTER(WHERE NOT p.impressed AND p.clicked) AS orphanC,
            count(*) FILTER(WHERE NOT p.impressed AND p.purchased) AS orphanP,
            count(*) FILTER(WHERE p.impressed AND p.purchased AND NOT p.clicked) AS purchaseWithoutClick
            FROM pairs p JOIN requests r USING(request_id) WHERE '''+where,params)[0]
        requests=self.run('SELECT count(*) AS n FROM requests r WHERE '+where,params)[0]['n']
        request_metrics=self.run('''SELECT count(DISTINCT r.request_id) FILTER(WHERE p.impressed AND p.clicked) AS clicked_requests,
            count(DISTINCT r.request_id) FILTER(WHERE p.impressed AND p.purchased) AS purchased_requests,
            count(DISTINCT p.item_id) FILTER(WHERE p.impressed) AS exposed_items,
            count(DISTINCT p.item_id) FILTER(WHERE p.impressed AND i.item_id IS NOT NULL) AS metadata_items
            FROM pairs p JOIN requests r USING(request_id) LEFT JOIN items i USING(item_id) WHERE '''+where,params)[0]
        duplicates=self.run('SELECT coalesce(sum(duplicate_list_entries),0) AS n FROM requests r WHERE '+where,params)[0]['n'] if self.meta.get('schema_version',1)>=2 else None
        categories=self.run('''SELECT coalesce(i.category_id,'UNKNOWN') AS id,
            count(*) AS E,count(*) FILTER(WHERE p.clicked) AS C,count(*) FILTER(WHERE p.purchased) AS P
            FROM pairs p JOIN requests r USING(request_id) LEFT JOIN items i USING(item_id)
            WHERE p.impressed AND '''+where+' GROUP BY 1',params)
        by_id={x['id']:x for x in categories};out=self.named_categories(categories)
        assert sum(c['E'] for c in out)==totals['E']
        E=totals['E'];metrics_out={**totals,**request_metrics,'requests':requests,'duplicate_list_entries':duplicates,'pair_click_rate':rate(totals['C'],E),'pair_purchase_feedback_rate':rate(totals['P'],E),'request_click_rate':rate(request_metrics['clicked_requests'],requests),'request_purchase_feedback_rate':rate(request_metrics['purchased_requests'],requests)}
        return {'snapshot_id':self.meta['snapshot_id'],'scope_id':scope_id,'metric_version':VERSION,'data_mode':self.meta['data_mode'],
                'unit':'request_item_pair','denominator':E,'metrics':metrics_out,'warnings':(['synthetic_not_real_business_statistics'] if self.meta['data_mode']=='synthetic' else [])+(['zero_denominator'] if E==0 else []),
                'exact_queries':spec['exact_query_keys'],'split_policy':spec['split_policy'],'requests':requests,**totals,
                'categories':out,'products':[],'other_categories':[],
                'scale_spec':self.scale_spec,'coverage':{'metadata_pairs':rate(E-by_id.get('UNKNOWN',{}).get('E',0),E),'metadata_items':rate(request_metrics['metadata_items'],request_metrics['exposed_items']),'matched_items':request_metrics['metadata_items'],'exposed_items':request_metrics['exposed_items']}}
    def fact_model(self,spec,scope_id):
        where,params=self.where(spec);where=where.replace('r.','p.')
        totals=self.run('''SELECT count(*) FILTER(WHERE impressed) AS E,count(*) FILTER(WHERE impressed AND clicked) AS C,
            count(*) FILTER(WHERE impressed AND purchased) AS P,count(*) FILTER(WHERE NOT impressed AND clicked) AS orphanC,
            count(*) FILTER(WHERE NOT impressed AND purchased) AS orphanP,count(*) FILTER(WHERE impressed AND purchased AND NOT clicked) AS purchaseWithoutClick,
            count(DISTINCT request_id) FILTER(WHERE impressed AND clicked) AS clicked_requests,
            count(DISTINCT request_id) FILTER(WHERE impressed AND purchased) AS purchased_requests,
            count(DISTINCT item_id) FILTER(WHERE impressed) AS exposed_items,
            count(DISTINCT item_id) FILTER(WHERE impressed AND metadata_matched) AS metadata_items FROM facts p WHERE '''+where,params)[0]
        rw,rp=self.where(spec)
        request=self.run('SELECT count(*) AS n,coalesce(sum(duplicate_list_entries),0) AS duplicates FROM requests r WHERE '+rw,rp)[0]
        categories=self.run('''SELECT category_id AS id,count(*) AS E,count(*) FILTER(WHERE clicked) AS C,count(*) FILTER(WHERE purchased) AS P
            FROM facts p WHERE impressed AND '''+where+' GROUP BY category_id',params)
        by_id={c['id']:c for c in categories};out=self.named_categories(categories)
        assert sum(c['E'] for c in out)==totals['E']
        E=totals['E'];requests=request['n'];metrics_out={**totals,'requests':requests,'duplicate_list_entries':request['duplicates'],
            'pair_click_rate':rate(totals['C'],E),'pair_purchase_feedback_rate':rate(totals['P'],E),
            'request_click_rate':rate(totals['clicked_requests'],requests),'request_purchase_feedback_rate':rate(totals['purchased_requests'],requests)}
        return {'snapshot_id':self.meta['snapshot_id'],'scope_id':scope_id,'metric_version':VERSION,'data_mode':self.meta['data_mode'],
            'unit':'request_item_pair','denominator':E,'metrics':metrics_out,
            'warnings':(['synthetic_not_real_business_statistics'] if self.meta['data_mode']=='synthetic' else [])+(['zero_denominator'] if E==0 else []),
            'exact_queries':spec['exact_query_keys'],'split_policy':spec['split_policy'],'requests':requests,
            **{k:totals[k] for k in ('E','C','P','orphanC','orphanP','purchaseWithoutClick')},'categories':out,'products':[],
            'other_categories':[],
            'scale_spec':self.scale_spec,'coverage':{'metadata_pairs':rate(E-by_id.get('UNKNOWN',{}).get('E',0),E),
                'metadata_items':rate(totals['metadata_items'],totals['exposed_items']),'matched_items':totals['metadata_items'],'exposed_items':totals['exposed_items']}}
    def item_rows(self,spec,limit=80,cursor=0,minimum=0,category=None,item_id=None,selected=None,find=''):
        where,params=self.where(spec);params=list(params)
        if item_id:where+=' AND p.item_id=?';params.append(item_id)
        stats='''SELECT p.item_id AS id,coalesce(max(i.title),p.item_id) AS title,
            coalesce(max(i.category_id),'UNKNOWN') AS categoryId,coalesce(max(i.stable_index),0) AS index,
            count(*) FILTER(WHERE p.impressed) AS E,count(*) FILTER(WHERE p.impressed AND p.clicked) AS C,
            count(*) FILTER(WHERE p.impressed AND p.purchased) AS P
            FROM pairs p JOIN requests r USING(request_id) LEFT JOIN items i USING(item_id)
            WHERE '''+where+' GROUP BY p.item_id'
        if self.is_global(spec) and (self.folder/'item_stats.parquet').is_file():
            stats='SELECT id,title,categoryId,index,E,C,P FROM item_stats'
            params=[]
            if item_id:stats+=' WHERE id=?';params=[item_id]
        elif (self.folder/'facts.parquet').is_file():
            stats='''SELECT p.item_id AS id,coalesce(max(p.title),p.item_id) AS title,
                max(p.category_id) AS categoryId,max(p.stable_index) AS index,
                count(*) FILTER(WHERE impressed) AS E,count(*) FILTER(WHERE impressed AND clicked) AS C,
                count(*) FILTER(WHERE impressed AND purchased) AS P FROM facts p WHERE '''+where.replace('r.','p.')+' GROUP BY p.item_id'
        conditions=[];filter_params=[]
        if not item_id:conditions.append('E>=?');filter_params.append(max(1,minimum))
        if category:
            if category=='OTHER':
                conditions.append('categoryId NOT IN ('+','.join('?' for _ in self.meta['keep']+['UNKNOWN'])+')')
                filter_params+=self.meta['keep']+['UNKNOWN']
            else:conditions.append('categoryId=?');filter_params.append(category)
        if find:conditions.append('(contains(title,?) OR contains(id,?))');filter_params += [find,find]
        filtered='SELECT * FROM ('+stats+') WHERE '+(' AND '.join(conditions) or 'TRUE')
        all_params=params+filter_params
        total=self.run('SELECT count(*) AS n FROM ('+stats+')',params)[0]['n']
        eligible=self.run('SELECT count(*) AS n FROM ('+filtered+')',all_params)[0]['n']
        rows=self.run(filtered+' ORDER BY E DESC,id LIMIT ? OFFSET ?',all_params+[limit,cursor])
        if item_id and not rows:
            found=self.run('SELECT item_id AS id,title,category_id AS categoryId,stable_index AS index FROM items WHERE item_id=?',(item_id,))
            rows=[{**found[0],'E':0,'C':0,'P':0}] if found else [{'id':item_id,'title':'元数据未匹配 · '+item_id,'categoryId':'UNKNOWN','index':0,'E':0,'C':0,'P':0}]
        if selected and cursor==0 and all(p['id']!=selected for p in rows):
            pinned=self.run('SELECT * FROM ('+filtered+') WHERE id=?',all_params+[selected])
            if pinned:rows=rows[:max(0,limit-1)]+[pinned[0]]
        for p in rows:
            p['displayCategoryId']=p['categoryId']
            p['click_rate']=rate(p['C'],p['E']);p['purchase_rate']=rate(p['P'],p['E'])
            p['categoryName']=self.meta['all_category_names'].get(p['categoryId'],'未匹配类目')
            identity=self.category_identity(p['categoryId']);p['color']=identity['color'];p['textColor']=identity['textColor']
        return {'items':rows,'total':total,'eligible':eligible,'cursor':cursor,'next_cursor':cursor+limit if cursor+limit<eligible else None,
                'visible_exposed_pairs':sum(p['E'] for p in rows)}
    def evidence(self,spec,cursor=0,limit=50,item_id=None,category_id=None):
        where,params=self.where(spec);params=list(params)
        condition=''
        if item_id:condition=' AND p.impressed AND p.item_id=?';params.append(item_id)
        if category_id:
            if category_id=='OTHER':
                condition+=" AND p.impressed AND coalesce(i.category_id,'UNKNOWN') NOT IN ("+','.join('?' for _ in self.meta['keep']+['UNKNOWN'])+')'
                params+=self.meta['keep']+['UNKNOWN']
            else:condition+=" AND p.impressed AND coalesce(i.category_id,'UNKNOWN')=?";params.append(category_id)
        ids_sql='SELECT DISTINCT r.request_id FROM requests r JOIN pairs p USING(request_id) LEFT JOIN items i USING(item_id) WHERE '+where+condition if item_id or category_id else 'SELECT r.request_id FROM requests r WHERE '+where
        if (item_id or category_id) and (self.folder/'facts.parquet').is_file():
            ids_sql='SELECT DISTINCT p.request_id FROM facts p WHERE '+where.replace('r.','p.')+condition.replace("coalesce(i.category_id,'UNKNOWN')",'p.category_id')
        count=self.run('SELECT count(*) AS n FROM ('+ids_sql+')',params)[0]['n']
        raw_columns=',feedback_input,duplicate_list_entries' if self.meta.get('schema_version',1)>=2 else ''
        chosen=self.run('SELECT request_id,query_display AS query,split_raw AS split,time_index_raw AS time_index,source_file,source_line'+raw_columns+' FROM requests WHERE request_id IN ('+ids_sql+') ORDER BY request_id LIMIT ? OFFSET ?',params+[limit,cursor])
        ids=[r['request_id'] for r in chosen]
        pair_rows=self.run('SELECT request_id,item_id,impressed,clicked,purchased FROM pairs WHERE request_id IN ('+','.join('?' for _ in ids)+') ORDER BY request_id,item_id',ids) if ids else []
        by_request={rid:[] for rid in ids}
        for p in pair_rows:by_request[p['request_id']].append(p)
        records=[]
        for r in chosen:
            p=by_request[r['request_id']]
            r.update({field:[x['item_id'] for x in p if x[flag]] for field,flag in [('impressed_item_ids','impressed'),('clicked_item_ids','clicked'),('purchased_item_ids','purchased')]})
            original=r.pop('feedback_input',None)
            if original is not None:
                r['original_feedback_lists']=json.loads(original)
                r['feedback_list_basis']=r['original_feedback_lists'].pop('__basis__','normalized_input')
                for field,values in r['original_feedback_lists'].items():r[field]=[id_string(x['item_id'] if isinstance(x,dict) else x) for x in values]
            r['source_sha256']=self.meta['source'].get('hashes',{}).get(r['source_file'],self.meta['file_hash']);records.append(r)
        return {'snapshot_id':self.meta['snapshot_id'],'metric_version':VERSION,'data_mode':self.meta['data_mode'],'records':records,'total':count,'cursor':cursor,'next_cursor':cursor+limit if cursor+limit<count else None,
                'note':'完整规范化请求用于回查；如提供且校验源列表，则保留其次序和重复。整行不等于当前聚焦对象的独立贡献。用户标识未返回。'}
