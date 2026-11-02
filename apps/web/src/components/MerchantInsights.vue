<script setup lang="ts">
import {computed} from 'vue'
import {useWorkbench} from '../stores/scope'
import {number,percent,ratio,delta} from '../domain/types'
const store=useWorkbench()
const minPairs=computed({get:()=>store.diagnosisMinPairs,set:(value:number)=>{store.diagnosisMinPairs=value}})
const emit=defineEmits<{save:[note:string];evidence:[]}>()
const product=computed(()=>store.view==='products'&&store.detailProduct?.id===store.itemFocus?store.detailProduct:null)
const report=computed(()=>product.value?store.merchantDiagnosis:null)
const categoryItems=computed(()=>store.categoryProductsKey===store.model?.scope_id+'|'+store.category?.id?store.categoryProducts:[])
const representativeE=computed(()=>categoryItems.value.reduce((n,p)=>n+p.E,0))
const leading=computed(()=>store.model?.categories.reduce((best,c)=>!best||c.E>best.E?c:best,store.model.categories[0]))
const label=computed(()=>store.queryKey==='all'?'全部查询':store.queryKey==='saved'?'已保存查询范围':store.query||'空查询')
const context=computed(()=>store.view==='compare'&&store.comparison?`A ${store.comparison.a.cohort.name} / B ${store.comparison.b.cohort.name} · 冻结查询组`:`${label.value} · ${store.model?.split_policy.join(' / ')||'无 split'}`)
const busy=computed(()=>store.loading||store.compareLoading)
</script>
<template>
<section v-if="store.model" id="merchant-insights" class="merchant-insights" aria-label="商家分析与优化建议" :aria-busy="busy" :data-state="busy?'loading':report?.state??store.view">
 <div class="merchant-heading"><div><span class="merchant-kicker">商家解读</span><span class="merchant-context" :title="context">{{context}}</span></div><label v-if="store.view==='products'">诊断最低曝光<select v-model.number="minPairs" aria-label="商家诊断最低曝光" :disabled="busy"><option :value="30">30 条</option><option :value="100">100 条</option><option :value="300">300 条</option></select></label><span v-else class="merchant-badge">{{store.index?.data_mode==='synthetic'?'合成演示 · 方法示例':'历史样本 · 描述性分析'}}</span></div>
 <p v-if="busy" class="merchant-wait" role="status">正在更新分析范围，完成后显示对应结论与建议…</p>
 <template v-else-if="store.view==='products'&&report&&product">
  <div class="merchant-product-grid">
   <div class="merchant-finding"><h2>{{report.title}}</h2><p class="merchant-object" :title="product.title">{{product.title}}</p><p class="merchant-conclusion">{{report.conclusion}}</p>
    <div class="merchant-rate-grid"><div v-for="m in [{name:'匹配点击占比',value:report.click,key:'C' as const},{name:'购买反馈占比',value:report.purchase,key:'P' as const}]" :key="m.key" class="merchant-rate"><span>{{m.name}}</span><strong>{{percent(m.value.current)}}<small :class="{'merchant-gap':m.value.lower}">{{delta(m.value.deltaPP)}} 个百分点</small></strong><p>本商品 {{number(product[m.key])}} / {{number(product.E)}}<br>同类目其余商品 {{report.peers?number(report.peers[m.key])+' / '+number(report.peers.E):'无有效参照'}} · {{percent(m.value.reference)}}</p><span class="merchant-eligibility">{{m.value.eligible?'达到当前诊断门槛':'样本或参照反馈不足，暂不判低'}}</span></div></div>
    <p class="merchant-reference">参照：当前查询与 split 下，{{report.category?.name||'对应类目'}}的其余商品，已剔除本商品；按完整曝光加权，包含图外商品。</p>
   </div>
   <div class="merchant-next"><span class="merchant-section-label">建议怎样优化 · 原因待人工核实</span><ol><li v-for="a in report.actions" :key="a.title"><strong>{{a.title}}</strong><p>{{a.detail}}</p></li></ol><div class="merchant-actions"><button class="primary-button" @click="emit('save',report.note)">保存诊断与优化待办 ＋</button><button class="text-button" @click="emit('evidence')">核对对应记录 ↗</button></div></div>
  </div>
  <details class="merchant-rules"><summary>判断依据与使用边界</summary><p>规则可复查：本商品与其余商品曝光都达到 {{number(report.minPairs)}} 条、参照对应反馈至少 10 条，且本商品占比比参照低至少 20%，才提示偏低。20% 是相对差值，并非 20 个百分点；门槛是复核筛选规则，不是统计显著性检验。</p><p>购买反馈占比 = 购买反馈 / 曝光，不是点击后成交率。价格、库存、主图和详情页未在当前数据中验证；这些是建议检查的方向。未绑定店铺归属，不声称是你的商品，也不预测销量、收入或优化收益。</p></details>
 </template>
 <p v-else-if="store.view==='products'" class="merchant-wait" role="status">{{store.itemFocus?'正在读取所选商品的反馈，请稍候…':'当前范围没有可分析的商品，请调整查询或显示门槛。'}}</p>
 <template v-else-if="store.view==='compare'&&store.comparison">
  <div class="merchant-scope-grid"><div><h2>两组反馈有差异，先检查需求与商品构成</h2><p class="merchant-conclusion">B 相比 A：匹配点击占比 {{delta(store.comparison.click_delta_pp)}} 个百分点，购买反馈占比 {{delta(store.comparison.purchase_delta_pp)}} 个百分点。两组重叠 {{number(store.comparison.overlap_requests)}} 条请求。</p></div><div class="merchant-next"><strong>商家下一步</strong><p>核对两组的查询需求、类目占比和样本量，定位差异来自哪些商品。当前是历史查询组对照，不能据此宣布某个标题、投放或优化方案有效。</p><button class="text-button" @click="emit('save','商家对照复核：检查两组查询需求、类目构成及样本量；描述性差异不代表优化的因果效果。')">保存对照复核待办 ＋</button></div></div>
 </template>
 <template v-else>
  <div class="merchant-scope-grid"><div><h2>{{store.queryKey==='all'?'先选一个相关搜索词，再判断商品如何优化':leading?`“${label}”的曝光主要流向「${leading.name}」`:'当前范围没有曝光，先核对数据与查询'}}</h2><p v-if="leading&&store.model.E" class="merchant-conclusion">最高曝光类目 {{number(leading.E)}} 条，占当前范围 {{percent(ratio(leading.E,store.model.E))}}。{{store.queryKey==='all'?'全局分布适合找分析入口，具体优化需要缩小到相关查询。':'先检查这个类目是否回应搜索需求，再查看具体商品的反馈；曝光集中不等于商品表现好。'}}</p><p v-else class="merchant-conclusion">没有曝光分母时，暂不能评价点击或购买反馈表现。</p><p class="merchant-reference">曝光量反映当前样本的展示配对，不等于搜索人数、销量或当前市场需求。</p></div><div class="merchant-next"><span class="merchant-section-label">从分布走向具体优化</span><p v-if="store.category&&categoryItems.length">当前「{{store.category.name}}」展示的 {{categoryItems.length}} 件代表商品，共覆盖该类目 {{percent(ratio(representativeE,store.category.E))}} 曝光。它们只代表展示部分，商品诊断使用完整类目作参照。</p><p v-else>在左侧选择搜索词、在图中选择类目，再点一件商品查看诊断。</p><div v-if="categoryItems.length" class="merchant-candidates"><button v-for="p in categoryItems.slice(0,3)" :key="p.id" @click="store.showProduct(p.id)" :title="p.title"><span>{{p.title}}</span><small>{{number(p.E)}} 曝光</small><b>查看优化建议 ↗</b></button></div></div></div>
 </template>
 <p class="merchant-scope-foot">{{store.index?.data_mode==='synthetic'?'当前为合成样本，只演示诊断方法。':store.index?.data_mode==='public_real_subset'?'当前为 2025 年公开历史样本；用于店铺经营需导入近期授权数据，并核对商品归属。':'当前为授权日志快照；请核对商品归属与数据窗口。'}}</p>
</section>
</template>
<style src="../theme/merchant.css"></style>
