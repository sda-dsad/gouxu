import type {Category,Product} from './types'

export interface FlowPart {id:string;label:string;E:number;product:Product|null;remainder:boolean}
export interface FlowBand {id:string;E:number;d:string;categoryId:string;partId?:string}
export interface FlowRow {id:string;y:number;E:number}

// Every ribbon uses one linear count scale. Label cards have a fixed, non-quantitative size.
export function exposureFlow(categories:Category[],total:number,focusId:string|null,products:Product[],ready:boolean,focused=false){
 if(!Number.isSafeInteger(total)||total<0||categories.some(c=>!Number.isSafeInteger(c.E)||c.E<0))throw Error('曝光流向的计数无效')
 if(categories.reduce((n,c)=>n+c.E,0)!==total)throw Error('类目曝光合计与范围不一致')
 const selected=categories.find(c=>c.id===focusId)??categories.find(c=>c.E>0)??categories[0]??null
 const shown=focused&&selected?[selected]:categories
 const shownTotal=focused&&selected?selected.E:total
 const parts:FlowPart[]=[]
 if(selected&&ready){
  const seen=new Set<string>()
  for(const p of products){
   if(seen.has(p.id)||!Number.isSafeInteger(p.E)||p.E<=0||(p.displayCategoryId??p.categoryId)!==selected.id)throw Error('类目商品与曝光范围不一致')
   seen.add(p.id)
   parts.push({id:p.id,label:p.title,E:p.E,product:p,remainder:false})
  }
  const remainder=selected.E-parts.reduce((n,p)=>n+p.E,0)
  if(remainder<0)throw Error('商品曝光合计超过类目')
  if(remainder>0)parts.push({id:'__remainder__',label:'其余商品曝光',E:remainder,product:null,remainder:true})
 }
 const height=Math.max(580,160+Math.max(shown.length,parts.length)*82)
 const maxCategory=Math.max(0,...shown.map(c=>c.E))
 const unit=shownTotal?Math.min(Math.min(height-180,480)/shownTotal,54/Math.max(1,maxCategory)):0
 const center=(i:number,n:number)=>n<2?height/2:100+i*(height-200)/(n-1)
 const rows:FlowRow[]=shown.map((c,i)=>({id:c.id,E:c.E,y:center(i,shown.length)}))
 const childHeight=Math.max(580,160+parts.length*82)
 const selectedY=rows.find(c=>c.id===selected?.id)?.y??height/2
 const childOffset=Math.max(0,Math.min(height-childHeight,selectedY-childHeight/2))
 const children:FlowRow[]=parts.map((p,i)=>({id:p.id,E:p.E,y:(parts.length<2?childHeight/2:100+i*(childHeight-200)/(parts.length-1))+childOffset}))
 const rootCenter=Math.min(height/2,360)
 const rootTop=rootCenter-shownTotal*unit/2
 const incoming:FlowBand[]=[],outgoing:FlowBand[]=[]
 let rootOffset=0
 for(const row of rows){
  if(row.E)incoming.push({id:'range-'+row.id,E:row.E,categoryId:row.id,d:ribbon(206,rootTop+rootOffset*unit,400,row.y-row.E*unit/2,row.E*unit)})
  rootOffset+=row.E
 }
 const selectedRow=rows.find(c=>c.id===selected?.id)
 if(selectedRow){
  let offset=0
  for(const row of children){
   outgoing.push({id:'product-'+row.id,E:row.E,categoryId:selectedRow.id,partId:row.id,d:ribbon(574,selectedRow.y-selectedRow.E*unit/2+offset*unit,790,row.y-row.E*unit/2,row.E*unit)})
   offset+=row.E
  }
 }
 return {height,unit,rootTop,rootCenter,shownTotal,selected,shown,parts,rows,children,incoming,outgoing,ready}
}

export function ribbon(x0:number,y0:number,x1:number,y1:number,h:number):string{
 const bend=(x1-x0)*.48
 return `M${x0},${y0} C${x0+bend},${y0} ${x1-bend},${y1} ${x1},${y1} L${x1},${y1+h} C${x1-bend},${y1+h} ${x0+bend},${y0+h} ${x0},${y0+h} Z`
}
export function flowLabel(text:string,length=12){const chars=Array.from(text);return chars.length>length?chars.slice(0,length).join('')+'…':text}
