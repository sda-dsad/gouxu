import type {Category,ScopeModel} from './types.ts'
export type PulseMetric='click'|'purchase_feedback'
export interface PulseRow extends Category {rank:number;exposureShare:number;feedbackShare:number|null;gapPP:number|null;cumulativeE:number;cumulativeN:number;cumExposure:number;cumFeedback:number|null;feedback:number;feedbackRate:number|null}
/** Complete scope decomposition; presentation controls never redefine these totals. */
export function categoryPulse(model:Pick<ScopeModel,'E'|'C'|'P'|'categories'>,metric:PulseMetric){
 const key=metric==='click'?'C':'P',totalN=model[key]
 const valid=(v:number)=>Number.isSafeInteger(v)&&v>=0
 const consistent=[model.E,model.C,model.P].every(valid)&&model.C<=model.E&&model.P<=model.E&&model.categories.every(c=>[c.E,c.C,c.P].every(valid)&&c.C<=c.E&&c.P<=c.E)&&['E','C','P'].every(k=>model.categories.reduce((s,c)=>s+c[k as 'E'|'C'|'P'],0)===model[k as 'E'|'C'|'P'])&&new Set(model.categories.map(c=>c.id)).size===model.categories.length
 let cumulativeE=0,cumulativeN=0
 const rows:PulseRow[]=consistent?model.categories.filter(c=>c.E>0).slice().sort((a,b)=>b.E-a.E||a.id.localeCompare(b.id,'en')).map((c,i)=>{
  cumulativeE+=c.E;cumulativeN+=c[key]
  const exposureShare=c.E/model.E,feedbackShare=totalN>0?c[key]/totalN:null
  return {...c,rank:i+1,feedback:c[key],feedbackRate:c[key]/c.E,exposureShare,feedbackShare,gapPP:feedbackShare==null?null:100*(feedbackShare-exposureShare),cumulativeE,cumulativeN,cumExposure:cumulativeE/model.E,cumFeedback:totalN>0?cumulativeN/totalN:null}
 }):[]
 const n80=model.E>0&&consistent?(rows.find(r=>r.cumulativeE>=model.E*.8)?.rank??null):null
 const top3=rows.length?rows.slice(0,3).reduce((s,c)=>s+c.E,0)/model.E:null
 const max=Math.max(0,...rows.flatMap(r=>[r.exposureShare,r.feedbackShare??0]))
 const shareMax=max<=.1?.1:max<=.25?.25:max<=.5?.5:1
 return {rows,consistent,n80,top3,shareMax,totalE:model.E,totalN}
}
