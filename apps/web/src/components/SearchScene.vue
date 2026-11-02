<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,watch,nextTick,computed} from 'vue'
import {useWorkbench} from '../stores/scope'
import {RendererHost,type Label} from '../scenes/core/RendererHost'
import {percent,ratio,type Product} from '../domain/types'
import {axisPercent,exposureScale,markerClusters,productScale,scalePosition} from '../scenes/core/productLayout'
import {categoryScale} from '../scenes/core/categoryScale'
import {categoryWindow} from '../domain/categoryDisplay'
const store=useWorkbench(),host=ref<HTMLElement>(),labels=ref<Label[]>([]),fallback=ref(false),renderer=ref<Record<string,unknown>|null>(null)
const emit=defineEmits<{overlap:[Product[]]}>();let stage:RendererHost|undefined
const spaceSize=ref({width:820,height:490});let sizeObserver:ResizeObserver|undefined
const allCategories=ref(false)
const shownCategories=computed(()=>categoryWindow(store.model?.categories??[],store.category?.id??null,allCategories.value?Infinity:8))
const displayModel=computed(()=>store.sceneModel?{...store.sceneModel,categories:shownCategories.value}:null)
const displayComparison=computed(()=>store.comparison?{...store.comparison,categories:categoryWindow(store.comparison.categories,null,allCategories.value?Infinity:8)}:null)
const categoryCount=computed(()=>store.view==='compare'?store.comparison?.categories.length??0:store.model?.categories.length??0)
const shownCount=computed(()=>store.view==='compare'?displayComparison.value?.categories.length??0:shownCategories.value.length)
const legend=computed(()=>store.view==='products'?store.sceneLegend:store.view==='compare'?displayComparison.value?.categories??[]:shownCategories.value)
function toggleCategories(){allCategories.value=!allCategories.value;if(allCategories.value)store.render='2d'}
const groups=computed(()=>{const grouped=new Map<string,Product[]>();for(const p of store.products){const value=store.metric==='click'?p.click_rate:p.purchase_rate;if(value==null||!p.E)continue;const key=p.E+':'+value;grouped.set(key,[...(grouped.get(key)??[]),p])}return[...grouped.values()].map(m=>({members:m,item:m.find(p=>p.id===store.itemFocus)??m[0]}))})
const instruction=computed(()=>store.view==='search'?'柱子越高，曝光越多':store.view==='products'?'越右曝光越多，越高'+(store.metric==='click'?'点击':'购买反馈')+'占比越高':'同类同色，A 浅色 / B 原色')
const scale=computed(()=>productScale(store.products,store.metric,store.productAxisMode))
const xScale=computed(()=>exposureScale(store.products,store.model?.scale_spec.item_max??1,store.productXAxisMode))
const searchScale=computed(()=>categoryScale(store.model?.categories??[],store.model?.scale_spec.search_max??1,store.categoryAxisMode))
const flatClusters=computed(()=>markerClusters(groups.value.map(g=>({id:'item:'+g.item.id,x:productX(g.item.E),y:productY(g.item),members:g.members.map(p=>'item:'+p.id)})),store.itemFocus?'item:'+store.itemFocus:null,28/Math.max(.1,Math.min((spaceSize.value.width-28)/820,(spaceSize.value.height-28)/490))))
function refresh(){if(stage&&displayModel.value){stage.setData(displayModel.value,store.view==='products'?store.itemFocus:store.category?.id??null,store.view,store.metric,displayComparison.value,store.productAxisMode,store.productXAxisMode,searchScale.value);renderer.value=stage.info}}
function pick(id:string){if(id.startsWith('item:')){const key=id.slice(5);store.selectItem(key);const group=groups.value.find(g=>g.members.some(p=>p.id===key));if(group&&group.members.length>1)emit('overlap',group.members)}else store.setCategory(id.startsWith('cat:')?id.slice(4):id)}
function pickCluster(id:string,members?:string[]){if(members&&members.length>1){emit('overlap',store.products.filter(p=>members.includes('item:'+p.id)));return}pick(id)}
function pickFlat(id:string){pickCluster(id,flatClusters.value.find(c=>c.members.includes(id))?.members)}
function zoom(change:number){if(stage){stage.zoom=Math.max(.75,Math.min(1.12,stage.zoom+change));stage.draw()}}
function reset(){store.camera='overview';if(stage){stage.zoom=1;stage.setCamera('overview')}}
function productY(p:Product){return 426-(store.metric==='click'?p.click_rate??0:p.purchase_rate??0)/scale.value.max*370}
function productX(exposure:number){return 75+scalePosition(exposure,xScale.value)*680}
onMounted(()=>{sizeObserver=new ResizeObserver(entries=>{const r=entries[0]?.contentRect;if(r)spaceSize.value={width:r.width,height:r.height}});sizeObserver.observe(host.value!.parentElement!);try{stage=new RendererHost(host.value!,l=>labels.value=l,pick,()=>{fallback.value=true;store.render='2d'});refresh();(window as any).__GOUXU_RENDERER=()=>stage?.info}catch{fallback.value=true;store.render='2d'}})
watch(()=>[store.sceneModel,store.focus,store.itemFocus,store.view,store.metric,store.productAxisMode,store.productXAxisMode,store.categoryAxisMode,store.comparison,allCategories.value],refresh)
watch(()=>store.camera,v=>stage?.setCamera(v))
watch(()=>store.render,()=>nextTick(()=>stage?.draw()))
onBeforeUnmount(()=>{sizeObserver?.disconnect();stage?.dispose()})
</script>
<template>
<section class="stage-panel" aria-label="交互图形与平面读数">
 <div class="scene-top"><span class="scope-label"><i/>{{store.view==='compare'?'A / B 冻结查询组':store.queryKey==='all'?'全部查询':store.query}}</span><div class="segmented"><button :class="{active:store.render==='3d'}" :disabled="fallback" @click="store.render='3d'">立体</button><button :class="{active:store.render==='2d'}" @click="store.render='2d'">平面读数</button></div></div>
 <div class="chart-instruction"><span>{{instruction}}</span><span>{{store.view==='search'?(store.categoryAxisMode==='auto'?'当前范围量尺':'全局统一量尺')+' 0—'+searchScale.max.toLocaleString()+' 条':store.view==='products'?'每个标记同尺寸 · 深度固定':'共同量尺 0—100%'}}</span></div>
 <div v-if="store.view!=='products'" class="category-display-control"><span>按当前范围曝光排序 · 显示 {{shownCount}} / {{categoryCount}} 个真实类目 · 完整范围分母保留</span><button v-if="categoryCount>8" class="text-button" @click="toggleCategories">{{allCategories?'收起为高曝光类目':'查看全部真实类目'}}</button></div>
 <div v-if="store.view==='search'" class="scatter-tools category-scale-tools"><div class="segmented" role="group" aria-label="类目柱高度量尺"><button :class="{active:store.categoryAxisMode==='auto'}" :aria-pressed="store.categoryAxisMode==='auto'" @click="store.categoryAxisMode='auto'">按范围自适应</button><button :class="{active:store.categoryAxisMode==='full'}" :aria-pressed="store.categoryAxisMode==='full'" @click="store.categoryAxisMode='full'">全局统一量尺</button></div><span>零起点 · 线性{{store.categoryAxisMode==='auto'?' · 跨查询比较请留意刻度变化':''}}</span></div>
 <div v-if="store.view==='products'" class="scatter-tools"><div class="segmented" role="group" aria-label="商品纵轴范围"><button :class="{active:store.productAxisMode==='auto'}" :aria-pressed="store.productAxisMode==='auto'" @click="store.productAxisMode='auto'">自动范围</button><button :class="{active:store.productAxisMode==='full'}" :aria-pressed="store.productAxisMode==='full'" @click="store.productAxisMode='full'">0—100%</button></div><span class="scatter-range">纵轴 0—{{axisPercent(scale.max)}} · 线性{{store.productAxisMode==='auto'?' · 随当前显示商品调整':''}}</span><span class="scatter-help">× 数字可展开商品</span></div>
 <div v-if="store.view==='products'" class="scatter-tools scatter-x-tools"><div class="segmented" role="group" aria-label="商品横轴范围"><button :class="{active:store.productXAxisMode==='auto'}" :aria-pressed="store.productXAxisMode==='auto'" @click="store.productXAxisMode='auto'">横轴自适应</button><button :class="{active:store.productXAxisMode==='full'}" :aria-pressed="store.productXAxisMode==='full'" @click="store.productXAxisMode='full'">横轴从 0 起</button></div><span class="scatter-x-range">横轴 {{xScale.min.toLocaleString()}}—{{xScale.max.toLocaleString()}} 条 · 线性{{xScale.min>0?' · 局部范围':''}}</span></div>
 <div class="scene-space" :class="{flat:store.render==='2d'}">
  <div ref="host" class="canvas-host" v-show="store.render==='3d'"></div>
  <div class="labels" v-show="store.render==='3d'"><template v-for="(label,i) in labels" :key="i"><button v-if="label.id" :class="['scene-label',label.kind,{selected:label.id==='cat:'+store.category?.id||label.id==='item:'+store.itemFocus}]" :style="{left:label.x+'px',top:label.y+'px',color:label.color}" @click="pickCluster(label.id!,label.members)" :aria-label="label.aria??label.text" :title="label.aria??label.text">{{label.text}}</button><span v-else :class="['scene-label',label.kind]" :style="{left:label.x+'px',top:label.y+'px'}">{{label.text}}</span></template></div>
  <div v-if="store.render==='2d'&&store.view==='search'" class="flat-chart"><div v-for="c in shownCategories" :key="c.id" class="flat-row"><button @click="store.setCategory(c.id)" :aria-pressed="store.category?.id===c.id">{{c.name}}</button><div class="flat-track"><span :style="{width:100*c.E/searchScale.max+'%',background:c.color}"/></div><strong>{{c.E.toLocaleString()}}</strong></div></div>
  <div v-else-if="store.render==='2d'&&store.view==='compare'" class="flat-chart compare-flat"><div v-for="c in displayComparison?.categories" :key="c.id" class="flat-row"><button @click="store.setCategory(c.id)">{{c.name}}</button><div><div class="flat-track"><span :style="{width:100*(c.a??0)+'%',background:c.color,opacity:.45}"/></div><div class="flat-track"><span :style="{width:100*(c.b??0)+'%',background:c.color}"/></div></div><span>{{percent(c.a)}}<br>{{percent(c.b)}}</span></div></div>
  <svg v-else-if="store.render==='2d'&&store.view==='products'" class="flat-scatter" viewBox="0 0 820 490" role="img" :aria-label="store.metric==='click'?'商品曝光与点击占比':'商品曝光与购买反馈占比'">
   <g v-for="i in 6" :key="'y'+i"><line x1="75" :y1="426-(i-1)*74" x2="755" :y2="426-(i-1)*74"/><text x="24" :y="430-(i-1)*74">{{axisPercent(scale.ticks[i-1]!)}}</text></g>
   <g v-for="tick in xScale.ticks" :key="'x'+tick"><line :x1="productX(tick)" y1="55" :x2="productX(tick)" y2="426"/><text :x="productX(tick)" y="452" text-anchor="middle">{{tick.toLocaleString()}}</text></g>
   <text x="75" y="28">{{store.metric==='click'?'匹配点击占比':'购买反馈占比'}}</text><text x="608" y="480">曝光配对数（条）</text>
   <g v-for="group in groups" :key="group.item.id" class="flat-product" :data-item="group.item.id" :transform="'translate('+productX(group.item.E)+','+productY(group.item)+')'"><circle v-if="group.members.some(p=>p.id===store.itemFocus)" r="13" fill="none" stroke="#193e37" stroke-width="2"/><circle r="8" :fill="group.item.color" stroke="#fff" stroke-width="1.5" tabindex="0" role="button" :aria-label="group.item.title+(group.members.length>1?'，同坐标'+group.members.length+'件':'')" @click="pickFlat('item:'+group.item.id)" @keydown.enter="pickFlat('item:'+group.item.id)" @keydown.space.prevent="pickFlat('item:'+group.item.id)"><title>{{group.item.title}}</title></circle></g>
   <g v-for="cluster in flatClusters.filter(c=>c.members.length>1)" :key="cluster.anchor.id" class="flat-cluster" :transform="'translate('+cluster.anchor.x+','+cluster.anchor.y+')'" role="button" tabindex="0" :aria-label="'展开邻近商品，共'+cluster.members.length+'件'" @click="pickCluster(cluster.anchor.id,cluster.members)" @keydown.enter="pickCluster(cluster.anchor.id,cluster.members)" @keydown.space.prevent="pickCluster(cluster.anchor.id,cluster.members)"><rect x="-16" y="-12" width="32" height="24" rx="12"/><text text-anchor="middle" y="4">×{{cluster.members.length}}</text></g>
   <text v-if="!groups.length" x="280" y="245">没有达到显示门槛的商品</text>
  </svg>
 </div>
 <div v-if="store.view==='products'&&store.detailProduct" class="scatter-selection"><span>选中 #{{store.detailProduct.index.toString(36).toUpperCase()}}</span><strong :title="store.detailProduct.title">{{store.detailProduct.title}}</strong><span>{{store.detailProduct.E}} 条 / {{percent(store.metric==='click'?store.detailProduct.click_rate:store.detailProduct.purchase_rate)}}</span></div>
 <div class="camera-controls"><div class="segmented"><button v-for="(name,key) in {overview:'总览',front:'正视',top:'俯视'}" :key="key" :class="{active:store.camera===key}" :disabled="store.render==='2d'" @click="store.camera=key">{{name}}</button></div><span class="renderer-status">{{store.render==='2d'?(fallback?'WebGL不可用 · 平面读数':'平面读数'):renderer?.engine+' · WebGL2'}}</span><div class="zoom-buttons"><button aria-label="缩小" :disabled="store.render==='2d'" @click="zoom(-.08)">−</button><button :disabled="store.render==='2d'" @click="reset">复位</button><button aria-label="放大" :disabled="store.render==='2d'" @click="zoom(.06)">＋</button></div></div>
 <div class="scene-footer"><div class="legend"><span v-for="c in legend" :key="c.id"><i :style="{background:c.color}"/>{{c.name}}</span></div><span>{{store.view==='products'?'图中 '+store.products.length+' / '+store.productTotal+' 件 · 曝光覆盖 '+percent(ratio(store.visiblePairs,store.model?.E??0)):store.view==='compare'?'组内占比 · B − A 为百分点':'图中类目覆盖 '+percent(ratio(shownCategories.reduce((n,c)=>n+c.E,0),store.model?.E??0))+' · 完整分母保留'}}</span></div>
</section>
</template>
