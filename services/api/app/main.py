"""FastAPI routes, immutable scopes, persistent reviews, imports and exports."""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
import csv,hashlib,io,json,re,sqlite3,threading,time,uuid
from fastapi import FastAPI,Request,HTTPException,BackgroundTasks,UploadFile,File,Query
from fastapi.responses import JSONResponse,FileResponse
from fastapi.exceptions import RequestValidationError
from .config import ROOT,STATE,DATA,VERSION
from .state import initialize,connection,now,job_update,job_cancelled
from .analytics import Analytics,ingest,ImportCancelled,safe_text,rate,verify_prepared_snapshot,register
from .models import ScopeInput,CohortInput,CompareInput,ReviewInput,ReviewUpdate,ImportInput,ExportInput

ENGINES={};MODEL_CACHE={};CACHE_LOCK=threading.Lock()
REGISTERED={'demo':ROOT/'fixtures/layout.synthetic.json','kuaisearch-real-1pct':DATA/'subset.json'}

def fail(code,message,status=400):raise HTTPException(status,{'code':code,'message':message})
def engine(sid,owner):
    if sid not in ENGINES:fail('SOURCE_UNVERIFIED','快照尚未就绪',404)
    value=ENGINES[sid]
    if value.meta['data_mode']=='authorized_private':
        with connection() as db:
            if not db.execute('SELECT 1 FROM snapshot_owners WHERE snapshot_id=? AND owner=?',(sid,owner)).fetchone():fail('SOURCE_UNVERIFIED','快照不可访问',404)
    return value
def scope(sid,owner):
    with connection() as db:
        row=db.execute('SELECT s.* FROM scopes s JOIN scope_owners o USING(scope_id) WHERE s.scope_id=? AND o.owner=?',(sid,owner)).fetchone()
    if not row:fail('INCOMPATIBLE_SCOPE','分析范围不存在或不可访问',404)
    return dict(row),json.loads(row['filter_json'])
def scope_model(sid,owner):
    record,spec=scope(sid,owner);e=engine(record['snapshot_id'],owner)
    with CACHE_LOCK:cached=MODEL_CACHE.get(sid)
    if cached is None:
        cached=e.model(spec,sid)
        with CACHE_LOCK:
            if len(MODEL_CACHE)>128:MODEL_CACHE.pop(next(iter(MODEL_CACHE)))
            MODEL_CACHE[sid]=cached
    return cached
def create_scope(body,owner):
    e=engine(body.snapshot_id,owner);keys=sorted(set(body.exact_query_keys))
    if keys and not set(keys)<=e.valid_keys(keys):fail('INVALID_SCHEMA','查询ID不属于当前快照')
    splits=sorted(set(body.split_policy or e.meta['splits']))
    if not set(splits)<=set(e.meta['splits']):fail('INVALID_SCHEMA','内部split标记不属于当前快照')
    spec={'exact_query_keys':keys,'split_policy':splits}
    text=json.dumps(spec,sort_keys=True,separators=(',',':'))
    sid='scope-'+hashlib.sha256((body.snapshot_id+VERSION+text).encode()).hexdigest()[:24]
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO scopes VALUES (?,?,?,?,?)',(sid,body.snapshot_id,VERSION,text,now()))
        db.execute('INSERT OR IGNORE INTO scope_owners VALUES (?,?)',(sid,owner))
    return scope_model(sid,owner)

def cohort(cid,owner):
    with connection() as db:
        row=db.execute('SELECT c.* FROM cohorts c JOIN cohort_owners o USING(cohort_id) WHERE c.cohort_id=? AND o.owner=?',(cid,owner)).fetchone()
    if not row:fail('INCOMPATIBLE_SCOPE','查询组不存在或不可访问',404)
    return dict(row)
