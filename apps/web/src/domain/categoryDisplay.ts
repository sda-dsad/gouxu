interface CountedCategory{id:string;E:number;aE?:number;bE?:number}
export function categoryWindow<T extends CountedCategory>(categories:T[],focus:string|null,limit=8):T[]{
 const weight=(c:T)=>c.aE!==undefined||c.bE!==undefined?(c.aE??0)+(c.bE??0):c.E
 const ranked=[...categories].filter(c=>weight(c)>0).sort((a,b)=>weight(b)-weight(a)||a.id.localeCompare(b.id))
 const shown=ranked.slice(0,limit)
 const selected=ranked.find(c=>c.id===focus)
 if(selected&&!shown.some(c=>c.id===selected.id))shown.push(selected)
 return shown
}
