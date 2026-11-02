"""Tiny, independently counted synthetic sources for the streamed full-Lite path."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/api'))
spec=importlib.util.spec_from_file_location('full_lite_builder',ROOT/'tools/build_full_lite.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class FullLiteBuilderTests(unittest.TestCase):
    def test_streamed_sources_match_independent_counts_and_preserve_original_lists(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache/temp') as tmp:
            folder=Path(tmp);revision='synthetic-full-lite-test'
            raw=folder/'raw'/revision; (raw/'recall_lite').mkdir(parents=True);(raw/'items_lite').mkdir()
            requests=[
                {'user_id':'u1','session_id':'s1','query':'q','split':'train','time_index':0,
                 'impressed_item_ids':['a','a','b'],'clicked_item_ids':['a','x'],'purchased_item_ids':['b','y']},
                {'user_id':'u1','session_id':'s1','query':'q','split':'train','time_index':1,
                 'impressed_item_ids':['a','c'],'clicked_item_ids':['a','c'],'purchased_item_ids':['a']},
                {'user_id':'u2','session_id':'s2','query':'empty','split':'valid','time_index':2,
                 'impressed_item_ids':[],'clicked_item_ids':[],'purchased_item_ids':[]}]
            items=[{'item_id':iid,'item_title':'test '+iid,'category_level1_id':'cat','category_level1_name':'测试'} for iid in ['a','b','c','unused']]
            files=[]
            for name,rows in [('recall_lite/train.jsonl',requests),('items_lite/train.jsonl',items)]:
                path=raw/name;path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
                files.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            lock=folder/'lock.json';lock.write_text(json.dumps({'repo_id':'synthetic-test-only','revision':revision,'files':files,'license_verification':'Self-created synthetic test data'}),encoding='utf-8')
            meta=builder.build(folder/'raw',lock,folder/'analytics',folder/'reports',memory='64MB',synthetic_test=True)
            self.assertEqual(meta['data_mode'],'synthetic')
            self.assertEqual(meta['counts'],{'requests':3,'items':4,'queries':2})
            self.assertEqual({k:meta['global_model'][k] for k in ['E','C','P','orphanC','orphanP','purchaseWithoutClick']},
                             {'E':4,'C':3,'P':2,'orphanC':1,'orphanP':1,'purchaseWithoutClick':1})
            self.assertEqual(meta['quality']['source_users'],2)
            self.assertEqual(meta['quality']['source_duplicate_list_entries'],1)
            self.assertEqual(meta['global_model']['metrics']['request_click_rate'],2/3)
            import duckdb
            with duckdb.connect() as db:
                path=folder/'analytics'/meta['snapshot_id']/'requests.parquet'
                original=json.loads(db.execute('SELECT feedback_input FROM read_parquet(?) WHERE request_id=?',[str(path),'KSL-1']).fetchone()[0])
                self.assertEqual(original['impressed_item_ids'],['a','a','b'])
                self.assertEqual(original['__basis__'],'provided_source_lists')
            self.assertNotIn('u1',json.dumps(meta))
            self.assertTrue(all(p['sha256']==builder.fingerprint(folder/'analytics'/meta['snapshot_id']/name) for name,p in meta['prepared_files'].items()))
            with self.assertRaises(ValueError):
                builder.build(folder/'raw',lock,folder/'analytics',folder/'reports',synthetic_test=True)


if __name__=='__main__':unittest.main()