def comparison(aid,bid,owner):
    a=cohort(aid,owner);b=cohort(bid,owner)
    ar,asp=scope(a['scope_id'],owner);br,bsp=scope(b['scope_id'],owner)
    if ar['snapshot_id']!=br['snapshot_id'] or ar['metric_version']!=br['metric_version'] or asp['split_policy']!=bsp['split_policy']:
        fail('INCOMPATIBLE_SCOPE','两组必须来自同一快照、指标版本和split策略',409)
    am=scope_model(a['scope_id'],owner);bm=scope_model(b['scope_id'],owner);e=engine(ar['snapshot_id'],owner)
    aw,ap=e.where(asp);bw,bp=e.where(bsp)
    overlap=e.run('SELECT count(*) AS n FROM (SELECT r.request_id FROM requests r WHERE '+aw+' INTERSECT SELECT r.request_id FROM requests r WHERE '+bw+')',ap+bp)[0]['n']
    cats={c['id']:c for c in am['categories']+bm['categories']}
    ac={c['id']:c for c in am['categories']};bc={c['id']:c for c in bm['categories']}
    categories=[]
    for cid,c in cats.items():
        ea=ac.get(cid,{}).get('E',0);eb=bc.get(cid,{}).get('E',0)
        categories.append({**c,'a':rate(ea,am['E']),'b':rate(eb,bm['E']),'aE':ea,'bE':eb})
    delta=lambda metric:None if am['metrics'][metric] is None or bm['metrics'][metric] is None else 100*(bm['metrics'][metric]-am['metrics'][metric])
    return {'snapshot_id':ar['snapshot_id'],'scope_id':a['scope_id']+'|'+b['scope_id'],'metric_version':VERSION,'data_mode':am['data_mode'],
            'a':{'cohort':a,'model':am},'b':{'cohort':b,'model':bm},'categories':categories,
            'click_delta_pp':delta('pair_click_rate'),'purchase_delta_pp':delta('pair_purchase_feedback_rate'),
            'overlap_requests':overlap,'scale_spec':{'rate_max':1},'interpretation':'描述性差异，不代表随机实验或因果效果'}

@asynccontextmanager
async def lifespan(app):
    initialize()
    # Interrupted jobs never retain a success flag.
    with connection() as db:
        db.execute("UPDATE jobs SET state='failed',error_code='INTERRUPTED',finished_at=? WHERE state IN ('queued','running')",(now(),))
    # Verified full-Lite tables live on the read-only registered data mount.
    # State contains only a link, so cold start can restore registration without copying GBs.
    for path in (DATA/'full_lite').glob('*/metadata.json'):
        meta=verify_prepared_snapshot(path.parent)
        target=STATE/'analytics'/meta['snapshot_id'];target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_symlink():
            if target.resolve()!=path.parent.resolve():raise ValueError('Full-Lite link points to different data')
        elif target.exists():raise ValueError('Full-Lite target must not overwrite existing state')
        else:target.symlink_to(path.parent.resolve(),target_is_directory=True)
        register(meta,None)
    for path in (STATE/'analytics').glob('*/metadata.json') if (STATE/'analytics').exists() else []:
        if path.parent.name.startswith('staging-'):continue
        meta=json.loads(path.read_text(encoding='utf-8'));ENGINES[meta['snapshot_id']]=Analytics(meta)
    for key,path in REGISTERED.items():
        if path.is_file():
            meta=ingest(path,allow_real=key=='kuaisearch-real-1pct')
            ENGINES[meta['snapshot_id']]=Analytics(meta)
    yield

app=FastAPI(title='购序 · 搜索分析 API',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None)

