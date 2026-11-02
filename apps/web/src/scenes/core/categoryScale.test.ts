import test from 'node:test'
import assert from 'node:assert/strict'
import {categoryScale} from './categoryScale.ts'

test('单查询数万曝光不再使用数百万快照量尺，最大柱占据可读高度',()=>{
  const values=[{E:10},{E:0},{E:12},{E:50653},{E:2},{E:0},{E:0},{E:76}],before=structuredClone(values)
  const axis=categoryScale(values,8700000,'auto')
  assert.equal(axis.max,60000)
  assert.deepEqual(axis.ticks,[0,15000,30000,45000,60000])
  assert.ok(values[3]!.E/axis.max>.8)
  assert.deepEqual(values,before)
})
test('全局量尺可恢复，切换模式不更改计数及线性比例',()=>{
  const values=[{E:10},{E:5},{E:0}],a=categoryScale(values,8700000,'auto'),b=categoryScale(values,8700000,'full')
  assert.equal(b.max,8700000)
  assert.equal(a.min,0);assert.equal(b.min,0)
  assert.equal((values[0]!.E/a.max)/(values[1]!.E/a.max),2)
  assert.equal(values[2]!.E/a.max,0)
})
test('单次曝光与空范围保留非零整数刻度，不制造零柱高度',()=>{
  for(const values of [[],[{E:0}],[{E:1}],[{E:2}],[{E:3}]]){
    const axis=categoryScale(values,8700000,'auto')
    assert.equal(axis.max,4)
    assert.deepEqual(axis.ticks,[0,1,2,3,4])
    assert.ok(values.every(c=>c.E<=axis.max))
  }
})
test('量尺只由当前范围决定，聚焦及类目顺序不影响结果',()=>{
  const values=[{E:500},{E:300},{E:1200}]
  assert.deepEqual(categoryScale(values,8700000,'auto'),categoryScale([...values].reverse(),9900000,'auto'))
  assert.ok(categoryScale([{E:50653},{E:150000}],8700000,'auto').max>=150000)
})
test('全部查询、不同大小范围及退化输入始终有界且包含所有有效柱',()=>{
  for(const high of [1,7,27,100,50653,8700000,17800904]){
    const axis=categoryScale([{E:high}],8700000,'auto')
    assert.ok(axis.max>=high&&axis.max<=(high<4?4:high*2))
    assert.ok(axis.ticks.every(Number.isInteger))
    assert.equal(new Set(axis.ticks).size,axis.ticks.length)
    assert.equal(axis.ticks.at(-1),axis.max)
  }
  for(const snapshot of [0,NaN,Infinity,-1])assert.equal(categoryScale([],snapshot,'full').max,1)
  assert.equal(categoryScale([{E:12}],1,'full').max,12)
})
