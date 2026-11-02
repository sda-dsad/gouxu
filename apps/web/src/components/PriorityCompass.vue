<script setup lang="ts">
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {useWorkbench} from '../stores/scope'
import {number,percent,ratio} from '../domain/types'
import {compassData,compassLayout,compassClusters,compassDelta,type CompassPoint} from '../domain/priorityCompass'
const store=useWorkbench(),category=ref('all'),onlyFlagged=ref(false),axisMode=ref<'auto'|'linear'>('auto'),hover=ref<string|null>(null),expanded=ref<string[]>([]),plotHost=ref<HTMLElement>(),plotWidth=ref(900)
let observer:ResizeObserver|undefined
const all=computed(()=>store.model?compassData(store.products,store.model,store.metric,store.diagnosisMinPairs):null)
const rows=computed(()=>all.value?.points.filter(p=>(category.value==='all'||p.product.categoryId===category.value)&&(!onlyFlagged.value||p.flagged))??[])
const layout=computed(()=>compassLayout(rows.value,900,460,axisMode.value))
const clusters=computed(()=>compassClusters(layout.value.points,store.itemFocus,24*900/Math.max(680,plotWidth.value)))
const categories=computed(()=>store.model?.categories.filter(c=>store.products.some(p=>p.categoryId===c.id))??[])
const queue=computed(()=>all.value?.queue.filter(p=>category.value==='all'||p.product.categoryId===category.value)??[])
const active=computed(()=>all.value?.points.find(p=>p.product.id===(hover.value??store.itemFocus)))
const expandedPoints=computed(()=>all.value?.points.filter(p=>expanded.value.includes(p.product.id))??[])
const feedback=computed(()=>store.metric==='click'?'匹配点击':'购买反馈')
const metricKey=computed(()=>store.metric==='click'?'C':'P')
watch(()=>store.model?.scope_id,()=>{category.value='all';expanded.value=[];hover.value=null})
watch(()=>store.metric,()=>{expanded.value=[];hover.value=null})
watch(plotHost,host=>{observer?.disconnect();if(host){observer=new ResizeObserver(entries=>{plotWidth.value=entries[0]?.contentRect.width??900});observer.observe(host)}})
onBeforeUnmount(()=>observer?.disconnect())
function selectCluster(group:ReturnType<typeof compassClusters>[number]){expanded.value=group.members.length>1?group.members.map(p=>p.product.id):[];store.selectItem(group.anchor.product.id)}
function choose(p:CompassPoint){hover.value=null;store.selectItem(p.product.id)}
function accessible(p:CompassPoint){return `${p.product.title}，曝光${number(p.product.E)}条，${feedback.value}占比较同类目其余商品${compassDelta(p.deltaPP)}个百分点，${p.flagged?'触发偏低复核规则':p.qualified?'达到诊断门槛':'样本或参照反馈不足，仅供读数'}`}
</script>