@app.middleware('http')
async def session_boundary(request,call_next):
    if request.method in ('POST','PATCH','DELETE','PUT'):
        if request.headers.get('x-gouxu-request')!='1':
            return JSONResponse({'error':{'code':'INVALID_SCHEMA','message':'缺少同源操作标记'}},status_code=403)
        origin=request.headers.get('origin')
        if origin and urlsplit(origin).netloc!=request.headers.get('host'):
            return JSONResponse({'error':{'code':'INVALID_SCHEMA','message':'跨来源写操作被拒绝'}},status_code=403)
    owner=request.cookies.get('gouxu_session','')
    with connection() as db:
        found=re.fullmatch('[0-9a-f]{32}',owner) and db.execute('SELECT 1 FROM sessions WHERE id=?',(owner,)).fetchone()
        if not found:owner=uuid.uuid4().hex;db.execute('INSERT INTO sessions VALUES (?,?)',(owner,now()))
    request.state.owner=owner
    response=await call_next(request)
    if not found:response.set_cookie('gouxu_session',owner,httponly=True,samesite='strict',max_age=365*24*3600,secure=request.url.scheme=='https')
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(HTTPException)
async def http_error(request,exc):return JSONResponse({'error':exc.detail if isinstance(exc.detail,dict) else {'code':'INVALID_SCHEMA','message':str(exc.detail)}},status_code=exc.status_code)
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):return JSONResponse({'error':{'code':'INVALID_SCHEMA','message':'参数类型或范围不符合契约','fields':[{'location':e['loc'],'type':e['type']} for e in exc.errors()]}},status_code=422)

@app.get('/healthz')
def health():return {'status':'ok','snapshots':len(ENGINES),'version':'1.0.0'}

@app.get('/api/v1/snapshots')
def snapshots(request:Request):
    values=[]
    for sid in ENGINES:
        try:e=engine(sid,request.state.owner)
        except HTTPException:continue
        values.append({k:e.meta[k] for k in ('snapshot_id','data_mode','metric_version','title','counts','source','quality','splits')})
    values.sort(key=lambda x:(False,-float(x.get('source',{}).get('sampling',{}).get('percent',0))) if x['data_mode']=='public_real_subset' else (True,0))
    return {'snapshots':values}

@app.get('/api/v1/snapshots/{sid}/index')
def index(sid:str,request:Request):
    e=engine(sid,request.state.owner)
    return {**{k:e.meta[k] for k in ('snapshot_id','data_mode','metric_version','title','counts','source','quality','splits')},'queries':e.queries()}

