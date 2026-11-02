import test from 'node:test'
import assert from 'node:assert/strict'
import {compassData,compassLayout,compassClusters} from './priorityCompass.ts'
import type {Product,ScopeModel} from './types.ts'
const p=(id:string,E:number,C:number,P:number):Product=>({id,title:'合成商品'+id,index:1,categoryId:'a',E,C,P})
const model=(products:Product[]):ScopeModel=>({snapshot_id:'synthetic',scope_id:'s',metric_version:'v',data_mode:'synthetic',exact_queries:[],split_policy:['test'],requests:1000,E:1000,C:210,P:42,orphanC:0,orphanP:0,purchaseWithoutClick:0,categories:[{id:'a',name:'类目a',color:'#4488aa',textColor:'#123',E:1000,C:210,P:42}],products,scale_spec:{search_max:1000,item_max:200},coverage:{metadata_pairs:1}})
test('compass places exact peer-adjusted difference from full category, not visible products',()=>{
 const product=p('a',200,10,2),m=model([product]),before=structuredClone(m),d=compassData([product],m,'click',100)
 assert.equal(d.points[0].referenceE,800);assert.equal(d.points[0].reference,.25);assert.equal(d.points[0].deltaPP,-20);assert.equal(d.queue[0].product.id,'a');assert.deepEqual(m,before)
})
test('read-only small samples keep observed coordinate without claiming a flagged diagnosis',()=>{
 const product=p('a',30,0,0),d=compassData([product],model([product]),'click',100)
 assert.equal(d.points.length,1);assert.equal(d.readOnly,1);assert.equal(d.queue.length,0);assert.ok(d.points[0].deltaPP<0)
})
test('purchase feedback remains independent of recorded clicks',()=>{
 const product=p('a',200,0,30),d=compassData([product],model([product]),'purchase_feedback',30)
 assert.equal(d.points[0].current,.15);assert.equal(d.points[0].referenceCount,12);assert.ok(d.points[0].deltaPP>0)
})
test('missing category, zero exposure and unknown category go to unplaced list, never fake zero delta',()=>{
 const products=[p('zero',0,0,0),{...p('unknown',30,1,1),categoryId:'UNKNOWN'},{...p('missing',30,1,1),categoryId:'missing'}]
 const d=compassData(products,model(products),'click',30);assert.equal(d.points.length,0);assert.equal(d.unplaced.length,3)
})
test('review queue is transparent exposure order and deterministic ties, not estimated revenue',()=>{
 const products=[p('z',100,0,0),p('b',200,0,0),p('a',200,0,0)],d=compassData(products,model(products),'click',30)
 assert.deepEqual(d.queue.map(v=>v.product.id),['a','b','z'])
})
test('threshold changes qualification but not source rates or plot coordinates',()=>{
 const products=[p('a',50,1,0)],m=model(products),a=compassData(products,m,'click',30),b=compassData(products,m,'click',100)
 assert.equal(a.queue.length,1);assert.equal(b.queue.length,0);assert.equal(a.points[0].deltaPP,b.points[0].deltaPP)
})
test('auto logarithmic exposure axis retains original units, endpoint coverage and unique ticks',()=>{
 const products=[p('a',1,0,0),p('b',500,0,0)],d=compassData(products,model(products),'click',30),l=compassLayout(d.points)
 assert.equal(l.logarithmic,true);assert.equal(l.xTicks[0].value,0);assert.ok(l.xMax>=500);assert.equal(new Set(l.xTicks.map(v=>v.value)).size,l.xTicks.length)
 for(const point of l.points){assert.ok(point.x>=l.left&&point.x<=l.right);assert.ok(point.y>=l.top&&point.y<=l.bottom)}
 assert.ok(l.points[0].x<l.points[1].x||d.points[0].product.E>d.points[1].product.E)
})
test('linear axis positions are proportional and metric changes use one signed zero line',()=>{
 const products=[p('a',100,10,1),p('b',200,60,20)],d=compassData(products,model(products),'click',30),l=compassLayout(d.points,900,460,'linear')
 assert.equal(l.logarithmic,false);for(const point of l.points)assert.ok(Math.abs((point.x-l.left)/(l.right-l.left)-point.product.E/l.xMax)<1e-10)
 assert.ok(l.yTicks.some(t=>t.value===0&&t.y===l.zeroY))
})
test('empty and identical delta sets have finite readable axes and distinct formatted tick values',()=>{
 const l=compassLayout([]);assert.ok(l.yMax>0&&l.xMax>0);assert.ok(l.xTicks.every(t=>Number.isFinite(t.x)));assert.equal(new Set(l.yTicks.map(v=>v.value.toFixed(2))).size,5)
})
test('clusters keep every item and anchor to selected actual position without jitter',()=>{
 const products=[p('a',100,10,1),p('b',100,10,1),p('c',100,10,1)],l=compassLayout(compassData(products,model(products),'click',30).points),before=structuredClone(l.points),groups=compassClusters(l.points,'b')
 assert.equal(groups.length,1);assert.deepEqual(groups[0].members.map(v=>v.product.id),['a','b','c']);assert.equal(groups[0].anchor.product.id,'b');assert.deepEqual(l.points,before)
})
