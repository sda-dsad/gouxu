import type {Category, Product, ScopeModel} from './types'

export const DIAGNOSIS_RULE = {defaultMinPairs: 100, relativeGap: .2, minReferenceFeedback: 10} as const
type Counts = Pick<Product, 'E'|'C'|'P'>
export type DiagnosisState = 'no-exposure'|'small-sample'|'no-reference'|'low-click'|'low-purchase'|'no-obvious-gap'
export interface Advice {title: string; detail: string}
export interface FeedbackComparison {
 current: number|null; reference: number|null; deltaPP: number|null; eligible: boolean; lower: boolean
}
export interface MerchantDiagnosis {
 state: DiagnosisState; title: string; conclusion: string; category: Category|null; peers: Counts|null
 click: FeedbackComparison; purchase: FeedbackComparison; actions: Advice[]; minPairs: number; note: string
}
const n = (value:number)=>value.toLocaleString('zh-CN')
const pct = (value:number|null)=>value==null?'—':(value*100).toFixed(1)+'%'
const valid = (value:Counts)=>[value.E,value.C,value.P].every(v=>Number.isSafeInteger(v)&&v>=0)&&value.C<=value.E&&value.P<=value.E

/** Preserve an existing manual review when attaching a new diagnosis. */
export function diagnosisReviewNote(existing:string,incoming:string):string {
 if(!incoming||existing.includes(incoming))return existing
 const merged=existing?existing+'\n\n'+incoming:incoming
 if(merged.length>2000)throw Error('该商品已有较长复核备注，无法追加完整诊断。请在复核清单整理备注后再保存；原备注已保留。')
 return merged
}

