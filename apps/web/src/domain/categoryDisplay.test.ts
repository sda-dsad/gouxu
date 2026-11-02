import test from 'node:test'
import assert from 'node:assert/strict'
import {categoryWindow} from './categoryDisplay.ts'
test('high exposure identities displace global low and zero categories',()=>{
 const categories=Array.from({length:12},(_,i)=>({id:String(i).padStart(2,'0'),E:i}))
 assert.deepEqual(categoryWindow(categories,null).map(c=>c.E),[11,10,9,8,7,6,5,4])
 assert.equal(categories[0]?.E,0)
})
test('selected lower category retains its true identity without OTHER',()=>{
 const rows=Array.from({length:12},(_,i)=>({id:String(i),E:i+1}))
 const selected=categoryWindow(rows,'0')
 assert.equal(selected.length,9);assert.equal(selected.at(-1)?.id,'0')
 assert.ok(selected.every(c=>c.id!=='OTHER'))
})
test('comparison selects shared categories by combined exposure',()=>{
 const rows=[{id:'a',E:1,aE:1,bE:99},{id:'b',E:20,aE:20,bE:0},{id:'z',E:90,aE:0,bE:0}]
 assert.deepEqual(categoryWindow(rows,null,1).map(c=>c.id),['a'])
})
test('all identities and deterministic tie ordering remain available',()=>{
 assert.deepEqual(categoryWindow([{id:'z',E:3},{id:'a',E:3}],null,Infinity).map(c=>c.id),['a','z'])
 assert.deepEqual(categoryWindow([],null),[])
})
