import test from 'node:test'
import assert from 'node:assert/strict'
import {categoryPulse} from './categoryPulse.ts'
const c=(id:string,E:number,C:number,P:number)=>({id,name:id,E,C,P,color:'#123456',textColor:'#123456'})
const m={E:100,C:20,P:10,categories:[c('a',60,6,8),c('b',30,12,0),c('c',10,2,2)]}
test('share comparison uses complete and independent E C P denominators',()=>{const p=categoryPulse(m,'click');assert.equal(p.rows[0].exposureShare,.6);assert.equal(p.rows[0].feedbackShare,.3);assert.equal(p.rows[0].gapPP,-30);assert.equal(p.rows[0].feedbackRate,.1)})
test('purchases are retained even when exceeding category clicks',()=>{const p=categoryPulse(m,'purchase_feedback');assert.equal(p.rows[0].feedback,8);assert.equal(p.rows[0].feedbackShare,.8);assert.equal(p.rows[0].feedbackRate,8/60)})
test('all decomposition shares and cumulative endpoints conserve totals',()=>{for(const metric of ['click','purchase_feedback'] as const){const p=categoryPulse(m,metric);assert.ok(Math.abs(p.rows.reduce((s,r)=>s+r.exposureShare,0)-1)<1e-12);assert.ok(Math.abs(p.rows.reduce((s,r)=>s+r.feedbackShare!,0)-1)<1e-12);assert.equal(p.rows.at(-1)?.cumExposure,1);assert.equal(p.rows.at(-1)?.cumFeedback,1)}})
test('80 percent count comes from complete categories and top3 is exact',()=>{const p=categoryPulse(m,'click');assert.equal(p.n80,2);assert.equal(p.top3,1)})
test('all-zero feedback is undefined share rather than zero percent',()=>{const p=categoryPulse({E:10,C:0,P:0,categories:[c('a',10,0,0)]},'click');assert.equal(p.rows[0].feedbackShare,null);assert.equal(p.rows[0].gapPP,null);assert.equal(p.rows[0].cumFeedback,null);assert.equal(p.rows[0].feedbackRate,0)})
test('measured category feedback zero retains meaningful zero share',()=>{const p=categoryPulse(m,'purchase_feedback');assert.equal(p.rows[1].feedbackShare,0);assert.equal(p.rows[1].gapPP,-30)})
test('empty exposure has no invented share or concentration',()=>{const p=categoryPulse({E:0,C:0,P:0,categories:[]},'click');assert.deepEqual(p.rows,[]);assert.equal(p.top3,null);assert.equal(p.n80,null)})
test('one-category decomposition has no fabricated relative disadvantage',()=>{const p=categoryPulse({E:30,C:5,P:2,categories:[c('a',30,5,2)]},'click');assert.equal(p.rows[0].gapPP,0);assert.equal(p.n80,1)})
test('mismatched totals are reported without rescaling categories',()=>{const p=categoryPulse({...m,E:101},'click');assert.equal(p.consistent,false);assert.deepEqual(p.rows,[])})
test('invalid and duplicate identities do not plot misleading curves',()=>{for(const categories of [[c('a',100,101,0)],[c('a',60,10,5),c('a',40,10,5)]])assert.equal(categoryPulse({...m,categories},'click').consistent,false)})
test('exposure order is stable under metric changes, ties use identities',()=>{const v={E:100,C:20,P:10,categories:[c('b',50,19,0),c('a',50,1,10)]};assert.deepEqual(categoryPulse(v,'click').rows.map(r=>r.id),['a','b']);assert.deepEqual(categoryPulse(v,'purchase_feedback').rows.map(r=>r.id),['a','b'])})
test('source model is not mutated and low identities remain ungrouped',()=>{const frozen=structuredClone(m);categoryPulse(m,'click');assert.deepEqual(m,frozen);assert.deepEqual(categoryPulse(m,'click').rows.map(r=>r.id),['a','b','c'])})
