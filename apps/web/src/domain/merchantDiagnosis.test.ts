import {test} from 'node:test'
import assert from 'node:assert/strict'
import {diagnoseProduct,diagnosisReviewNote} from './merchantDiagnosis.ts'
import type {ScopeModel,Product} from './types.ts'

const item=(values:Partial<Product>={}):Product=>({id:'p1',title:'合成商品',categoryId:'A',index:0,E:200,C:10,P:2,...values})
function scope(p:Product,rest={E:800,C:160,P:40}):ScopeModel {
 return {snapshot_id:'synthetic',scope_id:'scope-test',metric_version:'test',data_mode:'synthetic',exact_queries:['测试查询'],split_policy:['train'],requests:1000,E:10000,C:500,P:100,orphanC:0,orphanP:0,purchaseWithoutClick:0,
  categories:[{id:'A',name:'合成类目',color:'#fff',textColor:'#000',E:p.E+rest.E,C:p.C+rest.C,P:p.P+rest.P},{id:'B',name:'其他真实类目',color:'#000',textColor:'#fff',E:9000,C:1,P:0}],products:[],scale_spec:{search_max:10000,item_max:1000},coverage:{metadata_pairs:1}}
}
test('diagnosis uses full same-category counts minus selected item, not Top K or scope rate',()=>{
 const p=item(),m=scope(p),before=structuredClone(m),d=diagnoseProduct(p,m)
 assert.deepEqual(d.peers,{E:800,C:160,P:40});assert.equal(d.click.current,.05);assert.equal(d.click.reference,.2)
 assert.ok(Math.abs(d.click.deltaPP!+15)<1e-9);assert.equal(d.state,'low-click');assert.deepEqual(m,before)
})
test('product supplied outside rendered Top K still receives full reference',()=>{
 const p=item(),m=scope(p);m.products=[item({id:'other'})];assert.equal(diagnoseProduct(p,m).state,'low-click')
})
test('small sample does not become a bad-product conclusion',()=>{
 const p=item({E:3,C:0,P:0});assert.equal(diagnoseProduct(p,scope(p)).state,'small-sample')
})
test('zero exposure keeps null feedback rates',()=>{
 const p=item({E:0,C:0,P:0}),d=diagnoseProduct(p,scope(p));assert.equal(d.state,'no-exposure');assert.equal(d.click.current,null);assert.equal(d.purchase.current,null)
})
test('selected item cannot be its own reference',()=>{
 const p=item(),d=diagnoseProduct(p,scope(p,{E:0,C:0,P:0}));assert.equal(d.state,'no-reference');assert.equal(d.click.reference,null)
})
test('missing or unknown category does not make a cross-category reference',()=>{
 for(const categoryId of ['missing','UNKNOWN']){const p=item({categoryId}),m=scope(p);assert.equal(diagnoseProduct(p,m).state,'no-reference')}
})
test('inconsistent category subtraction disables reference instead of clamping counts',()=>{
 const p=item(),m=scope(p);m.categories[0].C=0;assert.equal(diagnoseProduct(p,m).state,'no-reference');assert.equal(diagnoseProduct(p,m).peers,null)
})
test('purchase feedback is independent of clicks and retains P even if P>C',()=>{
 const p=item({C:10,P:30}),d=diagnoseProduct(p,scope(p));assert.equal(d.purchase.current,.15);assert.equal(d.peers!.P,40);assert.equal(d.state,'low-click')
})
test('purchase-only gap has its own conditional inspection steps',()=>{
 const p=item({C:50,P:0}),d=diagnoseProduct(p,scope(p));assert.equal(d.state,'low-purchase');assert.equal(d.click.lower,false);assert.ok(d.actions[1].detail.includes('不能直接建议降价'))
})
test('sparse reference feedback does not trigger an extreme-rate diagnosis',()=>{
 const p=item({C:0,P:0}),d=diagnoseProduct(p,scope(p,{E:800,C:9,P:9}));assert.equal(d.state,'no-obvious-gap');assert.equal(d.click.eligible,false);assert.equal(d.purchase.eligible,false)
})
test('relative gap is 20 percent, not 20 percentage points',()=>{
 const p=item({E:200,C:32,P:10}),d=diagnoseProduct(p,scope(p));assert.equal(d.state,'low-click');assert.ok(Math.abs(d.click.deltaPP!+4)<1e-9)
 const near=item({E:200,C:34,P:10});assert.equal(diagnoseProduct(near,scope(near)).state,'no-obvious-gap')
})
test('changing diagnostic threshold changes eligibility, not source counts or denominators',()=>{
 const p=item({E:50,C:0,P:0}),m=scope(p),before=structuredClone(m)
 assert.equal(diagnoseProduct(p,m,100).state,'small-sample');assert.equal(diagnoseProduct(p,m,30).state,'low-click');assert.deepEqual(m,before)
})
test('saved advice includes frozen identity, exact counts, rules and caveats within API limit',()=>{
 const p=item(),d=diagnoseProduct(p,scope(p));assert.ok(d.note.includes('scope=scope-test'));assert.ok(d.note.includes('E=800'));assert.ok(d.note.includes('未确认原因'));assert.ok(d.note.length<2000)
})
test('attaching diagnosis preserves existing manual notes and does not duplicate a repeated save',()=>{
 const merged=diagnosisReviewNote('原人工备注','本次诊断');assert.equal(merged,'原人工备注\n\n本次诊断')
 assert.equal(diagnosisReviewNote(merged,'本次诊断'),merged);assert.equal(diagnosisReviewNote(merged,''),merged)
})
test('overlong combined diagnosis refuses to overwrite or silently truncate existing notes',()=>{
 const existing='原'.repeat(1500);assert.throws(()=>diagnosisReviewNote(existing,'新'.repeat(501)),/原备注已保留/);assert.equal(existing.length,1500)
})
