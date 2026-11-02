import test from 'node:test'
import assert from 'node:assert/strict'
import {exposureTreemap} from './exposureTreemap.ts'
test('each rectangle exactly reflects exposure share in a hand-counted population',()=>{
 const rows=[{id:'a',E:6},{id:'b',E:3},{id:'c',E:1}],before=structuredClone(rows),tiles=exposureTreemap(rows,100,100)
 for(const tile of tiles)assert.ok(Math.abs(tile.width*tile.height-tile.E/10*10000)<1e-8)
 assert.deepEqual(rows,before);assert.equal(tiles.length,3)
})
test('all rectangles stay inside frame and conserve total area without overlap',()=>{
 const rows=Array.from({length:64},(_,i)=>({id:String(i),E:(i+1)**2})),tiles=exposureTreemap(rows,813,571)
 assert.ok(Math.abs(tiles.reduce((sum,p)=>sum+p.width*p.height,0)-813*571)<1e-6)
 for(const p of tiles){assert.ok(p.x>=0&&p.y>=0&&p.x+p.width<=813+1e-8&&p.y+p.height<=571+1e-8);for(const q of tiles){if(p===q)continue;const overlap=Math.max(0,Math.min(p.x+p.width,q.x+q.width)-Math.max(p.x,q.x))*Math.max(0,Math.min(p.y+p.height,q.y+q.height)-Math.max(p.y,q.y));assert.ok(overlap<1e-7)}}
})
test('zero exposure does not fabricate area and a single item uses the complete frame',()=>{
 assert.deepEqual(exposureTreemap([{id:'z',E:0}],300,650),[])
 assert.deepEqual(exposureTreemap([{id:'a',E:3},{id:'z',E:0}],300,650),[{id:'a',E:3,x:0,y:0,width:300,height:650}])
})
test('a tiny item keeps its truthful area instead of being enlarged for a label',()=>{
 const tiles=exposureTreemap([{id:'large',E:999999},{id:'small',E:1}],1000,500),small=tiles.find(p=>p.id==='small')!
 assert.ok(Math.abs(small.width*small.height-.5)<1e-7)
})
test('layout identity is stable across input order and does not depend on feedback state',()=>{
 const rows=[{id:'a',E:20},{id:'b',E:20},{id:'c',E:10}]
 assert.deepEqual(exposureTreemap(rows,800,500),exposureTreemap([...rows].reverse(),800,500))
})
test('responsive dimensions preserve each item exposure fraction',()=>{
 const rows=Array.from({length:16},(_,i)=>({id:String(i),E:100+i*7})),total=rows.reduce((sum,p)=>sum+p.E,0)
 for(const [w,h] of [[360,650],[850,520]])for(const p of exposureTreemap(rows,w,h))assert.ok(Math.abs(p.width*p.height/(w*h)-p.E/total)<1e-10)
})
test('invalid counts, duplicate identities and invalid frames are rejected',()=>{
 assert.throws(()=>exposureTreemap([{id:'a',E:-1}],100,100));assert.throws(()=>exposureTreemap([{id:'a',E:1.2}],100,100));assert.throws(()=>exposureTreemap([{id:'a',E:1},{id:'a',E:2}],100,100));assert.throws(()=>exposureTreemap([],0,100))
})
