<script setup lang="ts">
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import type {PriorityRow} from '../domain/priorityBoard'
import {feedbackPercent} from '../domain/priorityBoard'
import {number,ratio} from '../domain/types'
import {exposureTreemap} from '../domain/exposureTreemap'
const props=defineProps<{rows:PriorityRow[];selected:string|null;metric:'click'|'purchase_feedback';scopeE:number}>()
const emit=defineEmits<{select:[row:PriorityRow]}>(),host=ref<HTMLElement>(),frameWidth=ref(800),frameHeight=ref<number|null>(null),enlarged=ref(false)
let observer:ResizeObserver|undefined
watch(host,element=>{observer?.disconnect();if(element){observer=new ResizeObserver(entries=>{const rect=entries[0]?.contentRect;if(rect){frameWidth.value=Math.max(1,Math.floor(rect.width));if(rect.height>0)frameHeight.value=Math.max(1,Math.floor(rect.height))}});observer.observe(element)}})
onBeforeUnmount(()=>observer?.disconnect())
const width=computed(()=>enlarged.value?Math.max(1000,frameWidth.value):frameWidth.value)
const height=computed(()=>enlarged.value?1100:frameHeight.value??(frameWidth.value<600?650:frameWidth.value<850?570:520))
const tiles=computed(()=>exposureTreemap(props.rows.map(p=>({id:p.product.id,E:p.product.E})),width.value,height.value).map((t,i)=>({...t,row:props.rows.find(p=>p.product.id===t.id)!,index:i+1})))
const total=computed(()=>props.rows.reduce((sum,p)=>sum+p.product.E,0))
const zeroCount=computed(()=>props.rows.filter(p=>p.product.E===0).length)
const feedback=computed(()=>props.metric==='click'?'点击':'购买反馈')
const state=(row:PriorityRow)=>row.flagged?'review':row.qualified?'normal':'sample'
const label=(row:PriorityRow)=>row.flagged?feedback.value+'偏低':row.qualified?'暂未偏低':'数据待补'
function select(id:string){const row=props.rows.find(p=>p.product.id===id);if(row)emit('select',row)}
function accessible(row:PriorityRow){return `${row.product.title}，${number(row.product.E)}条曝光，${feedback.value}${feedbackPercent(row.current)}，同类${feedbackPercent(row.reference)}，${label(row)}`}
</script>
<template>
<section class="exposure-map" aria-label="商品曝光版图">
 <div class="em-heading"><div><h3>曝光版图 <small>面积＝曝光</small></h3></div><button class="em-zoom" :aria-pressed="enlarged" @click="enlarged=!enlarged">{{enlarged?'恢复适配':'放大版图 ＋'}}</button></div>
 <div class="em-legend"><span><i class="review"/>建议检查</span><span><i class="normal"/>暂未偏低</span><span><i class="sample"/>数据待补</span><strong>{{tiles.length}} 个色块 · {{number(total)}} 条曝光</strong></div>
 <div ref="host" class="em-host"><div class="em-scroll"><svg v-if="tiles.length" class="em-svg" :viewBox="`0 0 ${width} ${height}`" :style="{width:width+'px',height:height+'px'}" role="group" aria-label="矩形面积表示商品曝光数量" :data-width="width" :data-height="height" :data-total="total">
  <g v-for="tile in tiles" :key="tile.id" class="em-cell" :class="[state(tile.row),{selected:tile.id===selected}]" role="button" tabindex="0" :aria-label="accessible(tile.row)" :aria-pressed="tile.id===selected" :data-id="tile.id" :data-exposure="tile.E" :data-area="tile.width*tile.height" :data-state="state(tile.row)" @click="select(tile.id)" @keydown.enter.prevent="select(tile.id)" @keydown.space.prevent="select(tile.id)">
   <title>{{accessible(tile.row)}}</title>
   <rect :x="tile.x" :y="tile.y" :width="tile.width" :height="tile.height" rx="4"/>
   <foreignObject v-if="tile.width>=80&&tile.height>=75" :x="tile.x+12" :y="tile.y+8" :width="tile.width-24" :height="tile.height-16"><div xmlns="http://www.w3.org/1999/xhtml" class="em-tile-content" :class="{small:tile.height<110}"><span class="em-tile-state">{{String(tile.index).padStart(2,'0')}} · {{label(tile.row)}}</span><strong :class="{short:tile.height<140}">{{tile.row.product.title}}</strong><div class="em-tile-count">{{number(tile.E)}}<small v-if="tile.width>=130">条曝光</small></div></div></foreignObject>
   <text v-else-if="tile.width>=24&&tile.height>=22" :x="tile.x+tile.width/2" :y="tile.y+tile.height/2+4" text-anchor="middle" class="em-tile-number">{{tile.index}}</text>
  </g>
 </svg><div v-else class="em-no-area"><strong>暂无曝光</strong><span>可在商品索引中查看读数</span></div></div></div>
 <p class="em-caption">候选曝光覆盖 {{feedbackPercent(ratio(total,scopeE))}}</p>
 <details class="em-readings"><summary>商品索引 · {{rows.length}}</summary><div class="em-picker"><label>选商品<select :value="selected??''" aria-label="按商品名选择版图商品" @change="select(($event.target as HTMLSelectElement).value)"><option value="" disabled>选择商品</option><option v-for="(row,i) in rows" :key="row.product.id" :value="row.product.id">{{i+1}}. {{row.product.title}} · {{number(row.product.E)}}条曝光</option></select></label><p v-if="zeroCount">{{zeroCount}} 件零曝光，仅保留读数</p></div><button v-for="row in rows" :key="row.product.id" @click="emit('select',row)"><strong>{{row.product.title}}</strong><span>{{number(row.product.E)}} 条曝光 · {{label(row)}} · 本商品 {{feedbackPercent(row.current)}} / 同类 {{feedbackPercent(row.reference)}}</span></button></details>
</section>
</template>
<style src="../theme/exposureTreemap.css"></style>
