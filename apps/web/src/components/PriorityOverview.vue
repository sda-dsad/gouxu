<script setup lang="ts">
import {computed,ref,watch,nextTick} from 'vue'
import {useWorkbench} from '../stores/scope'
import {number} from '../domain/types'
import {priorityRows,boardAdvice,feedbackPercent,type PriorityRow} from '../domain/priorityBoard'
import CompassDistribution from './PriorityCompass.vue'
import ExposureTreemap from './ExposureTreemap.vue'
defineProps<{busy?:boolean}>()
const emit=defineEmits<{save:[note:string];evidence:[];inspect:[]}>(),store=useWorkbench()
const category=ref('all'),tab=ref<'review'|'all'|'sample'|null>(null),advanced=ref(false),insight=ref<HTMLElement>()
const rows=computed(()=>store.model?priorityRows(store.products,store.model,store.metric,store.diagnosisMinPairs):[])
const filtered=computed(()=>rows.value.filter(p=>category.value==='all'||p.product.categoryId===category.value))
const review=computed(()=>filtered.value.filter(p=>p.flagged)),sample=computed(()=>filtered.value.filter(p=>!p.qualified))
const effectiveTab=computed(()=>tab.value??'all')
const selectedRows=computed(()=>effectiveTab.value==='review'?review.value:effectiveTab.value==='sample'?sample.value:filtered.value)
const active=computed(()=>rows.value.find(p=>p.product.id===store.itemFocus)??selectedRows.value[0])
const advice=computed(()=>active.value&&store.model?boardAdvice(active.value,store.model,store.metric,store.diagnosisMinPairs):null)
const feedback=computed(()=>store.metric==='click'?'点击':'购买反馈')
const key=computed(()=>store.metric==='click'?'C':'P')
const scopeName=computed(()=>store.queryKey==='all'?'全部查询':store.queryKey==='saved'?'已保存范围':store.query||'空查询')
const categories=computed(()=>store.model?.categories.filter(c=>rows.value.some(p=>p.product.categoryId===c.id))??[])
const canAct=computed(()=>!store.loading&&!store.error&&active.value?.product.id===store.detailProduct?.id)
watch(()=>store.model?.scope_id,()=>{category.value='all';tab.value=null;advanced.value=false})
watch(()=>store.metric,()=>{tab.value=null})
watch([()=>store.loading,()=>selectedRows.value.map(p=>p.product.id).join('|')],()=>{
 if(!store.loading&&selectedRows.value.length&&!selectedRows.value.some(p=>p.product.id===store.itemFocus))store.selectItem(selectedRows.value[0].product.id)
},{immediate:true})
async function choose(row:PriorityRow){await store.selectItem(row.product.id);await nextTick();if(matchMedia('(max-width:1100px)').matches)emit('inspect')}
function changeTab(value:'review'|'all'|'sample'){tab.value=value}
</script>
<template>
<section v-if="store.model" class="priority-overview" aria-label="商品优化建议" :aria-busy="store.loading">
 <div class="op-intro"><div><p class="op-scope"><i/><strong>{{scopeName}}</strong></p><h2 v-if="review.length"><em>{{review.length}} 件</em>待检查 <small>/ {{filtered.length}} 件候选</small></h2><h2 v-else-if="sample.length===filtered.length&&filtered.length">样本待补</h2><h2 v-else>暂无优先检查项</h2></div><div class="op-switch" role="group" aria-label="选择分析反馈"><button :class="{active:store.metric==='click'}" :aria-pressed="store.metric==='click'" @click="store.metric='click'">看点击表现</button><button :class="{active:store.metric==='purchase_feedback'}" :aria-pressed="store.metric==='purchase_feedback'" @click="store.metric='purchase_feedback'">看购买反馈</button></div></div>
 <div class="op-toolbar"><div class="op-tabs" role="group" aria-label="商品筛选"><button :class="{active:effectiveTab==='review'}" :aria-pressed="effectiveTab==='review'" @click="changeTab('review')">建议先检查 <b>{{review.length}}</b></button><button :class="{active:effectiveTab==='all'}" :aria-pressed="effectiveTab==='all'" @click="changeTab('all')">全部候选 <b>{{filtered.length}}</b></button><button :class="{active:effectiveTab==='sample'}" :aria-pressed="effectiveTab==='sample'" @click="changeTab('sample')">样本待补 <b>{{sample.length}}</b></button></div><div class="op-filters"><label>类目<select v-model="category" aria-label="优化建议类目"><option value="all">全部已加载类目</option><option v-for="c in categories" :key="c.id" :value="c.id">{{c.name}}</option></select></label><label>样本要求<select v-model.number="store.diagnosisMinPairs" aria-label="优化建议样本要求"><option :value="30">至少30条曝光</option><option :value="100">至少100条曝光</option><option :value="300">至少300条曝光</option></select></label></div></div>
 <p v-if="store.loading" class="op-loading" role="status">正在更新商品与分析结果…</p>
 <div v-else class="op-layout">
  <div class="op-candidates"><ExposureTreemap :rows="selectedRows" :selected="store.itemFocus" :metric="store.metric" :scope-e="store.model.E" @select="choose"/></div>
  <aside v-if="active&&advice" ref="insight" class="op-insight" aria-label="选中商品的优化建议" :data-id="active.product.id">
   <div class="op-insight-label"><span>优化建议</span><b>{{active.flagged?'建议检查':active.qualified?'继续观察':'先补样本'}}</b></div><h3 :title="active.product.title">{{active.product.title}}</h3><p class="op-insight-context">{{active.product.categoryName||active.product.categoryId}} · {{number(active.product.E)}} 条曝光</p>
   <div class="op-verdict"><strong>{{advice.title}}</strong></div>
   <div class="op-numbers"><div><span>本商品{{feedback}}占比</span><strong :class="{'op-low':active.flagged}">{{feedbackPercent(active.current)}}</strong><small>{{number(active.product[key])}} / {{number(active.product.E)}} 条曝光</small></div><div><span>同类商品{{feedback}}占比</span><strong>{{feedbackPercent(active.reference)}}</strong><small>{{active.referenceCount==null?'无有效参照':number(active.referenceCount)+' / '+number(active.referenceE)+' 条曝光'}}</small></div></div>
   <ol class="op-steps"><li v-for="(step,i) in advice.steps" :key="step.title"><b>{{i+1}}</b><details><summary>{{step.title}}</summary><p>{{step.detail}}</p></details></li></ol>
   <div class="op-actions"><button class="primary-button" aria-label="保存这份检查建议 ＋" :disabled="busy||!canAct" @click="emit('save',advice.note)">{{busy?'正在保存…':'保存建议 ＋'}}</button><button class="op-evidence" aria-label="查看对应记录 ↗" :disabled="busy||!canAct" @click="emit('evidence')">查看记录 ↗</button><button class="op-full" aria-label="打开完整商品分析 →" :disabled="!canAct" @click="store.showProduct(active.product.id)">完整分析 →</button></div>
   <p class="op-caveat">建议需人工核实</p>
  </aside>
 </div>
 <details class="op-method"><summary>读图与判断依据</summary><p>面积只比较图中候选的曝光，不是全量商品的市场份额；位置没有指标含义。小色块可放大或在商品索引中按名称选择，零曝光只保留读数。颜色表示当前反馈的检查状态，不是购买数量。</p><p v-if="advice">{{advice.summary}}</p><p>同类商品指同一快照、查询范围和拆分下，相同原始类目的其余商品，已剔除当前商品。参照使用完整类目，包含当前没有显示的商品。</p><p>本商品和同类商品曝光都达到所选样本要求、同类对应反馈至少10条，且本商品占比相对低至少20%，才建议优先检查。这是复核筛选规则，不是统计显著性检验，也不表示已确认原因。</p><p>点击和购买反馈都分别除以曝光；购买反馈不等于支付订单。类目筛选和样本要求不会改变原始计数或完整分析范围。当前日志没有验证主图、库存、价格或实际成交，不能直接认定原因。实际经营需导入近期授权数据并核对商品归属。</p></details>
 <details class="op-distribution" @toggle="advanced=($event.target as HTMLDetailsElement).open"><summary>完整分布图</summary><CompassDistribution v-if="advanced"/></details>
 <div class="op-coverage"><span><b>{{number(store.products.length)}}</b> / {{number(store.productTotal)}} 件候选</span><span>{{store.index?.data_mode==='synthetic'?'合成演示':store.index?.data_mode==='public_real_subset'?'2025 公开历史样本':'授权日志快照'}}</span></div>
</section>
</template>
<style src="../theme/priorityOverview.css"></style>
