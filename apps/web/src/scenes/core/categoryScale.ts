import type {Category} from '../../domain/types'

export type CategoryAxisMode = 'auto' | 'full'
export interface CategoryScale {min:number;max:number;ticks:number[];mode:CategoryAxisMode}

// A display scale only: counts, category membership and scope denominators stay intact.
export function categoryScale(categories:Pick<Category,'E'>[], snapshotMax:number, mode:CategoryAxisMode):CategoryScale {
  const largest=Math.max(0,...categories.map(c=>c.E).filter(v=>Number.isSafeInteger(v)&&v>=0))
  let max=Math.max(1,Number.isFinite(snapshotMax)&&snapshotMax>0?snapshotMax:1,largest)
  if(mode==='auto') {
    const target=Math.max(4,largest*1.12),magnitude=10**Math.floor(Math.log10(target))
    const rounded=([1,1.2,1.5,2,2.5,3,4,5,6,8,10].find(n=>n*magnitude>=target)??10)*magnitude
    max=Math.ceil(rounded/4)*4
  }
  const ticks=[...new Set(Array.from({length:5},(_,i)=>Math.round(max*i/4)))]
  return {min:0,max,ticks,mode}
}
