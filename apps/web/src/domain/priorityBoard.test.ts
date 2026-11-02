import test from 'node:test'
import assert from 'node:assert/strict'
import {priorityRows,pairedRateScale,boardAdvice,feedbackPercent,type PriorityRow} from './priorityBoard.ts'
import type {Product,ScopeModel} from './types.ts'
const product:Product={id:'test',title:'合成商品',categoryId:'a',E:200,C:10,P:2,index:1}
const model:ScopeModel={snapshot_id:'synthetic',scope_id:'s',metric_version:'v',data_mode:'synthetic',exact_queries:['测试查询'],split_policy:['test'],requests:1000,E:1000,C:210,P:42,orphanC:0,orphanP:0,purchaseWithoutClick:0,categories:[{id:'a',name:'合成类目',color:'#456',textColor:'#123',E:1000,C:210,P:42}],products:[],scale_spec:{search_max:1000,item_max:200},coverage:{metadata_pairs:1}}
test('new overview keeps full peer reference, source counts and exposure order',()=>{
 const before=structuredClone(model),rows=priorityRows([product],model,'click',100)
 assert.equal(rows[0].reference,.25);assert.equal(rows[0].referenceE,800);assert.equal(rows[0].current,.05);assert.equal(rows[0].flagged,true);assert.deepEqual(model,before)
})
test('two bars and different products share a real zero-based rate scale',()=>{
 const rows=[{current:.016,reference:.027},{current:.04,reference:.02}] as PriorityRow[],scale=pairedRateScale(rows)
 assert.equal(scale.max,.05);assert.equal(scale.width(.016),32);assert.equal(scale.width(.027),54);assert.equal(scale.width(0),0);assert.equal(scale.width(null),0)
})
test('unplaced zero and unknown reference retain null, not fabricated zero performance',()=>{
 const rows=priorityRows([{...product,E:0,C:0,P:0},{...product,id:'unknown',categoryId:'UNKNOWN'}],model,'click',100)
 assert.equal(rows.find(p=>p.product.E===0)!.current,null);assert.ok(rows.every(p=>p.reference===null&&!p.qualified&&!p.flagged))
})
test('selected purchase advice and saved note follow the displayed metric even when click is also low',()=>{
 const row=priorityRows([product],model,'purchase_feedback',30)[0],advice=boardAdvice(row,model,'purchase_feedback',30)
 assert.equal(row.flagged,true);assert.ok(advice.title.includes('购买条件'));assert.ok(advice.note.includes('购买反馈'));assert.ok(advice.note.includes('同类其余商品曝光=800'));assert.ok(advice.note.includes('不确认原因'));assert.ok(advice.note.length<2000)
})
test('insufficient samples and non-flagged results never become optimization promises',()=>{
 const row=priorityRows([product],model,'click',300)[0],advice=boardAdvice(row,model,'click',300)
 assert.ok(advice.title.includes('补足数据'));assert.ok(advice.note.includes('降低要求不会增加数据'))
 const normal=boardAdvice({...row,qualified:true,flagged:false},model,'click',30);assert.ok(normal.title.includes('没有优先'));assert.ok(normal.note.includes('不表示商品最优'))
})
test('small real feedback remains distinguishable from zero and missing data',()=>{
 assert.equal(feedbackPercent(.0004),'0.040%');assert.equal(feedbackPercent(.0006),'0.060%');assert.equal(feedbackPercent(0),'0%');assert.equal(feedbackPercent(null),'—');assert.equal(feedbackPercent(.0000001),'<0.001%');assert.equal(feedbackPercent(.05128),'5.1%')
})
