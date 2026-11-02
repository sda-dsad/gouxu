import os,sys,json,tempfile,unittest,sqlite3,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
TEMP_ROOT=ROOT/'.cache/api-tests';TEMP_ROOT.mkdir(parents=True,exist_ok=True)
CASE_STATE=TEMP_ROOT/('state-'+str(os.getpid()));CASE_STATE.mkdir(exist_ok=True)
assert TEMP_ROOT.resolve() in CASE_STATE.resolve().parents
os.environ['GOUXU_STATE_ROOT']=str(CASE_STATE)
sys.path.insert(0,str(ROOT/'services/api'))
from fastapi.testclient import TestClient
from app.main import app,csv_cell,create_job
from app.state import connection,job_update
from app.analytics import ingest,ImportCancelled
H={'x-gouxu-request':'1'}

class APIContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.ctx=TestClient(app);cls.client=cls.ctx.__enter__()
  cls.snapshot=next(s for s in cls.client.get('/api/v1/snapshots').json()['snapshots'] if s['data_mode']=='synthetic')
  cls.sid=cls.snapshot['snapshot_id']
  cls.model=cls.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':cls.sid}).json()
 @classmethod
 def tearDownClass(cls):cls.ctx.__exit__(None,None,None)
 def new_cohort(self,scope_id=None):
  r=self.client.post('/api/v1/cohorts',headers=H,json={'scope_id':scope_id or self.model['scope_id'],'name':'test cohort'});self.assertEqual(r.status_code,200);return r.json()['cohort_id']
 def test_golden_layout_counts(self):
  self.assertEqual((self.model['requests'],self.model['E'],self.model['C'],self.model['P'],self.model['purchaseWithoutClick']),(336,1722,533,118,4))
 def test_envelope_provenance(self):
  self.assertEqual(self.model['data_mode'],'synthetic');self.assertEqual(self.model['unit'],'request_item_pair');self.assertEqual(self.model['denominator'],1722)
 def test_categories_conserve(self):self.assertEqual(sum(c['E'] for c in self.model['categories']),1722)
 def test_parameter_validation(self):self.assertEqual(self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/items?limit=201').status_code,422)
 def test_unknown_query_key_rejected(self):
  r=self.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':self.sid,'exact_query_keys':['not-a-query']});self.assertEqual(r.status_code,400)
 def test_display_threshold_preserves_scope(self):
  r=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/items?min_pairs=180&limit=16').json()
  self.assertEqual(r['items'],[]);self.assertEqual(r['denominator'],1722)
 def test_item_totals(self):
  r=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/items?limit=200').json()
  self.assertEqual(sum(p['E'] for p in r['items']),1722);self.assertEqual(sum(p['C'] for p in r['items']),533)
 def test_selected_pin_obeys_budget(self):
  base=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/items?limit=200').json()['items']
  selected=base[-1]['id'];r=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/items?limit=3&selected_item_id='+selected).json()
  self.assertEqual(len(r['items']),3);self.assertIn(selected,[p['id'] for p in r['items']])
 def test_evidence_redaction_and_source_refs(self):
  r=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/evidence?limit=2').json()
  self.assertEqual(len(r['records']),2)
  self.assertTrue(all('user_id' not in x and len(x['source_sha256'])==64 for x in r['records']))
 def test_identical_groups_exact_zero(self):
  cid=self.new_cohort();r=self.client.post('/api/v1/compare',headers=H,json={'cohort_a':cid,'cohort_b':cid}).json()
  self.assertEqual((r['click_delta_pp'],r['purchase_delta_pp'],r['overlap_requests']),(0,0,336))
  self.assertTrue(all(c['a']==c['b'] for c in r['categories']))
 def test_scope_immutable(self):
  with connection() as db:
   with self.assertRaises(sqlite3.IntegrityError):db.execute('UPDATE scopes SET filter_json=? WHERE scope_id=?',('{}',self.model['scope_id']))
 def test_review_version_and_owner_isolation(self):
  body={'scope_id':self.model['scope_id'],'target_type':'item','target_id':'DEMO-01-01','name':'test item','note':'=HYPERLINK("bad")'}
  r=self.client.post('/api/v1/review-items',headers=H,json=body).json()
  update={'expected_version':r['version'],'note':'复核后的备注','status':'reviewed'}
  changed=self.client.patch('/api/v1/review-items/'+r['id'],headers=H,json=update);self.assertEqual(changed.status_code,200)
  self.assertEqual(self.client.patch('/api/v1/review-items/'+r['id'],headers=H,json=update).status_code,409)
  with TestClient(app) as other:self.assertEqual(other.get('/api/v1/review-items').json()['items'],[])
  stored=self.client.get('/api/v1/review-items').json()['items'];self.assertTrue(any(x['id']==r['id'] and x['status']=='reviewed' for x in stored))
  self.assertEqual(self.client.delete('/api/v1/review-items/'+r['id']+'?expected_version='+str(r['version']+1),headers=H).status_code,200)
 def test_csrf_rejected(self):
  self.assertEqual(self.client.post('/api/v1/scopes',json={'snapshot_id':self.sid}).status_code,403)
  self.assertEqual(self.client.post('/api/v1/scopes',headers={**H,'origin':'https://evil.example'},json={'snapshot_id':self.sid}).status_code,403)
 def test_repeat_registered_import_idempotent(self):
  first=self.client.post('/api/v1/import-jobs',headers=H,json={'registered_file_ids':['demo']}).json()
  result=self.client.get('/api/v1/import-jobs/'+first['job_id']).json();self.assertEqual(result['state'],'succeeded')
  self.client.post('/api/v1/import-jobs',headers=H,json={'registered_file_ids':['demo']})
  self.assertEqual(len([s for s in self.client.get('/api/v1/snapshots').json()['snapshots'] if s['snapshot_id']==self.sid]),1)
 def test_registered_paths_only(self):self.assertEqual(self.client.post('/api/v1/import-jobs',headers=H,json={'registered_file_ids':['../../etc/passwd']}).status_code,400)
 def test_private_sampling_metadata_is_not_sort_configuration(self):
  data=json.loads((ROOT/'fixtures/layout.synthetic.json').read_text(encoding='utf-8'));data['mode']='authorized_private';data['snapshot_id']='private-freeform-source-'+str(os.getpid())
  data['source']={'nature':'synthetic import test','sampling':{'percent':'free-form metadata'}}
  job=self.client.post('/api/v1/import-upload',headers=H,files={'file':('freeform.json',json.dumps(data),'application/json')}).json()
  self.assertEqual(self.client.get('/api/v1/import-jobs/'+job['job_id']).json()['state'],'succeeded')
  response=self.client.get('/api/v1/snapshots');self.assertEqual(response.status_code,200)
  found=next(s for s in response.json()['snapshots'] if s['snapshot_id']==data['snapshot_id'])
  self.assertEqual(found['source']['sampling']['percent'],'free-form metadata')
 def test_streamed_full_lite_fast_queries_match_original_joins(self):
  import importlib.util,hashlib,shutil
  from app.analytics import Analytics,register,query_key
  from app.main import ENGINES
  spec=importlib.util.spec_from_file_location('full_lite_builder_test',ROOT/'tools/build_full_lite.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
  base=CASE_STATE/'streamed-source';base.mkdir();revision='synthetic-test-'+str(os.getpid())
  raw=base/'raw'/revision;(raw/'recall_lite').mkdir(parents=True);(raw/'items_lite').mkdir()
  def row(user,session,time,q,i,c,p,split='train'):return {'user_id':user,'session_id':session,'time_index':time,'query':q,'split':split,'impressed_item_ids':i,'clicked_item_ids':c,'purchased_item_ids':p}
  requests=[row('u1','s1',0,'q',['a','a','b'],['a','x'],['b','y']),row('u1','s1',1,'q',['a','c'],['a','c'],['a']),row('u2','s2',2,'empty',[],[],[],'valid')]
  items=[{'item_id':iid,'item_title':'test '+iid,'category_level1_id':'cat','category_level1_name':'测试'} for iid in ['a','b','c','unused']]
  files=[]
  for name,rows in [('recall_lite/train.jsonl',requests),('items_lite/train.jsonl',items)]:
   p=raw/name;p.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8');files.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  lock=base/'lock.json';lock.write_text(json.dumps({'repo_id':'synthetic-test-only','revision':revision,'files':files,'license_verification':'Self-created synthetic fixture'}),encoding='utf-8')
  meta=builder.build(base/'raw',lock,CASE_STATE/'analytics',base/'reports',memory='64MB',synthetic_test=True)
  register(meta,None);fast=Analytics(meta);ENGINES[meta['snapshot_id']]=fast
  plain_folder=base/'plain';plain_folder.mkdir()
  for name in ['requests','pairs','items']:shutil.copyfile(fast.folder/(name+'.parquet'),plain_folder/(name+'.parquet'))
  plain=Analytics({**meta,'global_model':None});plain.folder=plain_folder
  for params in [{'exact_query_keys':[],'split_policy':['train','valid']},{'exact_query_keys':[query_key('q')],'split_policy':['train']},{'exact_query_keys':[query_key('empty')],'split_policy':['valid']},{'exact_query_keys':[],'split_policy':['valid']}]:
   self.assertEqual(fast.model(params,'same-scope'),plain.model(params,'same-scope'))
   self.assertEqual(fast.item_rows(params,limit=2,selected='c'),plain.item_rows(params,limit=2,selected='c'))
   self.assertEqual(fast.item_rows(params,find='test'),plain.item_rows(params,find='test'))
   self.assertEqual(fast.evidence(params),plain.evidence(params))
   self.assertEqual(fast.evidence(params,item_id='a'),plain.evidence(params,item_id='a'))
   self.assertEqual(fast.evidence(params,category_id='cat'),plain.evidence(params,category_id='cat'))
  self.assertEqual(fast.queries(),plain.queries())
  m=self.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':meta['snapshot_id']}).json()
  self.assertEqual((m['requests'],m['E'],m['C'],m['P']),(3,4,3,2))
  empty=self.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':meta['snapshot_id'],'exact_query_keys':[query_key('empty')]}).json()
  self.assertEqual((empty['requests'],empty['E'],empty['metrics']['pair_click_rate']),(1,0,None))
  job=self.client.post('/api/v1/exports',headers=H,json={'scope_id':m['scope_id'],'format':'json','target':'scope'}).json()
  result=self.client.get('/api/v1/exports/'+job['job_id']).json();self.assertEqual(result['state'],'succeeded')
  exported=self.client.get(result['progress']['download_url']).json()
  self.assertEqual(sum(p['E'] for p in exported['items']),4)
 def test_cancelled_import_does_not_publish(self):
  with connection() as db:owner=db.execute('SELECT id FROM sessions LIMIT 1').fetchone()['id']
  jid=create_job(owner,'import',{});job_update(jid,'cancelled')
  with self.assertRaises(ImportCancelled):ingest(ROOT/'fixtures/layout.synthetic.json',owner,jid)
  with connection() as db:self.assertEqual(db.execute('SELECT state FROM jobs WHERE job_id=?',(jid,)).fetchone()['state'],'cancelled')
 def test_order_only_file_rejected(self):
  content=json.dumps({'orders':[{'amount':1}]})
  r=self.client.post('/api/v1/import-upload',headers=H,files={'file':('orders.json',content,'application/json')})
  self.assertEqual(r.status_code,400);self.assertEqual(r.json()['error']['code'],'SOURCE_UNVERIFIED')
 def test_inflight_progress_cannot_reopen_cancelled_job(self):
  with connection() as db:owner=db.execute('SELECT id FROM sessions LIMIT 1').fetchone()['id']
  jid=create_job(owner,'import',{});job_update(jid,'running',{'requests':200});job_update(jid,'cancelled')
  with connection() as db:finished=db.execute('SELECT finished_at FROM jobs WHERE job_id=?',(jid,)).fetchone()['finished_at']
  job_update(jid,'running',{'requests':400});job_update(jid,'failed',error='late error');job_update(jid,'succeeded',{'requests':50000})
  with connection() as db:row=db.execute('SELECT state,finished_at FROM jobs WHERE job_id=?',(jid,)).fetchone()
  self.assertEqual(row['state'],'cancelled');self.assertEqual(row['finished_at'],finished)
 def test_completed_job_cannot_be_overwritten_by_late_error(self):
  with connection() as db:owner=db.execute('SELECT id FROM sessions LIMIT 1').fetchone()['id']
  jid=create_job(owner,'export',{});job_update(jid,'succeeded',{'rows':10});job_update(jid,'failed',error='late error')
  with connection() as db:row=db.execute('SELECT state,progress_json FROM jobs WHERE job_id=?',(jid,)).fetchone()
  self.assertEqual(row['state'],'succeeded');self.assertEqual(json.loads(row['progress_json'])['rows'],10)
 def test_golden_original_lists_request_rates_and_empty_evidence(self):
  data=json.loads((ROOT/'fixtures/layout.synthetic.json').read_text(encoding='utf-8'));data['mode']='authorized_private';data['snapshot_id']='golden-payload-'+str(os.getpid());data['source']={'nature':'hand calculated synthetic contract fixture'}
  def row(rid,q,i,c,p):return {'request_id':rid,'query':q,'impressed_item_ids':i,'clicked_item_ids':c,'purchased_item_ids':p}
  data['requests']=[row('r1','q',['a','b'],['a','x'],['b','y']),row('r2','q',['a','c'],['a','c'],['a']),row('r3','empty',[],[],[])]
  data['requests'][0]['source_feedback_lists']={'impressed_item_ids':['a','a','b'],'clicked_item_ids':['a','x'],'purchased_item_ids':['b','y']}
  data['items']=[{**x,'item_id':iid} for x,iid in zip(data['items'][:3],['a','b','c'])]
  job=self.client.post('/api/v1/import-upload',headers=H,files={'file':('golden.json',json.dumps(data),'application/json')}).json()
  self.assertEqual(self.client.get('/api/v1/import-jobs/'+job['job_id']).json()['state'],'succeeded')
  m=self.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':data['snapshot_id']}).json()
  self.assertEqual((m['E'],m['C'],m['P']),(4,3,2));self.assertEqual(m['metrics']['duplicate_list_entries'],1)
  self.assertEqual(m['metrics']['request_click_rate'],2/3);self.assertEqual(m['metrics']['request_purchase_feedback_rate'],2/3)
  evidence=self.client.get('/api/v1/scopes/'+m['scope_id']+'/evidence').json();self.assertEqual(evidence['total'],3)
  first=next(r for r in evidence['records'] if r['request_id']=='r1');self.assertEqual(first['impressed_item_ids'],['a','a','b']);self.assertEqual(first['original_feedback_lists']['clicked_item_ids'],['a','x'])
  index=self.client.get('/api/v1/snapshots/'+data['snapshot_id']+'/index').json();key=next(q['key'] for q in index['queries'] if q['query']=='empty')
  empty=self.client.post('/api/v1/scopes',headers=H,json={'snapshot_id':data['snapshot_id'],'exact_query_keys':[key]}).json()
  self.assertIsNone(empty['metrics']['pair_click_rate']);self.assertIn('zero_denominator',empty['warnings']);self.assertEqual(empty['coverage']['exposed_items'],0)
  data['requests'][0]['impressed_item_ids']=['a','a','b']
  invalid=self.client.post('/api/v1/import-upload',headers=H,files={'file':('invalid-duplicates.json',json.dumps(data),'application/json')}).json()
  self.assertEqual(self.client.get('/api/v1/import-jobs/'+invalid['job_id']).json()['state'],'failed')
 def test_authorized_normalized_upload(self):
  data=json.loads((ROOT/'fixtures/layout.synthetic.json').read_text(encoding='utf-8'));data['mode']='authorized_private';data['snapshot_id']='private-test-'+str(os.getpid())
  data['source']={'nature':'synthetic fixture used only to test authorized upload contract'}
  r=self.client.post('/api/v1/import-upload',headers=H,files={'file':('authorized.json',json.dumps(data),'application/json')}).json()
  self.assertEqual(self.client.get('/api/v1/import-jobs/'+r['job_id']).json()['state'],'succeeded')
  with TestClient(app) as other:self.assertNotIn(data['snapshot_id'],[s['snapshot_id'] for s in other.get('/api/v1/snapshots').json()['snapshots']])
 def test_item_search_preserves_denominator_and_paginates(self):
  base='/api/v1/scopes/'+self.model['scope_id']+'/items'
  first=self.client.get(base+'?limit=2').json();second=self.client.get(base+'?limit=2&cursor=2').json()
  self.assertTrue(set(x['id'] for x in first['items']).isdisjoint(x['id'] for x in second['items']))
  filtered=self.client.get(base,params={'find':'帆布','limit':200}).json()
  self.assertTrue(filtered['items']);self.assertTrue(all('帆布' in p['title'] for p in filtered['items']))
  self.assertEqual(filtered['denominator'],1722)
 def test_evidence_export_contains_full_rows_and_hash(self):
  evidence=self.client.get('/api/v1/scopes/'+self.model['scope_id']+'/evidence?limit=200&category_id=C01').json()
  jid=self.client.post('/api/v1/exports',headers=H,json={'target':'evidence','scope_id':self.model['scope_id'],'category_id':'C01'}).json()['job_id']
  job=self.client.get('/api/v1/exports/'+jid).json();self.assertEqual(job['state'],'succeeded')
  data=self.client.get(job['progress']['download_url']).json()
  self.assertEqual(len(data['records']),evidence['total']);self.assertEqual(data['unit'],'request_row')
  self.assertTrue(all(len(r['source_sha256'])==64 and 'user_id' not in r for r in data['records']))
 def test_export_csv_formula_protection(self):
  for v in ['=1+2',' +SUM(1)','@eval','-cmd']:self.assertTrue(csv_cell(v).startswith("'"))
  self.assertEqual(csv_cell(-5),-5)
 def test_export_job_download(self):
  r=self.client.post('/api/v1/exports',headers=H,json={'scope_id':self.model['scope_id'],'format':'json'}).json()
  result=self.client.get('/api/v1/exports/'+r['job_id']).json();self.assertEqual(result['state'],'succeeded')
  file=self.client.get(result['progress']['download_url']);self.assertEqual(file.status_code,200)
  data=file.json();self.assertEqual(data['E'],1722);self.assertEqual(sum(i['E'] for i in data['items']),1722)
  self.assertEqual(data['metric_version'],'request-item-pair-v1')
if __name__=='__main__':unittest.main()

