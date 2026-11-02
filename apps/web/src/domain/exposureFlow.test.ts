import test from 'node:test'
import assert from 'node:assert/strict'
import {exposureFlow,flowLabel} from './exposureFlow.ts'
import type {Category,Product} from './types'
const categories:Category[]=[{id:'a',name:'甲',color:'#7362DF',textColor:'#534397',E:60,C:10,P:3},{id:'b',name:'乙',color:'#4DB692',textColor:'#286A56',E:40,C:4,P:2},{id:'z',name:'零',color:'#4286D8',textColor:'#2D5C94',E:0,C:0,P:0}]
const product=(id:string,E:number,categoryId='a',displayCategoryId=categoryId):Product=>({id,title:id,E,C:0,P:0,categoryId,displayCategoryId,index:1})

test('范围、类目及代表商品加尾部均守恒，只有一个线性带宽量尺',()=>{
 const items=[product('i1',12),product('i2',18)],before=structuredClone({categories,items})
 const flow=exposureFlow(categories,100,'a',items,true)
 assert.equal(flow.incoming.reduce((n,p)=>n+p.E,0),100)
 assert.equal(flow.outgoing.reduce((n,p)=>n+p.E,0),60)
 assert.deepEqual(flow.parts.map(p=>p.E),[12,18,30])
 assert.equal(flow.parts.at(-1)?.remainder,true)
 assert.ok(flow.incoming.every(p=>p.d.endsWith('Z')&&!p.d.includes('NaN')))
 assert.ok(Math.abs((12*flow.unit)/(18*flow.unit)-2/3)<1e-12)
 assert.deepEqual({categories,items},before)
})
test('未加载完当前类目时不把旧商品或未知部分画成已完成分布',()=>{
 const flow=exposureFlow(categories,100,'b',[product('i1',12)],false)
 assert.equal(flow.parts.length,0);assert.equal(flow.outgoing.length,0)
 assert.equal(flow.incoming.length,2)
})
test('零曝光只有标签，空范围无带宽，不制造虚假曝光',()=>{
 const flow=exposureFlow(categories,100,'z',[],true)
 assert.equal(flow.outgoing.length,0)
 assert.ok(!flow.incoming.some(p=>p.categoryId==='z'))
 const empty=exposureFlow([],0,null,[],true)
 assert.equal(empty.unit,0);assert.equal(empty.incoming.length,0)
 assert.ok(Number.isFinite(empty.height)&&Number.isFinite(empty.rootTop))
})
test('聚焦类目只改变可视子集，原范围及类目计数保持不变',()=>{
 const flow=exposureFlow(categories,100,'a',[product('i1',12)],true,true)
 assert.equal(flow.shownTotal,60);assert.equal(flow.rows.length,1)
 assert.equal(flow.incoming.reduce((n,p)=>n+p.E,0),60)
 assert.equal(flow.parts.reduce((n,p)=>n+p.E,0),60)
 assert.equal(categories.reduce((n,c)=>n+c.E,0),100)
})
test('其他类目按显示归属连接，不丢失真实原类目信息',()=>{
 const other={...categories[0]!,id:'OTHER'}
 const p=product('i1',12,'source-category','OTHER')
 const flow=exposureFlow([other],60,'OTHER',[p],true)
 assert.equal(flow.parts[0]?.product?.categoryId,'source-category')
 assert.equal(flow.outgoing.reduce((n,p)=>n+p.E,0),60)
})
test('拒绝重复商品、错误类目、超额曝光及不守恒的输入',()=>{
 assert.throws(()=>exposureFlow(categories,101,'a',[],true))
 assert.throws(()=>exposureFlow(categories,100,'a',[product('i',12),product('i',12)],true))
 assert.throws(()=>exposureFlow(categories,100,'a',[product('i',12,'b')],true))
 assert.throws(()=>exposureFlow(categories,100,'a',[product('i',61)],true))
})
test('商品覆盖完整时不添加空尾部，长名称不拆开Unicode字符',()=>{
 const flow=exposureFlow(categories,100,'a',[product('i',60)],true)
 assert.equal(flow.parts.length,1);assert.equal(flow.parts[0]?.remainder,false)
 assert.equal(flowLabel('😀甲乙丙',2),'😀甲…')
})
test('many real categories keep source and leading products visible while conserving every band',()=>{
 const many=Array.from({length:81},(_,i)=>({...categories[0]!,id:String(i),E:100-i}))
 const total=many.reduce((n,c)=>n+c.E,0)
 const flow=exposureFlow(many,total,'0',[product('p',40,'0')],true)
 assert.equal(flow.rows.length,81)
 assert.equal(flow.incoming.reduce((n,c)=>n+c.E,0),total)
 assert.ok(flow.rootCenter<=360&&flow.children.every(c=>c.y<720))
 assert.ok(flow.rootTop>=0&&total*flow.unit<=480)
 assert.equal(flow.outgoing.reduce((n,c)=>n+c.E,0),100)
})
