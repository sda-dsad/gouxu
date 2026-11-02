import test from 'node:test'
import assert from 'node:assert/strict'
import {axisPercent,exposureScale,markerClusters,productScale,scalePosition} from './productLayout.ts'
import type {Product} from '../../domain/types'
const item=(id:string,E:number,click:number|null,purchase:number|null=0):Product=>({id,E,C:0,P:0,title:id,categoryId:'a',index:1,click_rate:click,purchase_rate:purchase})

test('低反馈商品展开到0—30%，保留零原点与线性刻度',()=>{
  const result=productScale([item('a',19,1/19),item('b',20,.25)],'click','auto')
  assert.ok(Math.abs(result.max-.3)<1e-12)
  assert.equal(result.min,0)
  assert.deepEqual(result.ticks.map(axisPercent),['0%','6%','12%','18%','24%','30%'])
})
test('完整量尺始终0—100%，自动上限不越过100%',()=>{
  assert.equal(productScale([item('a',1,1)],'click','auto').max,1)
  assert.deepEqual(productScale([item('a',19,.05)],'click','full').ticks,[0,.2,.4,.6,.8,1])
})
test('空、零分母与零反馈保留有限量尺且不修改原值',()=>{
  const source=[item('a',0,null),item('b',20,0)],before=structuredClone(source)
  assert.equal(productScale(source,'click','auto').max,.01)
  assert.equal(productScale([],'click','auto').max,.01)
  assert.deepEqual(source,before)
})
test('点击与购买反馈分别确定范围，小数刻度可读',()=>{
  const source=[item('a',200,.25,.005)]
  assert.ok(Math.abs(productScale(source,'click','auto').max-.3)<1e-12)
  assert.equal(productScale(source,'purchase_feedback','auto').max,.01)
  assert.equal(axisPercent(.002),'0.2%')
  assert.equal(axisPercent(.016),'1.6%')
  assert.equal(new Set(productScale([item('a',200,.02)],'click','auto').ticks.map(axisPercent)).size,6)
})
test('邻近点标签合并保留所有商品，孤立点保持独立',()=>{
  const points=[{id:'a',x:10,y:20,members:['a','a2']},{id:'b',x:25,y:20,members:['b']},{id:'c',x:110,y:200,members:['c']}]
  const before=structuredClone(points),result=markerClusters(points,null)
  assert.deepEqual(result.map(c=>c.members),[['a','a2','b'],['c']])
  assert.deepEqual(points,before)
  assert.equal(result[0]!.anchor,points[0])
})
test('选中商品作为已有坐标锚点，屏幕缩放重新区分标签',()=>{
  const points=[{id:'a',x:10,y:20,members:['a']},{id:'b',x:25,y:20,members:['b']}]
  assert.equal(markerClusters(points,'b')[0]!.anchor,points[1])
  assert.equal(markerClusters(points,'b',10).length,2)
})
test('链式遮挡只呈现一个入口且不漏点、不重复',()=>{
  const points=[0,20,40,60].map((x,i)=>({id:String(i),x,y:0,members:[String(i)]}))
  const result=markerClusters(points,null)
  assert.equal(result.length,1)
  assert.deepEqual(result[0]!.members,['0','1','2','3'])
})

test('横轴贴合当前曝光范围，扩展开非零起点的密集点',()=>{
  const source=[item('a',60,.1),item('b',62,.2)],before=structuredClone(source)
  const scale=exposureScale(source,100,'auto')
  assert.deepEqual({min:scale.min,max:scale.max,ticks:scale.ticks},{min:59,max:63,ticks:[59,60,61,62,63]})
  assert.equal(scalePosition(60,scale),.25)
  assert.equal(scalePosition(62,scale),.75)
  assert.deepEqual(source,before)
})
test('相同曝光和单点拥有非零跨度，点位居中且刻度为整数',()=>{
  for(const source of [[item('a',19,.1)],[item('a',19,.1),item('b',19,.2)]]){
    const scale=exposureScale(source,30,'auto')
    assert.deepEqual(scale.ticks,[18,19,20])
    assert.equal(scalePosition(19,scale),.5)
  }
})
test('横轴从0起保留快照量尺，小数曝光刻度不重复',()=>{
  const scale=exposureScale([item('a',60,.1)],100,'full')
  assert.equal(scale.min,0);assert.equal(scale.max,100);assert.equal(scalePosition(60,scale),.6)
  assert.deepEqual(exposureScale([item('a',1,.1)],1,'full').ticks,[0,1])
})
test('横轴空态与无效输入始终有限，不产生零跨度',()=>{
  for(const source of [[],[item('a',0,null),item('b',NaN,null)]]){
    const scale=exposureScale(source,0,'auto')
    assert.equal(scale.min,0);assert.equal(scale.max,1)
    assert.equal(scalePosition(0,scale),0)
  }
})
test('横轴保留离群点，曝光范围容纳全部原始读数',()=>{
  const source=[item('a',5,.1),item('b',20,.1),item('c',1500,.1)],scale=exposureScale(source,1600,'auto')
  assert.ok(scale.min<=5&&scale.max>=1500)
  assert.ok(scale.ticks.every(Number.isInteger))
  assert.equal(new Set(scale.ticks).size,scale.ticks.length)
  assert.ok(source.every(p=>scalePosition(p.E,scale)>=0&&scalePosition(p.E,scale)<=1))
})
test('显示商品改变后重新拟合，切回完整量尺仍保留原数据',()=>{
  const source=[item('a',10,.1),item('b',28,.2)]
  assert.deepEqual(exposureScale(source,30,'auto').ticks,[5,10,15,20,25,30])
  assert.equal(exposureScale([source[1]!],30,'auto').min,27)
  assert.equal(exposureScale(source,30,'full').max,30)
})
