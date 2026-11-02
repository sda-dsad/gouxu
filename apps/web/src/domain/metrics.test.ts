import test from 'node:test'
import assert from 'node:assert/strict'
import { calculate, displayProducts, groupCategories } from './metrics.ts'
const rows=[{query:'q',impressed_item_ids:['a','a','b'],clicked_item_ids:['a','x'],purchased_item_ids:['b','y']},{query:'q',impressed_item_ids:['a','c'],clicked_item_ids:['a','c'],purchased_item_ids:['a']},{query:'',impressed_item_ids:[],clicked_item_ids:[],purchased_item_ids:[]}]
test('独立手算保留购买无点击与曝光外反馈',()=>assert.deepEqual(calculate(rows),{requests:3,E:4,C:3,P:2,orphanC:1,orphanP:1,purchaseWithoutClick:1,click:.75,purchase:.5}))
test('原始重复列表不被改写',()=>{calculate(rows);assert.deepEqual(rows[0].impressed_item_ids,['a','a','b'])})
test('零分母是null',()=>assert.equal(calculate([]).click,null))
test('绘制阈值和选中置换不篡改源范围',()=>{const all=[{id:'a',E:20},{id:'b',E:10},{id:'c',E:5}];assert.deepEqual(displayProducts(all,2,0,'c').map(x=>x.id),['a','c']);assert.equal(all.reduce((s,p)=>s+p.E,0),35);assert.deepEqual(displayProducts(all,2,6,'c').map(x=>x.id),['a','b'])})
test('其他与UNKNOWN独立且合计守恒',()=>{const result=groupCategories([{id:'a',E:10,C:1,P:0},{id:'b',E:3,C:0,P:1},{id:'UNKNOWN',E:2,C:0,P:0}],['a']);assert.equal(result.shown.reduce((n,c)=>n+c.E,0)+result.other.E,15);assert.equal(result.shown[1].id,'UNKNOWN')})

