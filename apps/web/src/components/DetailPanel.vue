<script setup lang="ts">
import {useWorkbench} from '../stores/scope'
import {number,percent,ratio,delta} from '../domain/types'
const store=useWorkbench(),emit=defineEmits<{evidence:[];export:[];save:[];other:[];insights:[]}>()
async function openItem(id:string){await store.showProduct(id)}
</script>
<template>
<aside class="detail-panel">
 <template v-if="(store.view==='search'||store.view==='flow')&&store.category&&store.model">
  <div class="detail-eyebrow">当前类目<span><i :style="{background:store.category.color}"/>{{store.category.id}}</span></div><h2>{{store.category.name}}</h2><p class="detail-context">{{store.queryKey==='all'?'全部查询':store.query}} · {{number(store.model.requests)}} 条请求</p>
  <div class="detail-metric"><span>曝光配对数</span><strong>{{number(store.category.E)}}<small>条</small></strong><p>占本范围曝光的 {{percent(ratio(store.category.E,store.model.E))}}</p><div class="metric-track"><i :style="{background:store.category.color,width:100*(ratio(store.category.E,store.model.E)??0)+'%'}"/></div></div>
  <div class="detail-metric"><span>匹配点击占比</span><strong>{{percent(ratio(store.category.C,store.category.E))}}</strong><p>{{number(store.category.C)}} 条匹配点击 / {{number(store.category.E)}} 条曝光</p></div>
  <div class="detail-metric"><span>购买反馈占比</span><strong>{{percent(ratio(store.category.P,store.category.E))}}</strong><p>{{number(store.category.P)}} 条购买反馈 / {{number(store.category.E)}} 条曝光</p></div>
  <button v-if="store.category.id==='OTHER'" class="other-button" @click="emit('other')">查看其他类目的组成 ↗</button>
  <details class="detail-products"><summary>类目商品 · {{store.categoryProducts.length}}</summary><button v-for="p in store.categoryProducts" :key="p.id" @click="openItem(p.id)"><i :style="{background:p.color}"/><span :title="p.title">{{p.title}}</span><strong>{{number(p.E)}}</strong></button><p v-if="!store.categoryProducts.length" class="muted">当前范围没有匹配商品</p></details>
 </template>
 <template v-else-if="(store.view==='products'||store.view==='priority')&&store.detailProduct">
  <div class="detail-eyebrow">当前商品<span><i :style="{background:store.detailProduct.color}"/>#{{store.detailProduct.index.toString(36).toUpperCase()}}</span></div><h2>{{store.detailProduct.title}}</h2><p class="detail-context">{{store.detailProduct.categoryName}} · {{store.detailProduct.id}}</p>
  <div v-if="store.merchantDiagnosis&&!store.loading" class="merchant-compact" :data-state="store.merchantDiagnosis.state"><span>商家诊断 · 当前商品</span><strong>{{store.merchantDiagnosis.title}}</strong><button v-if="store.view==='priority'" class="merchant-detail-link" @click="store.showProduct(store.detailProduct.id)">查看数据依据与完整优化步骤 ↗</button><button v-else class="merchant-detail-link" @click="emit('insights')">查看优化建议 ↗</button></div>
  <div class="detail-metric"><span>曝光配对数</span><strong>{{number(store.detailProduct.E)}}<small>条</small></strong><p>同一请求，同一商品只计一个配对</p></div>
  <div class="detail-metric"><span>匹配点击占比</span><strong>{{percent(store.detailProduct.click_rate)}}</strong><p>{{number(store.detailProduct.C)}} / {{number(store.detailProduct.E)}} 条曝光</p></div>
  <div class="detail-metric"><span>购买反馈占比</span><strong>{{percent(store.detailProduct.purchase_rate)}}</strong><p>{{number(store.detailProduct.P)}} / {{number(store.detailProduct.E)}} 条曝光</p></div>
  <p class="detail-warning" v-if="store.detailProduct.E<store.minPairs">当前对象低于显示门槛，右侧保留精确读数。</p><p class="detail-warning" v-else-if="store.detailProduct.E<10">样本较少，先核对计数与原行。</p><p class="detail-description">当前样本仅描述反馈，<br>不自动判定商品好坏。</p>
 </template>
 <template v-else-if="store.view==='compare'&&store.comparison">
  <div class="detail-eyebrow">两组差异<span>B − A</span></div><h2>哪里不一样？</h2><p class="detail-context">冻结范围 · 描述性比较</p>
  <template v-for="m in [{name:'匹配点击占比',key:'C' as const,delta:store.comparison.click_delta_pp},{name:'购买反馈占比',key:'P' as const,delta:store.comparison.purchase_delta_pp}]" :key="m.key">
   <div class="detail-metric comparison-metric"><span>{{m.name}}</span><div v-for="(group,key) in {A:store.comparison.a.model,B:store.comparison.b.model}" :key="key" class="comparison-meter"><b>{{key}}</b><div><i :class="{tint:key==='A'}" :style="{width:100*(ratio(group[m.key],group.E)??0)+'%'}"/></div><strong>{{percent(ratio(group[m.key],group.E))}}</strong></div><p>A {{number(store.comparison.a.model[m.key])}} / {{number(store.comparison.a.model.E)}}　B {{number(store.comparison.b.model[m.key])}} / {{number(store.comparison.b.model.E)}}</p></div><div class="difference"><span>B − A</span><strong>{{delta(m.delta)}}<small>个百分点</small></strong></div>
  </template>
  <p class="detail-description">重叠请求 {{number(store.comparison.overlap_requests)}} 条。<br>差异不代表因果效果。</p>
 </template>
 <template v-else><h2>当前范围没有商品</h2><p class="detail-description">没有分母时占比显示“—”。</p></template>
 <div class="detail-actions"><button class="primary-button" :aria-label="(store.view==='products'||store.view==='priority')?'＋ 将商品加入复核':store.view==='compare'?'＋ 将对照加入复核':'＋ 将范围加入复核'" @click="emit('save')">加入复核 ＋</button><button class="secondary-button" aria-label="查看对应记录 ↗" @click="emit('evidence')">查看记录 ↗</button><button class="quiet-export" @click="emit('export')">导出这个分析范围 ↓</button></div>
</aside>
</template>