@app.get('/api/v1/snapshots/{sid}/queries')
def find_queries(sid:str,request:Request,find:str=Query('',max_length=200),cursor:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    return {'queries':engine(sid,request.state.owner).queries(find,cursor,limit),'cursor':cursor}

@app.get('/api/v1/snapshots/{sid}/quality')
def quality(sid:str,request:Request):
    e=engine(sid,request.state.owner)
    return {'snapshot_id':sid,'quality':e.meta['quality'],'source':e.meta['source']}

@app.post('/api/v1/scopes')
def new_scope(body:ScopeInput,request:Request):return create_scope(body,request.state.owner)
@app.get('/api/v1/scopes/{sid}/metrics')
def get_metrics(sid:str,request:Request):return scope_model(sid,request.state.owner)
@app.get('/api/v1/scopes/{sid}/query-category')
def get_categories(sid:str,request:Request):return scope_model(sid,request.state.owner)
@app.get('/api/v1/scopes/{sid}/queries')
def scope_queries(sid:str,request:Request,cursor:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    record,spec=scope(sid,request.state.owner);e=engine(record['snapshot_id'],request.state.owner);where,params=e.where(spec)
    return {'queries':e.run('SELECT query_key AS key,max(query_display) AS query,count(*) AS requests FROM requests r WHERE '+where+' GROUP BY query_key ORDER BY requests DESC,key LIMIT ? OFFSET ?',params+[limit,cursor])}
@app.get('/api/v1/scopes/{sid}/items')
def scope_items(sid:str,request:Request,cursor:int=Query(0,ge=0),limit:int=Query(16,ge=1,le=200),min_pairs:int=Query(0,ge=0),category_id:str|None=None,selected_item_id:str|None=None,find:str=Query('',max_length=200)):
    record,spec=scope(sid,request.state.owner);e=engine(record['snapshot_id'],request.state.owner)
    result=e.item_rows(spec,limit,cursor,min_pairs,category_id,selected=selected_item_id,find=find)
    result.update(snapshot_id=record['snapshot_id'],scope_id=sid,metric_version=VERSION,data_mode=e.meta['data_mode'],denominator=scope_model(sid,request.state.owner)['E'])
    return result
@app.get('/api/v1/scopes/{sid}/items/{iid}')
def item_detail(sid:str,iid:str,request:Request):
    record,spec=scope(sid,request.state.owner);e=engine(record['snapshot_id'],request.state.owner)
    return {**e.item_rows(spec,item_id=iid)['items'][0],'snapshot_id':record['snapshot_id'],'scope_id':sid,'metric_version':VERSION,'data_mode':e.meta['data_mode']}
@app.get('/api/v1/scopes/{sid}/evidence')
def evidence(sid:str,request:Request,cursor:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=200),item_id:str|None=None,category_id:str|None=None):
    record,spec=scope(sid,request.state.owner);return engine(record['snapshot_id'],request.state.owner).evidence(spec,cursor,limit,item_id,category_id)

@app.post('/api/v1/cohorts')
def new_cohort(body:CohortInput,request:Request):
    scope(body.scope_id,request.state.owner);cid='cohort-'+uuid.uuid4().hex
    with connection() as db:
        db.execute('INSERT INTO cohorts VALUES (?,?,?,?)',(cid,body.scope_id,body.name,now()))
        db.execute('INSERT INTO cohort_owners VALUES (?,?)',(cid,request.state.owner))
    return cohort(cid,request.state.owner)
@app.get('/api/v1/cohorts')
def cohorts(request:Request):
    with connection() as db:rows=db.execute('SELECT c.* FROM cohorts c JOIN cohort_owners o USING(cohort_id) WHERE o.owner=? ORDER BY c.created_at DESC LIMIT 200',(request.state.owner,)).fetchall()
    return {'cohorts':[dict(x) for x in rows]}
@app.post('/api/v1/compare')
def compare(body:CompareInput,request:Request):return comparison(body.cohort_a,body.cohort_b,request.state.owner)

def review_rows(owner):
    with connection() as db:
        rows=db.execute('SELECT r.*,s.snapshot_id,s.metric_version FROM review_items r JOIN review_owners o ON o.review_id=r.id JOIN scopes s USING(scope_id) WHERE o.owner=? ORDER BY r.created_at DESC LIMIT 10000',(owner,)).fetchall()
    out=[]
    for row in rows:
        value=dict(row);stored=json.loads(value.pop('note'));value.update(name=stored['name'],note=stored['note']);out.append(value)
    return out
@app.post('/api/v1/review-items')
def add_review(body:ReviewInput,request:Request):
    record,spec=scope(body.scope_id,request.state.owner)
    if body.target_type=='item':engine(record['snapshot_id'],request.state.owner).item_rows(spec,item_id=body.target_id)
    if body.target_type=='compare':
        parts=body.target_id.split('|')
        if len(parts)!=2:fail('INVALID_SCHEMA','对照对象需要两个冻结查询组')
        comparison(parts[0],parts[1],request.state.owner)
    with connection() as db:
        prior=db.execute('SELECT r.id FROM review_items r JOIN review_owners o ON o.review_id=r.id WHERE o.owner=? AND r.scope_id=? AND r.target_type=? AND r.target_id=?',(request.state.owner,body.scope_id,body.target_type,body.target_id)).fetchone()
        if prior:return next(x for x in review_rows(request.state.owner) if x['id']==prior['id'])
        rid='review-'+uuid.uuid4().hex;t=now()
        db.execute('INSERT INTO review_items VALUES (?,?,?,?,?,?,?,?,?)',(rid,body.scope_id,body.target_type,body.target_id,json.dumps({'name':body.name,'note':body.note},ensure_ascii=False),'pending',1,t,t))
        db.execute('INSERT INTO review_owners VALUES (?,?)',(rid,request.state.owner))
    return next(x for x in review_rows(request.state.owner) if x['id']==rid)
@app.get('/api/v1/review-items')
def list_reviews(request:Request):return {'items':review_rows(request.state.owner)}
@app.patch('/api/v1/review-items/{rid}')
def update_review(rid:str,body:ReviewUpdate,request:Request):
    item=next((r for r in review_rows(request.state.owner) if r['id']==rid),None)
    if not item:fail('STALE_VERSION','复核对象不存在',404)
    with connection() as db:
        cur=db.execute('UPDATE review_items SET note=?,status=?,version=version+1,updated_at=? WHERE id=? AND version=?',(json.dumps({'name':item['name'],'note':body.note},ensure_ascii=False),body.status,now(),rid,body.expected_version))
        if cur.rowcount!=1:fail('STALE_VERSION','复核对象已被更新，请重新读取',409)
    return next(x for x in review_rows(request.state.owner) if x['id']==rid)
@app.delete('/api/v1/review-items/{rid}')
def delete_review(rid:str,request:Request,expected_version:int=Query(...,ge=1)):
    item=next((r for r in review_rows(request.state.owner) if r['id']==rid),None)
    if not item:fail('STALE_VERSION','复核对象不存在',404)
    with connection() as db:
        if db.execute('DELETE FROM review_items WHERE id=? AND version=?',(rid,expected_version)).rowcount!=1:fail('STALE_VERSION','复核版本已变化',409)
    return {'deleted':True}

def create_job(owner,kind,params):
    jid='job-'+uuid.uuid4().hex
    with connection() as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',(jid,kind,'queued',json.dumps(params,ensure_ascii=False),'{}',None,now(),None))
        db.execute('INSERT INTO job_owners VALUES (?,?)',(jid,owner))
    return jid
def job_record(jid,owner):
    with connection() as db:row=db.execute('SELECT j.* FROM jobs j JOIN job_owners o USING(job_id) WHERE j.job_id=? AND o.owner=?',(jid,owner)).fetchone()
    if not row:fail('INVALID_SCHEMA','任务不存在',404)
    value=dict(row);value['progress']=json.loads(value.pop('progress_json') or '{}');value.pop('parameters_json');return value
def run_import(jid,path,owner,allow_real):
    try:
        if job_cancelled(jid):return
        job_update(jid,'running')
        meta=ingest(path,owner=owner,job=jid,allow_real=allow_real)
        if job_cancelled(jid):return
        ENGINES[meta['snapshot_id']]=Analytics(meta);job_update(jid,'succeeded',{'snapshot_id':meta['snapshot_id'],'requests':meta['counts']['requests']})
    except ImportCancelled:job_update(jid,'cancelled')
    except Exception:job_update(jid,'failed',error='INVALID_SCHEMA')
@app.get('/api/v1/registered-files')
def registered_files(request:Request):
    return {'files':[{'id':k,'name':'合成演示样本' if k=='demo' else '已核验KuaiSearch-Lite子集'} for k,p in REGISTERED.items() if p.is_file()]}
@app.post('/api/v1/import-jobs')
def import_job(body:ImportInput,request:Request,background:BackgroundTasks):
    key=body.registered_file_ids[0]
    if key not in REGISTERED or not REGISTERED[key].is_file():fail('SOURCE_UNVERIFIED','只允许已注册文件')
    if key!='demo' and not body.consent_metadata.get('license_discrepancy_acknowledged'):fail('SOURCE_UNVERIFIED','需确认已阅读保留的许可差异')
    path=REGISTERED[key]
    owner=request.state.owner
    with connection() as db:
        for row in db.execute("SELECT j.* FROM jobs j JOIN job_owners o USING(job_id) WHERE o.owner=? AND j.kind='import' AND j.state IN ('queued','running')",(owner,)).fetchall():
            if json.loads(row['parameters_json']).get('registered_file_id')==key:return job_record(row['job_id'],owner)
    jid=create_job(owner,'import',{'registered_file_id':key,'adapter_id':body.adapter_id})
    background.add_task(run_import,jid,path,owner,key=='kuaisearch-real-1pct')
    return {'job_id':jid,'state':'queued'}
@app.post('/api/v1/import-upload')
async def upload_import(request:Request,background:BackgroundTasks,file:UploadFile=File(...)):
    owner=request.state.owner;jid=create_job(owner,'import',{'adapter_id':'normalized-v1','uploaded':True})
    directory=STATE/'uploads';directory.mkdir(parents=True,exist_ok=True);path=directory/(jid+'.json')
    size=0
    try:
        with path.open('wb') as output:
            while part:=await file.read(1024*1024):
                size+=len(part)
                if size>50*1024*1024:fail('EXPORT_TOO_LARGE','上传文件最大50MB',413)
                output.write(part)
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('mode')!='authorized_private':fail('SOURCE_UNVERIFIED','新日志需明确标识为authorized_private')
        if any(k in data for k in ('users','user_profiles')) or any(any(k in r for k in ('user_id','gender','age','location')) for r in data.get('requests',[])):
            fail('INVALID_SCHEMA','规范化导入不得包含用户画像或原始用户标识')
        background.add_task(run_import,jid,path,owner,False)
        return {'job_id':jid,'state':'queued'}
    except HTTPException:job_update(jid,'failed',error='INVALID_SCHEMA');raise
    except Exception:job_update(jid,'failed',error='INVALID_SCHEMA');fail('INVALID_SCHEMA','需要完整normalized-v1 JSON日志，订单文件不能用于曝光分析')
@app.get('/api/v1/import-jobs/{jid}')
def get_import(jid:str,request:Request):return job_record(jid,request.state.owner)
@app.post('/api/v1/import-jobs/{jid}/cancel')
def cancel_import(jid:str,request:Request):
    job=job_record(jid,request.state.owner)
    with connection() as db:
        db.execute("UPDATE jobs SET state='cancelled',finished_at=? WHERE job_id=? AND state IN ('queued','running')",(now(),jid))
    return job_record(jid,request.state.owner)

def csv_cell(value):
    if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value

def run_export(jid,body,owner):
    try:
        if job_cancelled(jid):return
        job_update(jid,'running');folder=STATE/'exports';folder.mkdir(parents=True,exist_ok=True)
        target=folder/(jid+'.'+body.format)
        if body.target=='compare':
            value=comparison(body.cohort_a,body.cohort_b,owner);value['source']=engine(value['snapshot_id'],owner).meta['source'];rows=value['categories'];provenance={k:value[k] for k in ('snapshot_id','scope_id','metric_version','data_mode')}
            provenance.update(unit='category_exposure_share',denominator_a=value['a']['model']['E'],denominator_b=value['b']['model']['E'],overlap_requests=value['overlap_requests'],click_delta_pp=value['click_delta_pp'],purchase_delta_pp=value['purchase_delta_pp'],source=json.dumps(value['source'],ensure_ascii=False))
        elif body.target=='review':
            rows=[{**r,'source':json.dumps(engine(r['snapshot_id'],owner).meta['source'],ensure_ascii=False)} for r in review_rows(owner)];value={'items':rows,'type':'review','metric_version':VERSION};provenance={'metric_version':VERSION,'scope':'each saved immutable scope'}
        elif body.target=='evidence':
            record,spec=scope(body.scope_id,owner);e=engine(record['snapshot_id'],owner);rows=[];cursor=0
            while True:
                if job_cancelled(jid):return
                page=e.evidence(spec,cursor,200,body.item_id,body.category_id)
                if page['total']>20000:raise ValueError('export too large')
                rows.extend(page['records']);job_update(jid,'running',{'rows':len(rows)})
                if page['next_cursor'] is None:break
                cursor=page['next_cursor']
            provenance={'snapshot_id':record['snapshot_id'],'scope_id':body.scope_id,'metric_version':VERSION,'data_mode':e.meta['data_mode'],'unit':'request_row','source':json.dumps(e.meta['source'],ensure_ascii=False)}
            value={**provenance,'source':e.meta['source'],'focus':{'item_id':body.item_id,'category_id':body.category_id},'records':rows,'note':page['note']}
            if body.format=='csv':rows=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows]
        else:
            record,spec=scope(body.scope_id,owner);e=engine(record['snapshot_id'],owner);model=scope_model(body.scope_id,owner)
            budget=e.item_rows(spec,limit=1)
            if budget['eligible']>200000:raise ValueError('export too large')
            all_items=e.item_rows(spec,limit=200000)
            rows=all_items['items'];provenance={k:model[k] for k in ('snapshot_id','scope_id','metric_version','data_mode')}
            provenance.update(unit='request_item_pair',scope_exposed_pairs=model['E'],source=json.dumps(e.meta['source'],ensure_ascii=False),split_policy=json.dumps(spec['split_policy']),exact_query_keys=json.dumps(spec['exact_query_keys']))
            value={**model,'items':rows,'source':e.meta['source'],'export_unit':'request_item_pair','display_controls_do_not_filter_export':True}
        if body.format=='json':
            target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        else:
            columns=sorted({k for row in rows for k in row if not isinstance(row[k],(dict,list))})
            with target.open('w',newline='',encoding='utf-8-sig') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(dict.fromkeys(list(provenance)+columns)))
                writer.writeheader()
                for n,row in enumerate(rows):
                    if n%1000==0:
                        if job_cancelled(jid):target.unlink(missing_ok=True);return
                        job_update(jid,'running',{'rows':n})
                    writer.writerow({k:csv_cell(v) for k,v in {**provenance,**{k:row.get(k) for k in columns}}.items()})
        if job_cancelled(jid):target.unlink(missing_ok=True);return
        job_update(jid,'succeeded',{'rows':len(rows),'filename':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'download_url':'/api/v1/exports/'+jid+'/file'})
    except Exception:job_update(jid,'failed',error='EXPORT_TOO_LARGE')