/** Full-scope, exposure-weighted, same-category reference; never use rendered Top K as a population. */
export function diagnoseProduct(product:Product, model:ScopeModel, minPairs:number=DIAGNOSIS_RULE.defaultMinPairs):MerchantDiagnosis {
 minPairs=Number.isFinite(minPairs)?Math.max(1,Math.floor(minPairs)):DIAGNOSIS_RULE.defaultMinPairs
 const category=model.categories.find(c=>c.id===product.categoryId)??null
 const rest=category?{E:category.E-product.E,C:category.C-product.C,P:category.P-product.P}:null
 const peers=valid(product)&&rest&&valid(rest)?rest:null
 const enough=valid(product)&&product.E>=minPairs&&!!peers&&peers.E>=minPairs
 function comparison(key:'C'|'P'):FeedbackComparison {
  const current=valid(product)&&product.E>0?product[key]/product.E:null
  const reference=peers&&peers.E>0?peers[key]/peers.E:null
  const eligible=enough&&peers![key]>=DIAGNOSIS_RULE.minReferenceFeedback
  return {current,reference,deltaPP:current!=null&&reference!=null?(current-reference)*100:null,eligible,
   lower:eligible&&current!=null&&reference!=null&&current<reference&&current<=reference*(1-DIAGNOSIS_RULE.relativeGap)}
 }
 const click=comparison('C'),purchase=comparison('P')
 let state:DiagnosisState,title:string,conclusion:string,actions:Advice[]
 const query=model.exact_queries.length===1?`“${model.exact_queries[0].slice(0,120)}${model.exact_queries[0].length>120?'…':''}”`:'当前查询范围'
 const verify:Advice={title:'记录改动，再复查同口径数据',detail:'一次只验证一个改动。补充近期授权日志后，对比相同查询、类目和曝光口径；群组差异本身不能证明改动有效。'}
 if(product.E===0&&valid(product)) {
  state='no-exposure';title='当前范围没有曝光，暂不能评价反馈'
  conclusion='曝光分母为 0，点击与购买反馈占比均不成立。先核对商品与搜索范围是否匹配。'
  actions=[{title:'核对商品与分析范围',detail:'确认选中了正确商品、查询词和 split；没有曝光不等于商品没有需求。'},
   {title:'补充可用的曝光记录',detail:'导入包含这件商品的近期授权搜索日志，再观察展示与反馈。'},verify]
 } else if(!valid(product)||product.E<minPairs) {
  state='small-sample';title='先补充样本，再决定优化方向'
  conclusion=valid(product)?`当前商品 ${n(product.E)} 条曝光，未达到本次诊断门槛 ${n(minPairs)} 条。现有占比只供读数，不据此判断商品表现。`:'当前反馈计数未通过一致性检查，暂不判断商品表现，请核对对应记录。'
  actions=[{title:'先核对计数与对应记录',detail:'少量曝光或反馈容易造成占比波动，先确认当前查询和商品是否正确。'},
   {title:'积累同口径曝光',detail:'补充同一查询范围的授权数据；降低诊断门槛只改变筛选规则，不会增加样本。'},verify]
 } else if(!category||category.id==='UNKNOWN'||!peers||peers.E<minPairs) {
  state='no-reference';title='同类目参照不足，先查看原始反馈'
  conclusion=`当前商品有 ${n(product.E)} 条曝光，但找不到曝光达到 ${n(minPairs)} 条的有效同类目其余商品参照，暂不输出偏低判断。`
  actions=[{title:'核对类目与数据覆盖',detail:'确认商品类目映射和元数据完整；未知类目不能当作一种可比商品。'},
   {title:'使用可比的查询范围',detail:'选择能覆盖同类商品的查询，或补充近期授权日志；不要跨不相关类目拼凑参照。'},verify]
 } else if(click.lower) {
  state='low-click';title='优先检查搜索匹配与展示信息'
  conclusion=`点击占比 ${pct(click.current)}，低于同范围同类目其余商品的 ${pct(click.reference)}。${purchase.lower?'购买反馈占比也低于该参照。':''}这是需要优先复核的反馈差异，原因仍待检查。`
  actions=[{title:'核对搜索词与商品是否匹配',detail:`检查标题、品类和真实属性能否回应${query}；补足准确的规格与用途描述，避免堆砌不相关词。`},
   {title:'人工检查主图与展示卖点',detail:'检查图片是否清晰、卖点和实物是否一致，并记录待验证的问题；当前日志不能直接判断图片质量。'},verify]
 } else if(purchase.lower) {
  state='low-purchase';title='优先核对商品信息与购买条件'
  conclusion=`购买反馈占比 ${pct(purchase.current)}，低于同类目其余商品的 ${pct(purchase.reference)}；点击指标${click.eligible?'未触发偏低规则':'参照反馈数不足，暂不判断'}。不能据此确定是价格、库存或详情页造成的。`
  actions=[{title:'核对详情页是否说明关键规格',detail:'人工检查材质、尺寸、适用范围和交付承诺是否完整、准确，记录具体缺项。'},
   {title:'核对价格、库存与履约条件',detail:'结合店铺后台检查实际售价、可售规格和履约说明；这些字段在本页数据中未验证，不能直接建议降价。'},verify]
 } else {
  state='no-obvious-gap';title=click.eligible||purchase.eligible?'当前未触发反馈偏低规则':'参照反馈较少，继续积累证据'
  conclusion=`商品点击占比 ${pct(click.current)}、购买反馈占比 ${pct(purchase.current)}。${click.eligible||purchase.eligible?'在可判断的指标中，未出现比参照低 20% 及以上的情况；这不表示商品最优。':'同类目其余商品的两项反馈均不足 10 条，暂不做偏低判断。'}`
  actions=[{title:'保留已有信息，继续核对相关性',detail:`检查商品是否准确回应${query}，先保留可验证的卖点，不因单次读数大幅改动。`},
   {title:'选择具体查询继续观察',detail:'按商品相关的查询分别查看曝光与反馈，避免把不同需求混在一起解释。'},verify]
 }
 const reference=peers?`参照（已剔除当前商品）：E=${peers.E}，C=${peers.C}，P=${peers.P}。`:'无有效同类目参照。'
 const note=[`商家诊断：${title}`,`snapshot=${model.snapshot_id}; scope=${model.scope_id}; metric=${model.metric_version}`,
  `当前商品：E=${product.E}，C=${product.C}，P=${product.P}。`,reference,conclusion,
  `规则：商品与参照曝光均≥${minPairs}；参照对应反馈≥10；占比较参照低≥20%。`,
  ...actions.map((a,i)=>`${i+1}. ${a.title}：${a.detail}`),
  '描述性复核建议，未确认原因；购买反馈/曝光不等于点击后成交率或支付订单。'].join('\n')
 return {state,title,conclusion,category,peers,click,purchase,actions,minPairs,note}
}
