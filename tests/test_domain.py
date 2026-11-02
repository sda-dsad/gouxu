import unittest,json,sys,sqlite3,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from domain import metrics,id_set,id_string,category_flows,co_click,by_item,validate_request
from prepare_subset import chosen
from audit_jsonl import audit

class DomainTests(unittest.TestCase):
 def setUp(self): self.g=json.loads((R/'fixtures/golden.synthetic.json').read_text())
 def test_hand_calculated_counts(self):
  m=metrics(self.g['requests'])
  for k,v in self.g['expected'].items():self.assertAlmostEqual(m[k],v,msg=k)
 def test_empty_denominator(self):
  m=metrics([]);self.assertIsNone(m['pair_click_rate']);self.assertIsNone(m['request_click_rate'])
 def test_no_exposure_request_retained(self):
  m=metrics([{'query':'a','impressed_item_ids':[],'clicked_item_ids':[],'purchased_item_ids':[]}]);self.assertEqual(m['requests'],1);self.assertIsNone(m['pair_click_rate']);self.assertEqual(m['request_click_rate'],0)
 def test_purchase_not_subset_click(self):
  m=metrics(self.g['requests']);self.assertEqual(m['purchased_pairs'],2);self.assertEqual(m['triple_pairs'],1)
 def test_orphans_are_not_inserted_in_exposure(self):
  m=metrics(self.g['requests']);self.assertEqual(m['exposed_pairs'],4);self.assertEqual(m['orphan_click_pairs'],1);self.assertEqual(m['orphan_purchase_pairs'],1)
 def test_duplicate_list_reduced_only_for_metrics(self):
  r=self.g['requests'];metrics(r);self.assertEqual(r[0]['impressed_item_ids'],['a','a','b'])
 def test_no_float_identifier(self):
  with self.assertRaises(ValueError):id_string(123.0)
 def test_no_bool_identifier(self):
  with self.assertRaises(ValueError):id_string(True)
 def test_id_leading_zero_kept(self): self.assertEqual(id_string('001'),'001')
 def test_supported_struct_ids(self):self.assertEqual(id_set([{'item_id':3},{'item_id':'4'}]),{'3','4'})
 def test_null_list_rejected(self):
  with self.assertRaises(ValueError):id_set(None)
 def test_unknown_struct_rejected(self):
  with self.assertRaises(ValueError):id_set([{'id':3}])
 def test_missing_query_rejected(self):
  with self.assertRaises(ValueError):validate_request({'impressed_item_ids':[],'clicked_item_ids':[],'purchased_item_ids':[]})
 def test_flow_conservation(self):
  f=category_flows(self.g['requests'],[{'item_id':'a','category_level1_id':'A'}]);self.assertEqual(f['total'],4);self.assertEqual(f['unknown_pairs'],2);self.assertEqual(f['metadata_coverage'],.5)
 def test_empty_flow_coverage_null(self):self.assertIsNone(category_flows([],[])['metadata_coverage'])
 def test_item_totals_equal_aggregate(self):
  v=list(by_item(self.g['requests']).values());self.assertEqual(sum(x['exposed'] for x in v),4);self.assertEqual(sum(x['clicked'] for x in v),3)
 def test_coclick(self):
  m=co_click(self.g['requests'],'a','c');self.assertEqual(m['both_requests'],1);self.assertEqual(m['jaccard'],.5)
 def test_coclick_empty(self):self.assertIsNone(co_click([],'a','c')['jaccard'])
 def test_user_hash_deterministic(self):self.assertEqual([chosen(str(x),'s',1) for x in range(300)],[chosen(str(x),'s',1) for x in range(300)])
 def test_user_hash_same_user_all_requests(self):self.assertEqual(len(set(chosen('some-user','s',20) for _ in range(10))),1)
 def test_audit_prefix_not_full(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.jsonl';p.write_text('\n'.join(json.dumps({'user_id':1,'session_id':n,**r}) for n,r in enumerate(self.g['requests'])))
   r=audit(p,'recall',1);self.assertFalse(r['full_scan']);self.assertEqual(r['counts']['lines'],1)
 def test_audit_full(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.jsonl';p.write_text('\n'.join(json.dumps({'user_id':1,'session_id':n,**r}) for n,r in enumerate(self.g['requests'])))
   r=audit(p,'recall');self.assertTrue(r['full_scan']);self.assertEqual(r['counts']['valid_rows'],3)
 def test_audit_invalid_not_swallowed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.jsonl';p.write_text('{"query":"a"}\nnot json\n');r=audit(p,'recall');self.assertEqual(r['counts']['invalid_rows'],2)

class ContractTests(unittest.TestCase):
 def test_layout_schema(self):
  import jsonschema
  jsonschema.validate(json.loads((R/'fixtures/layout.synthetic.json').read_text()),json.loads((R/'contracts/normalized.schema.json').read_text()))
 def test_metric_schema(self):
  import jsonschema
  jsonschema.validate(json.loads((R/'fixtures/metrics.synthetic.expected.json').read_text()),json.loads((R/'contracts/metrics.schema.json').read_text()))
 def test_source_lock_only_two_files(self):
  s=json.loads((R/'contracts/source.lock.json').read_text());self.assertEqual(len(s['files']),2);self.assertEqual(len(s['revision']),40);self.assertTrue(all(len(f['sha256'])==64 for f in s['files']))
 def test_fixture_synthetic(self):self.assertEqual(json.loads((R/'fixtures/layout.synthetic.json').read_text())['mode'],'synthetic')
 def test_known_layout_counts_independent(self):
  d=json.loads((R/'fixtures/layout.synthetic.json').read_text());self.assertEqual(len(d['requests']),336);self.assertEqual(len(d['items']),28)
  self.assertEqual(sum(len(set(x['impressed_item_ids'])) for x in d['requests']),1722)
 def test_sqlite_schema(self):
  db=sqlite3.connect(':memory:');db.executescript((R/'contracts/state.sqlite.sql').read_text());self.assertGreaterEqual(len(db.execute("select name from sqlite_master where type='table'").fetchall()),5)
 def test_sqlite_scope_immutable(self):
  db=sqlite3.connect(':memory:');db.executescript((R/'contracts/state.sqlite.sql').read_text());db.execute("insert into snapshots values ('s','synthetic',NULL,'{}','test','today')");db.execute("insert into scopes values('q','s','v','{}','today')")
  with self.assertRaises(sqlite3.IntegrityError):db.execute("update scopes set filter_json='changed' where scope_id='q'")
 def test_no_font_files_in_package(self):self.assertEqual([p for p in R.rglob('*') if p.suffix.lower() in ('.ttf','.otf','.woff','.woff2','.ttc')],[])
if __name__=='__main__':unittest.main()
