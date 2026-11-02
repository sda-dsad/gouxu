import json
import unittest
import test_api as fixture
from fastapi.testclient import TestClient
from app.main import app,ENGINES


class DynamicCategoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=TestClient(app);cls.client=cls.ctx.__enter__()
        data=json.loads((fixture.ROOT/'fixtures/layout.synthetic.json').read_text(encoding='utf-8'))
        data['mode']='authorized_private';data['snapshot_id']='dynamic-category-synthetic-contract'
        data['source']={'nature':'self-created synthetic category ranking contract test'}
        data['items']=[{'item_id':'i'+str(i),'item_title':'测试商品'+str(i),'category_level1_id':'K'+str(i).zfill(2),'category_level1_name':'测试真实类目'+str(i)} for i in range(9)]
        rows=[]
        def add(query,ids,count):
            for _ in range(count):
                rows.append({'request_id':'r'+str(len(rows)),'query':query,'impressed_item_ids':ids,'clicked_item_ids':ids[:1],'purchased_item_ids':ids[-1:] if len(ids)>1 else [],'split':'train'})
        add('请求较多曝光较少',['i0'],20)
        add('曝光最多',[f'i{i}' for i in range(8)],6)
        add('多类目曝光',[f'i{i}' for i in range(9)],4)
        add('演示单类目',['i8'],1)
        data['requests']=rows
        job=cls.client.post('/api/v1/import-upload',headers=fixture.H,files={'file':('synthetic.json',json.dumps(data),'application/json')}).json()
        assert cls.client.get('/api/v1/import-jobs/'+job['job_id']).json()['state']=='succeeded'
        cls.sid=data['snapshot_id']
        cls.index=cls.client.get('/api/v1/snapshots/'+cls.sid+'/index').json()
        cls.global_model=cls.client.post('/api/v1/scopes',headers=fixture.H,json={'snapshot_id':cls.sid}).json()
        key=next(q['key'] for q in cls.index['queries'] if q['query']=='演示单类目')
        cls.tail=cls.client.post('/api/v1/scopes',headers=fixture.H,json={'snapshot_id':cls.sid,'exact_query_keys':[key]}).json()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None,None,None)

    def test_low_global_category_is_named_in_its_own_query(self):
        self.assertNotIn('K08',ENGINES[self.sid].meta['keep'])
        self.assertEqual([(c['id'],c['name'],c['E']) for c in self.tail['categories']],[('K08','测试真实类目8',1)])
        self.assertEqual(self.tail['other_categories'],[])

    def test_all_categories_sorted_and_all_metrics_conserved(self):
        rows=self.global_model['categories']
        self.assertEqual(len(rows),9)
        self.assertEqual([c['E'] for c in rows],sorted([c['E'] for c in rows],reverse=True))
        self.assertTrue(all(c['E']>0 and c['id']!='OTHER' for c in rows))
        for key in ('E','C','P'):
            self.assertEqual(sum(c[key] for c in rows),self.global_model[key])
        self.assertEqual(self.global_model['E'],105)

    def test_query_ranking_uses_exposure_instead_of_request_count(self):
        rows=self.index['queries']
        self.assertEqual([r['E'] for r in rows],[48,36,20,1])
        self.assertEqual(rows[0]['requests'],6)
        self.assertEqual(rows[2]['requests'],20)
        first=self.client.get('/api/v1/snapshots/'+self.sid+'/queries?limit=2').json()['queries']
        second=self.client.get('/api/v1/snapshots/'+self.sid+'/queries?limit=2&cursor=2').json()['queries']
        self.assertEqual(first+second,rows)

    def test_product_color_identity_and_evidence_use_real_category(self):
        base='/api/v1/scopes/'+self.tail['scope_id']
        product=self.client.get(base+'/items?category_id=K08').json()['items'][0]
        category=self.tail['categories'][0]
        self.assertEqual((product['categoryId'],product['displayCategoryId'],product['categoryName']),('K08','K08','测试真实类目8'))
        self.assertEqual(product['color'],category['color'])
        evidence=self.client.get(base+'/evidence?category_id=K08').json()
        self.assertEqual(evidence['total'],1)
        self.assertEqual(evidence['records'][0]['impressed_item_ids'],['i8'])

    def test_comparison_and_export_retain_named_categories(self):
        def cohort(model):
            return self.client.post('/api/v1/cohorts',headers=fixture.H,json={'scope_id':model['scope_id'],'name':'synthetic'}).json()['cohort_id']
        result=self.client.post('/api/v1/compare',headers=fixture.H,json={'cohort_a':cohort(self.tail),'cohort_b':cohort(self.global_model)}).json()
        self.assertTrue(any(c['id']=='K08' and c['aE']==1 for c in result['categories']))
        self.assertTrue(all(c['id']!='OTHER' for c in result['categories']))
        job=self.client.post('/api/v1/exports',headers=fixture.H,json={'scope_id':self.tail['scope_id'],'format':'json'}).json()
        state=self.client.get('/api/v1/exports/'+job['job_id']).json()
        self.assertEqual(state['state'],'succeeded')
        exported=self.client.get(state['progress']['download_url']).json()
        self.assertEqual(exported['categories'][0]['id'],'K08')
        self.assertEqual(exported['items'][0]['displayCategoryId'],'K08')
