import type {Product,ScopeModel} from './types'
import {compassData,type CompassMetric} from './priorityCompass.ts'

export interface PriorityRow {product:Product;current:number|null;reference:number|null;referenceE:number;referenceCount:number|null;qualified:boolean;flagged:boolean}
export function feedbackPercent(value:number|null):string {
 if(value==null||!Number.isFinite(value)||value<0)return '—'
 const p=value*100;if(p===0)return '0%';if(p<.001)return '<0.001%'
 return p.toFixed(p<.1?3:p<1?2:1)+'%'
}
export function priorityRows(products:Product[],model:ScopeModel,metric:CompassMetric,minPairs:number):PriorityRow[]{
 const data=compassData(products,model,metric,minPairs),points=new Map(data.points.map(p=>[p.product.id,p]))
 return [...products].sort((a,b)=>b.E-a.E||a.id.localeCompare(b.id)).map(product=>points.get(product.id)??{
  product,current:product.E>0?product[metric==='click'?'C':'P']/product.E:null,reference:null,referenceE:0,referenceCount:null,qualified:false,flagged:false
 })
}
/** Every paired bar uses one zero-based scale for the whole visible candidate set. */
export function pairedRateScale(rows:PriorityRow[]){
 const high=Math.max(.01,...rows.flatMap(p=>[p.current,p.reference]).filter((v):v is number=>v!=null&&Number.isFinite(v)&&v>=0&&v<=1))
 const unit=10**Math.floor(Math.log10(high)),scaled=high/unit,max=(scaled<=1?1:scaled<=2?2:scaled<=5?5:10)*unit
 return {max,width:(rate:number|null)=>rate==null?0:100*rate/max}
}
export function boardAdvice(row:PriorityRow,model:ScopeModel,metric:CompassMetric,minPairs:number){
 const purchase=metric==='purchase_feedback',label=purchase?'购买反馈':'匹配点击'
 const query=model.exact_queries.length===1?`“${model.exact_queries[0].slice(0,100)}”`:'当前查询'
 let title:string,summary:string,steps:{title:string;detail:string}[]
 if(!row.qualified){
  title='先补足数据，再决定是否调整'
  summary='当前商品或同类商品的数据不足，现有占比只供查看，暂不判断表现偏低。'
  steps=[{title:'确认选对查询与商品',detail:`核对这件商品是否与${query}相关，并确认类目和记录完整。`},{title:'积累同口径曝光',detail:`当前样本要求为${minPairs}条；降低要求不会增加数据。补充近期授权日志后再比较。`},{title:'先记录，不急于改动',detail:'保留已观察到的情况，避免根据少量反馈批量改标题或价格。'}]
 }else if(row.flagged&&purchase){
  title='先核对商品说明与购买条件'
  summary='购买反馈占比低于同类商品，值得优先检查；数据还不能确定具体原因。'
  steps=[{title:'把关键规格说明白',detail:'人工核对尺寸、材质、适用范围及交付承诺，补齐缺失或容易误解的描述。'},{title:'核对实际购买条件',detail:'到店铺后台检查可售规格、库存、价格与履约信息；本页没有验证这些字段，不能直接认定需要降价。'},{title:'记录改动，再用新数据验证',detail:'一次只验证一个调整，再用近期授权日志中的可比查询复查反馈。'}]
 }else if(row.flagged){
  title='先检查标题与展示信息'
  summary='有曝光，但点击占比低于同类商品。先核实搜索匹配与展示内容，再决定改什么。'
  steps=[{title:'标题是否回应搜索需求',detail:`核对标题、品类和真实属性能否回答${query}，只补充准确相关的规格与用途。`},{title:'主图是否把卖点说明白',detail:'人工查看主图清晰度、关键卖点与实物是否一致；日志没有图片，不能直接判断主图有问题。'},{title:'每次验证一个改动',detail:'记录修改内容，再补充同口径的新数据检查反馈变化；前后差异本身不能证明优化有效。'}]
 }else{
  title='当前没有优先调整信号'
  summary='在本次筛选规则下，该项反馈未明显低于同类商品。先保留准确的信息，继续观察。'
  steps=[{title:'保留准确的商品信息',detail:'核对标题与规格是否符合当前查询需求，不根据一次读数大幅改动。'},{title:'换相关查询继续检查',detail:'不同查询对应不同需求，可分别观察这件商品的曝光与反馈。'},{title:'补充近期数据复查',detail:'未触发检查规则不表示商品最优，也不能据此判断销量或利润。'}]
 }
 const note=[`优化罗盘建议 · ${label}`,`snapshot=${model.snapshot_id}; scope=${model.scope_id}; metric=${model.metric_version}`,
  `商品E=${row.product.E}; C=${row.product.C}; P=${row.product.P}。同类其余商品曝光=${row.referenceE}; 对应反馈=${row.referenceCount??'无有效参照'}。`,
  `样本要求=${minPairs}；参照对应反馈≥10；占比相对同类低至少20%才提示检查。`,title,summary,
  ...steps.map((s,i)=>`${i+1}. ${s.title}：${s.detail}`),'仅为待核实方向，不确认原因，不预测收益；购买反馈不等于支付订单。'].join('\n')
 return {title,summary,steps,note,label}
}
