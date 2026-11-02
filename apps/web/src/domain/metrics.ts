import { ratio } from './types.ts'
export interface RequestRow { query:string; impressed_item_ids:string[]; clicked_item_ids:string[]; purchased_item_ids:string[] }
export function calculate(rows:RequestRow[]) {
 let E=0,C=0,P=0,orphanC=0,orphanP=0,purchaseWithoutClick=0
 for(const row of rows) {
  for(const f of ['impressed_item_ids','clicked_item_ids','purchased_item_ids'] as const) if(!Array.isArray(row[f])) throw new Error('缺少反馈列表')
  const i=new Set(row.impressed_item_ids),c=new Set(row.clicked_item_ids),p=new Set(row.purchased_item_ids)
  E+=i.size
  for(const id of c) if(i.has(id))C++;else orphanC++
  for(const id of p) if(i.has(id)){P++;if(!c.has(id))purchaseWithoutClick++}else orphanP++
 }
 return {requests:rows.length,E,C,P,orphanC,orphanP,purchaseWithoutClick,click:ratio(C,E),purchase:ratio(P,E)}
}
export function displayProducts<T extends {id:string;E:number}>(all:T[],topK:number,min:number,selected:string|null):T[] {
 const eligible=all.filter(p=>p.E>=min).sort((a,b)=>b.E-a.E||a.id.localeCompare(b.id))
 const out=eligible.slice(0,topK),current=eligible.find(p=>p.id===selected)
 if(current&&!out.some(p=>p.id===current.id))return [...out.slice(0,topK-1),current]
 return out
}
export function groupCategories<T extends {id:string;E:number;C:number;P:number}>(all:T[],keep:string[]) {
 const shown=all.filter(c=>keep.includes(c.id)||c.id==='UNKNOWN'),hidden=all.filter(c=>!keep.includes(c.id)&&c.id!=='UNKNOWN')
 return {shown,other:{id:'OTHER',E:hidden.reduce((n,c)=>n+c.E,0),C:hidden.reduce((n,c)=>n+c.C,0),P:hidden.reduce((n,c)=>n+c.P,0)},hidden}
}

