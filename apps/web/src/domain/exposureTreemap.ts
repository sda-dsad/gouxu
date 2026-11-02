export interface ExposureWeight {id:string;E:number}
export interface ExposureTile extends ExposureWeight {x:number;y:number;width:number;height:number}

/** A deterministic binary treemap. Rectangle area is exactly proportional to E. */
export function exposureTreemap(items:ExposureWeight[],width:number,height:number):ExposureTile[]{
 if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)throw Error('曝光版图尺寸无效')
 const ids=new Set<string>()
 for(const item of items){if(ids.has(item.id)||!Number.isSafeInteger(item.E)||item.E<0)throw Error('曝光版图商品或计数无效');ids.add(item.id)}
 const source=items.filter(p=>p.E>0).map(p=>({...p})).sort((a,b)=>b.E-a.E||a.id.localeCompare(b.id))
 const total=source.reduce((sum,p)=>sum+p.E,0);if(!Number.isSafeInteger(total))throw Error('曝光版图合计无效')
 const tiles:ExposureTile[]=[]
 function split(rows:ExposureWeight[],sum:number,x:number,y:number,w:number,h:number){
  if(rows.length===1){tiles.push({...rows[0]!,x,y,width:w,height:h});return}
  let leftSum=0,bestSum=0,index=1,distance=Infinity
  for(let i=1;i<rows.length;i++){leftSum+=rows[i-1]!.E;const d=Math.abs(sum/2-leftSum);if(d<distance){distance=d;index=i;bestSum=leftSum}}
  if(w>=h){const a=w*bestSum/sum;split(rows.slice(0,index),bestSum,x,y,a,h);split(rows.slice(index),sum-bestSum,x+a,y,w-a,h)}
  else{const a=h*bestSum/sum;split(rows.slice(0,index),bestSum,x,y,w,a);split(rows.slice(index),sum-bestSum,x,y+a,w,h-a)}
 }
 if(source.length)split(source,total,0,0,width,height)
 return tiles
}