@app.post('/api/v1/exports')
def export_job(body:ExportInput,request:Request,background:BackgroundTasks):
    if body.target in ('scope','evidence'):
        if not body.scope_id:fail('INVALID_SCHEMA','导出需要冻结范围')
        scope(body.scope_id,request.state.owner)
    elif body.target=='compare':
        if not body.cohort_a or not body.cohort_b:fail('INVALID_SCHEMA','对照导出需要两个冻结查询组')
        comparison(body.cohort_a,body.cohort_b,request.state.owner)
    jid=create_job(request.state.owner,'export',body.model_dump())
    background.add_task(run_export,jid,body,request.state.owner);return {'job_id':jid,'state':'queued'}
@app.get('/api/v1/exports/{jid}')
def get_export(jid:str,request:Request):return job_record(jid,request.state.owner)
@app.get('/api/v1/exports/{jid}/file')
def export_file(jid:str,request:Request):
    record=job_record(jid,request.state.owner)
    if record['state']!='succeeded':fail('INVALID_SCHEMA','导出尚未完成',409)
    filename=record['progress']['filename']
    if not re.fullmatch(r'job-[0-9a-f]{32}\.(?:json|csv)',filename):fail('INVALID_SCHEMA','无效导出文件')
    return FileResponse(STATE/'exports'/filename,filename='gouxu-'+filename,media_type='application/json' if filename.endswith('.json') else 'text/csv')

