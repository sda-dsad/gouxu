import type {Product,ScopeModel} from './types'
import {diagnoseProduct} from './merchantDiagnosis.ts'

export type CompassMetric='click'|'purchase_feedback'
export interface CompassPoint {product:Product;deltaPP:number;current:number;reference:number;referenceE:number;referenceCount:number;qualified:boolean;flagged:boolean}
export interface CompassLayout {points:(CompassPoint&{x:number;y:number})[];xMax:number;yMax:number;logarithmic:boolean;xTicks:{value:number;x:number}[];yTicks:{value:number;y:number}[];zeroY:number;left:number;right:number;top:number;bottom:number}
const stable=(a:CompassPoint,b:CompassPoint)=>b.product.E-a.product.E||a.product.id.localeCompare(b.product.id)

/** Interpretation layer only. Full same-category reference comes from the shared diagnosis. */
export function compassData(products:Product[],model:ScopeModel,metric:CompassMetric,minPairs:number){
 const points:CompassPoint[]=[],unplaced:Product[]=[]
 for(const product of products){
  const diagnosis=diagnoseProduct(product,model,minPairs),value=metric==='click'?diagnosis.click:diagnosis.purchase
  if(product.E<=0||diagnosis.category?.id==='UNKNOWN'||!diagnosis.peers||value.current==null||value.reference==null||value.deltaPP==null){unplaced.push(product);continue}
  points.push({product,deltaPP:value.deltaPP,current:value.current,reference:value.reference,referenceE:diagnosis.peers.E,referenceCount:diagnosis.peers[metric==='click'?'C':'P'],qualified:value.eligible,flagged:value.lower})
 }
 points.sort(stable)
 const queue=points.filter(p=>p.flagged).sort(stable)
 return {points,unplaced,queue,qualified:points.filter(p=>p.qualified).length,readOnly:points.filter(p=>!p.qualified).length,loadedPairs:products.reduce((sum,p)=>sum+p.E,0)}
}

function niceCeil(value:number){const unit=10**Math.floor(Math.log10(Math.max(value,.0001))),scaled=value/unit;return (scaled<=1?1:scaled<=2?2:scaled<=5?5:10)*unit}
export function compassLayout(points:CompassPoint[],width=900,height=460,mode:'auto'|'linear'='auto'):CompassLayout {
 const left=88,right=Math.max(left+100,width-30),top=45,bottom=Math.max(top+100,height-72)
 const exposures=points.map(p=>p.product.E),max=Math.max(1,...exposures),min=Math.max(1,Math.min(...exposures))
 const logarithmic=mode==='auto'&&max/min>=20,xMax=niceCeil(max),yMax=niceCeil(Math.max(.1,...points.map(p=>Math.abs(p.deltaPP))))
 const x=(value:number)=>left+(right-left)*(logarithmic?Math.log1p(value)/Math.log1p(xMax):value/xMax)
 const y=(value:number)=>top+(bottom-top)*(1-value/yMax)/2
 let values:number[]
 if(logarithmic){values=[0];for(let power=0;power<=Math.ceil(Math.log10(xMax));power++)for(const base of [1,3]){const v=base*10**power;if(v<xMax)values.push(v)}values.push(xMax);if(values.length>7){const source=values;values=[...new Set(Array.from({length:7},(_,i)=>source[Math.round(i*(source.length-1)/6)]))]}}
 else {const step=Math.max(1,Math.ceil(xMax/5));values=[0];for(let v=step;v<xMax;v+=step)values.push(v);values.push(xMax)}
 return {points:points.map(p=>({...p,x:x(p.product.E),y:y(p.deltaPP)})),xMax,yMax,logarithmic,xTicks:values.map(value=>({value,x:x(value)})),yTicks:[-yMax,-yMax/2,0,yMax/2,yMax].map(value=>({value,y:y(value)})),zeroY:y(0),left,right,top,bottom}
}

/** Cluster labels anchor to an original point; every original coordinate is still drawn. */
export function compassClusters(points:CompassLayout['points'],selected:string|null,radius=24){
 const groups:CompassLayout['points'][]=[]
 for(const point of points){const group=groups.find(g=>g.some(p=>Math.hypot(p.x-point.x,p.y-point.y)<radius));if(group)group.push(point);else groups.push([point])}
 // Merge transitive screen-neighbour components deterministically.
 for(let i=0;i<groups.length;i++)for(let j=i+1;j<groups.length;){if(groups[i].some(a=>groups[j].some(b=>Math.hypot(a.x-b.x,a.y-b.y)<radius))){groups[i].push(...groups[j]);groups.splice(j,1);i=-1;break}else j++}
 return groups.map(members=>({members,anchor:members.find(p=>p.product.id===selected)??members[0]}))
}
export const compassDelta=(value:number)=>(value>0?'+':'')+value.toFixed(2)