<template>
<section class="priority-compass" aria-label="优化罗盘" :aria-busy="store.loading" v-if="store.model&&all">
 <div class="compass-heading"><div><p class="eyebrow">PRIORITY COMPASS / 先看差异，再决定先查谁</p><h2>同类参照，一眼找到复核方向</h2><p>横向看曝光，纵向看与各自同类参照的差值。选中商品，右侧查看诊断。</p></div><span class="compass-mark" aria-hidden="true">✳</span></div>
 <div class="compass-stats"><div><strong>{{number(all.qualified)}}</strong><span>达到当前诊断门槛</span></div><div><strong>{{number(all.queue.length)}}</strong><span>触发{{feedback}}偏低规则</span></div><div><strong>{{number(all.readOnly+all.unplaced.length)}}</strong><span>仅供读数 / 参照不足</span></div></div>
 <div class="compass-controls"><label>诊断最低曝光<select v-model.number="store.diagnosisMinPairs" aria-label="罗盘诊断最低曝光"><option :value="30">30 条</option><option :value="100">100 条</option><option :value="300">300 条</option></select></label><label>图内类目<select v-model="category" aria-label="罗盘图内类目"><option value="all">全部已加载类目</option><option v-for="c in categories" :key="c.id" :value="c.id">{{c.name}}</option></select></label><label class="compass-check"><input v-model="onlyFlagged" type="checkbox" aria-label="只看待复核商品">只看待复核</label><button class="text-button" @click="axisMode=axisMode==='auto'?'linear':'auto'">{{axisMode==='auto'?'切换线性曝光尺':'恢复自适应曝光尺'}}</button></div>
 <p v-if="store.loading" class="compass-wait" role="status">范围更新中，完成后显示对应商品的差异…</p>
 <template v-else>
 <div ref="plotHost" class="compass-scroll">
  <svg class="compass-svg" viewBox="0 0 900 460" role="group" aria-label="商品曝光与同类参照反馈差值图" :data-axis="layout.logarithmic?'log1p':'linear'" :data-shown="rows.length">
   <defs><linearGradient id="compass-positive" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d8e9df" stop-opacity=".7"/><stop offset="1" stop-color="#f5f8ef" stop-opacity=".15"/></linearGradient><linearGradient id="compass-negative" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff3dd" stop-opacity=".15"/><stop offset="1" stop-color="#f3d8bb" stop-opacity=".6"/></linearGradient></defs>
   <g aria-hidden="true"><rect :x="layout.left" :y="layout.top" :width="layout.right-layout.left" :height="layout.zeroY-layout.top" rx="10" fill="url(#compass-positive)"/><rect :x="layout.left" :y="layout.zeroY" :width="layout.right-layout.left" :height="layout.bottom-layout.zeroY" rx="10" fill="url(#compass-negative)"/>
    <text :x="layout.right-12" :y="layout.top+23" text-anchor="end" class="compass-zone">高于各自同类参照</text><text :x="layout.right-12" :y="layout.bottom-14" text-anchor="end" class="compass-zone">低于各自同类参照</text>
    <g v-for="tick in layout.yTicks" :key="tick.value"><line :x1="layout.left" :x2="layout.right" :y1="tick.y" :y2="tick.y" :class="tick.value===0?'compass-zero':'compass-grid'"/><text :x="layout.left-12" :y="tick.y+4" text-anchor="end" class="compass-tick">{{compassDelta(tick.value)}}</text></g>
    <g v-for="tick in layout.xTicks" :key="tick.value"><line :x1="tick.x" :x2="tick.x" :y1="layout.top" :y2="layout.bottom" class="compass-grid vertical"/><text :x="tick.x" :y="layout.bottom+24" text-anchor="middle" class="compass-tick">{{number(tick.value)}}</text></g>
    <line :x1="layout.left" :x2="layout.left" :y1="layout.top" :y2="layout.bottom" class="compass-axis"/><line :x1="layout.left" :x2="layout.right" :y1="layout.bottom" :y2="layout.bottom" class="compass-axis"/>
    <text :x="layout.left" y="22" class="compass-axis-title">{{feedback}}占比 − 各自同类参照（个百分点）</text><text :x="layout.right" y="446" text-anchor="end" class="compass-axis-title">曝光配对数 · {{layout.logarithmic?'log(1+曝光) 自适应尺':'线性尺'}} →</text>
    <rect :x="layout.left+8" :y="layout.zeroY-12" width="117" height="24" rx="5" fill="#fbfcf5"/><text :x="layout.left+17" :y="layout.zeroY+4" class="compass-zero-label">0 = 各自同类参照</text>
   </g>
   <g v-for="point in layout.points" :key="point.product.id" class="compass-original" :data-product="point.product.id" :data-exposure="point.product.E" :data-delta="point.deltaPP" :data-qualified="point.qualified" :data-flagged="point.flagged" aria-hidden="true"><line :x1="point.x" :x2="point.x" :y1="layout.zeroY" :y2="point.y" :stroke="point.product.color??'#6e9383'" :class="['compass-tether',{readonly:!point.qualified,chosen:point.product.id===store.itemFocus}]"/><circle :cx="point.x" :cy="point.y" r="3" :fill="point.qualified?(point.product.color??'#6e9383'):'#fffdf5'" :stroke="point.product.color??'#6e9383'" opacity=".55"/></g>
   <g v-for="group in clusters" :key="group.members.map(p=>p.product.id).join('|')" class="compass-hit" role="button" tabindex="0" :aria-label="group.members.length>1?`邻近${group.members.length}件商品，展开逐件查看`:accessible(group.anchor)" :aria-pressed="group.members.some(p=>p.product.id===store.itemFocus)" @click="selectCluster(group)" @keydown.enter.prevent="selectCluster(group)" @keydown.space.prevent="selectCluster(group)" @mouseenter="hover=group.anchor.product.id" @mouseleave="hover=null" @focus="hover=group.anchor.product.id" @blur="hover=null">
    <circle :cx="group.anchor.x" :cy="group.anchor.y" r="16" fill="transparent"/>
    <circle v-if="group.members.some(p=>p.product.id===store.itemFocus)" :cx="group.anchor.x" :cy="group.anchor.y" r="13" class="compass-selection-ring"/>
    <circle v-if="group.members.length>1" :cx="group.anchor.x" :cy="group.anchor.y" r="10" fill="#234f43" stroke="#fffdf5" stroke-width="2"/>
    <path v-else-if="group.anchor.flagged" :d="`M ${group.anchor.x} ${group.anchor.y-8} l 8 8 -8 8 -8 -8 Z`" :fill="group.anchor.product.color??'#6e9383'" stroke="#fffdf5" stroke-width="2"/>
    <circle v-else :cx="group.anchor.x" :cy="group.anchor.y" r="6.5" :fill="group.anchor.qualified?(group.anchor.product.color??'#6e9383'):'#fffdf5'" :stroke="group.anchor.product.color??'#6e9383'" stroke-width="2"/>
    <text v-if="group.members.length>1" :x="group.anchor.x" :y="group.anchor.y+4" text-anchor="middle" class="compass-count">{{group.members.length}}</text>
   </g>
   <text v-if="!rows.length" x="490" y="185" text-anchor="middle" class="compass-empty">{{onlyFlagged?'当前筛选没有触发偏低规则的商品':'当前筛选暂无可绘制的同类参照差值'}}</text>
  </svg>
 </div>
 <div class="compass-legend"><span>◆ 待复核</span><span>● 达到门槛</span><span>○ 样本或参照反馈不足，只供读数</span><span>数字 = 相邻商品，可展开</span></div>
 <div class="compass-focus" aria-live="polite" v-if="active"><div><strong>{{active.product.title}}</strong><span>{{active.product.categoryName}} · {{number(active.product.E)}} 条曝光 · {{active.qualified?'达到当前门槛':'未达诊断条件，仅供读数'}}</span></div><div class="compass-focus-value"><strong>{{compassDelta(active.deltaPP)}}<small>个百分点</small></strong><span>{{percent(active.current)}} vs {{percent(active.reference)}} 同类参照</span></div><button class="primary-button" @click="store.showProduct(active.product.id)">查看优化步骤 ↗</button><p>本商品 {{number(active.product[metricKey])}} / {{number(active.product.E)}}；其余同类商品 {{number(active.referenceCount)}} / {{number(active.referenceE)}}。连线表示差值，不是时间趋势。</p></div>
 <div v-else class="compass-focus empty">点击或用 Tab 选中图中商品，查看精确差值、计数和优化步骤。</div>
 <div v-if="expandedPoints.length>1" class="compass-neighbours"><span>邻近商品 · 原始坐标保持不变</span><button v-for="p in expandedPoints" :key="p.product.id" @click="choose(p)">{{p.product.title}}<b>{{compassDelta(p.deltaPP)}} 个百分点</b></button></div>
 <div class="compass-queue"><div class="compass-section-head"><h3>先复核这几件</h3><span>当前已加载候选内，按曝光从多到少 · {{queue.length}} 件触发规则</span></div><button v-for="(point,i) in queue.slice(0,5)" :key="point.product.id" class="compass-queue-item" @click="choose(point)"><b>{{String(i+1).padStart(2,'0')}}</b><span><strong>{{point.product.title}}</strong><small>{{point.product.categoryName}} · {{number(point.product.E)}} 曝光</small></span><em>{{compassDelta(point.deltaPP)}} <small>个百分点</small></em><span class="compass-queue-action">选中查看 →</span></button><p v-if="!queue.length">当前候选没有触发{{feedback}}偏低规则的商品。空心点不代表差商品；可核对门槛、类目或加载更多候选。</p></div>
 <details class="compass-accessible"><summary>逐件读数与未绘制商品（{{store.products.length}} 件）</summary><button v-for="p in all.points" :key="p.product.id" @click="choose(p)">{{p.product.title}}<span>{{number(p.product.E)}} 曝光 / {{compassDelta(p.deltaPP)}} 个百分点 / {{p.flagged?'待复核':p.qualified?'达到门槛':'只供读数'}}</span></button><button v-for="p in all.unplaced" :key="p.id" @click="store.selectItem(p.id)">{{p.title}}<span>零曝光或无有效同类参照，未伪造坐标</span></button></details>
 </template>
 <div class="compass-footer"><span>当前加载 {{number(store.products.length)}} / {{number(store.productTotal)}} 件商品 · 曝光覆盖 {{percent(ratio(all.loadedPairs,store.model.E))}}。本页不是全量商品排名；完整范围分母保留。</span><span>参照使用完整同类目并剔除本商品；偏低规则沿用商家诊断。颜色识别类目，形状提示门槛，不预测销量与收益。</span></div>
</section>
</template>
<style src="../theme/priorityCompass.css"></style>
