import { defineStore } from 'pinia'
import { ref,computed } from 'vue'
import { request,post } from '../api/client'
import type {ScopeModel,SnapshotIndex,CameraPreset,View,Product,Review,CompareModel,QueryEntry} from '../domain/types'
import type {ProductAxisMode} from '../scenes/core/productLayout'
import type {CategoryAxisMode} from '../scenes/core/categoryScale'
import {diagnoseProduct,diagnosisReviewNote,DIAGNOSIS_RULE} from '../domain/merchantDiagnosis'
interface ProductPage{items:Product[];total:number;eligible:number;visible_exposed_pairs:number;snapshot_id:string;scope_id:string;metric_version:string}
export const useWorkbench=defineStore('workbench',()=>{
 const index=ref<SnapshotIndex|null>(null),model=ref<ScopeModel|null>(null),snapshots=ref<SnapshotIndex[]>([])
 const query=ref('ALL'),queryKey=ref('all'),focus=ref<string|null>(null),itemFocus=ref<string|null>(null)
 const view=ref<View>('search'),camera=ref<CameraPreset>('overview'),render=ref<'3d'|'2d'>('3d')
 const metric=ref<'click'|'purchase_feedback'>('click'),topK=ref(16),minPairs=ref(0),splitPolicy=ref<string[]>([])
 const productAxisMode=ref<ProductAxisMode>('auto')
 const productXAxisMode=ref<ProductAxisMode>('auto')
 const categoryAxisMode=ref<CategoryAxisMode>('auto')
 const diagnosisMinPairs=ref<number>(DIAGNOSIS_RULE.defaultMinPairs)
 const products=ref<Product[]>([]),detailProduct=ref<Product|null>(null),categoryProducts=ref<Product[]>([]),categoryProductsKey=ref('')
 const productTotal=ref(0),eligibleTotal=ref(0),visiblePairs=ref(0),queries=ref<QueryEntry[]>([])
 const reviews=ref<Review[]>([]),comparison=ref<CompareModel|null>(null)
 const loading=ref(false),error=ref(''),mode=ref<'real'|'demo'>('real'),compareLoading=ref(false)
 let active:AbortController|undefined,scopeToken=0,snapshotToken=0,itemToken=0,focusToken=0,findToken=0,compareToken=0
 let memoEpoch=0,memoChars=0
 const readMemo=new Map<string,{value:unknown;size:number}>()
 async function memoRead<T>(key:string,read:()=>Promise<T>):Promise<T>{
  const cached=readMemo.get(key)
  if(cached){readMemo.delete(key);readMemo.set(key,cached);return structuredClone(cached.value) as T}
  const epoch=memoEpoch,value=await read(),size=JSON.stringify(value).length
  if(epoch===memoEpoch&&size<=262144){
   const previous=readMemo.get(key);if(previous){memoChars-=previous.size;readMemo.delete(key)}
   while(readMemo.size&&(readMemo.size>=64||memoChars+size>2097152)){const oldest=readMemo.keys().next().value!;memoChars-=readMemo.get(oldest)!.size;readMemo.delete(oldest)}
   readMemo.set(key,{value:structuredClone(value),size});memoChars+=size
  }
  return value
 }
 const itemPage=(path:string,signal?:AbortSignal)=>memoRead('items:'+path,()=>request<ProductPage>(path,{signal}))
 const category=computed(()=>model.value?.categories.find(c=>c.id===focus.value)??model.value?.categories[0])
 const merchantDiagnosis=computed(()=>model.value&&detailProduct.value?.id===itemFocus.value?diagnoseProduct(detailProduct.value!,model.value,diagnosisMinPairs.value):null)
 const sceneModel=computed(()=>model.value?{...model.value,products:products.value}:null)
 const sceneLegend=computed(()=>view.value==='products'?[...new Map(products.value.map(p=>[p.categoryId,{id:p.categoryId,name:p.categoryName??p.categoryId,color:p.color??'#a3ada6'}])).values()]:view.value==='compare'?comparison.value?.categories??[]:model.value?.categories??[])
 function validate(m:{snapshot_id:string;metric_version:string}){if(m.snapshot_id!==index.value?.snapshot_id||m.metric_version!==index.value?.metric_version)throw Error('快照版本不匹配')}
 async function load(which:'real'|'demo'='real',selectedId?:string){
  const token=++snapshotToken;++scopeToken;++compareToken;++itemToken;++focusToken;++findToken;active?.abort();mode.value=which;loading.value=true;error.value='';model.value=null;comparison.value=null;products.value=[];detailProduct.value=null;categoryProducts.value=[]
  ++memoEpoch;readMemo.clear();memoChars=0
  try{
   const result=await request<{snapshots:SnapshotIndex[]}>('/snapshots');if(token!==snapshotToken)return
   snapshots.value=result.snapshots
   const candidate=selectedId?result.snapshots.find(s=>s.snapshot_id===selectedId):result.snapshots.find(s=>which==='demo'?s.data_mode==='synthetic':s.data_mode==='public_real_subset')
   if(!candidate){index.value=null;loading.value=false;return}
   const next=await request<SnapshotIndex>('/snapshots/'+candidate.snapshot_id+'/index');if(token!==snapshotToken)return
   index.value=next;queries.value=next.queries;splitPolicy.value=next.splits??[];focus.value=null;itemFocus.value=null;view.value='search';camera.value='overview'
   await select('ALL','all');await loadReviews()
  }catch(e){error.value=(e as Error).message;loading.value=false}
 }
 async function select(label:string,key='all'){
  if(!index.value)return
  active?.abort();active=new AbortController();const token=++scopeToken
  loading.value=true;error.value=''
  try{
   const body={snapshot_id:index.value.snapshot_id,exact_query_keys:key==='all'?[]:[key],split_policy:splitPolicy.value}
   const next=await memoRead('scope:'+JSON.stringify(body),()=>post<ScopeModel>('/scopes',body,active!.signal))
   if(token!==scopeToken)return
   validate(next)
   const cid=next.scope_id===model.value?.scope_id&&next.categories.some(c=>c.id===focus.value)?focus.value:next.categories[0]?.id??null
   const params=new URLSearchParams({limit:String(topK.value),min_pairs:String(minPairs.value)});if(itemFocus.value)params.set('selected_item_id',itemFocus.value)
   const [items,categoryItems]=await Promise.all([
    itemPage('/scopes/'+next.scope_id+'/items?'+params,active.signal),
    itemPage('/scopes/'+next.scope_id+'/items?limit=5&category_id='+encodeURIComponent(cid??''),active.signal)
   ])
   if(token!==scopeToken)return
   const selected=itemFocus.value??items.items[0]?.id??null
   const listed=items.items.find(p=>p.id===selected)
   const detail=listed??(selected?await request<Product>('/scopes/'+next.scope_id+'/items/'+encodeURIComponent(selected),{signal:active.signal}):null)
   if(token!==scopeToken)return
   ++itemToken;++focusToken;model.value=next;query.value=label;queryKey.value=key;focus.value=cid;itemFocus.value=selected
   products.value=items.items;productTotal.value=items.total;eligibleTotal.value=items.eligible;visiblePairs.value=items.visible_exposed_pairs;detailProduct.value=detail;categoryProducts.value=categoryItems.items;categoryProductsKey.value=next.scope_id+'|'+cid
  }catch(e){if((e as Error).name!=='AbortError'&&token===scopeToken)error.value=(e as Error).message}
  finally{if(token===scopeToken)loading.value=false}
 }
 async function findQueries(text:string){
  if(!index.value)return
  const token=++findToken
  try{const result=await request<{queries:QueryEntry[]}>('/snapshots/'+index.value.snapshot_id+'/queries?find='+encodeURIComponent(text)+'&limit=100');if(token===findToken)queries.value=result.queries}catch(e){error.value=(e as Error).message}
 }
 async function refreshProducts(){
  if(!model.value)return
  const token=++itemToken,sid=model.value.scope_id
  const params=new URLSearchParams({limit:String(topK.value),min_pairs:String(minPairs.value)})
  if(itemFocus.value)params.set('selected_item_id',itemFocus.value)
  try{
   const result=await itemPage('/scopes/'+sid+'/items?'+params)
   if(token!==itemToken||sid!==model.value?.scope_id)return;validate(result)
   products.value=result.items;productTotal.value=result.total;eligibleTotal.value=result.eligible;visiblePairs.value=result.visible_exposed_pairs
   if(!itemFocus.value&&result.items.length)itemFocus.value=result.items[0].id
   if(itemFocus.value)await selectItem(itemFocus.value)
  }catch(e){error.value=(e as Error).message}
 }
 async function selectItem(id:string){
  if(!model.value)return;itemFocus.value=id
  const token=++focusToken,sid=model.value.scope_id
  const listed=products.value.find(p=>p.id===id)
  if(listed){detailProduct.value=listed;return}
  try{const p=await request<Product&{snapshot_id:string;scope_id:string;metric_version:string}>('/scopes/'+sid+'/items/'+encodeURIComponent(id));if(token===focusToken&&sid===model.value?.scope_id){validate(p);detailProduct.value=p}}catch(e){error.value=(e as Error).message}
 }
 async function refreshCategory(){
  if(!model.value||!category.value)return
  const sid=model.value.scope_id,cid=category.value.id
  try{const r=await itemPage('/scopes/'+sid+'/items?limit=5&category_id='+encodeURIComponent(cid));if(sid===model.value?.scope_id&&cid===category.value?.id){categoryProducts.value=r.items;categoryProductsKey.value=sid+'|'+cid}}catch(e){error.value=(e as Error).message}
 }
 async function setCategory(id:string){focus.value=id;await refreshCategory()}
 async function showProduct(id:string){view.value='products';camera.value='overview';itemFocus.value=id;await refreshProducts()}
 async function setView(next:View){view.value=next;camera.value='overview';if(next==='products'||next==='priority')await refreshProducts();if(next==='compare'&&!comparison.value)await freezeCompare([index.value?.queries[0]?.key??'all'],[index.value?.queries[1]?.key??'all'])}
 async function freezeCompare(aKeys:string[],bKeys:string[],same=false,aLabel?:string,bLabel?:string){
  if(!index.value)return;const token=++compareToken;compareLoading.value=true;error.value=''
  const sid=index.value.snapshot_id
  const name=(keys:string[])=>keys.includes('all')?'全部查询':keys.length===1?index.value?.queries.find(q=>q.key===keys[0])?.query??'单查询组':keys.length+'个查询'
  async function freeze(keys:string[],label?:string){
   const scope=await post<ScopeModel>('/scopes',{snapshot_id:sid,exact_query_keys:keys.includes('all')?[]:keys,split_policy:splitPolicy.value})
   return post<{cohort_id:string;scope_id:string;name:string}>('/cohorts',{scope_id:scope.scope_id,name:(label??name(keys)).slice(0,80)})
  }
  try{
   const a=await freeze(aKeys,aLabel),b=same?a:await freeze(bKeys,bLabel)
   const result=await post<CompareModel>('/compare',{cohort_a:a.cohort_id,cohort_b:b.cohort_id})
   if(token!==compareToken)return;validate(result);comparison.value=result
  }catch(e){if(token===compareToken)error.value=(e as Error).message}
  finally{if(token===compareToken)compareLoading.value=false}
 }
 async function sameGroup(){if(!comparison.value)return;const token=++compareToken;compareLoading.value=true;try{const cid=comparison.value.a.cohort.cohort_id,result=await post<CompareModel>('/compare',{cohort_a:cid,cohort_b:cid});if(token===compareToken){validate(result);comparison.value=result}}catch(e){if(token===compareToken)error.value=(e as Error).message}finally{if(token===compareToken)compareLoading.value=false}}
 async function loadReviews(){const r=await request<{items:Review[]}>('/review-items');reviews.value=r.items}
 async function openReview(item:Review){
  if(index.value?.snapshot_id!==item.snapshot_id)await load(item.snapshot_id.includes('synthetic')?'demo':'real',item.snapshot_id)
  active?.abort();++scopeToken;++itemToken;++focusToken
  const saved=await request<ScopeModel>('/scopes/'+item.scope_id+'/metrics');validate(saved)
  model.value=saved;splitPolicy.value=saved.split_policy;query.value='已保存范围';queryKey.value='saved';focus.value=saved.categories[0]?.id??null;itemFocus.value=null
  await Promise.all([refreshProducts(),refreshCategory()])
  if(item.target_type==='item'){view.value='products';await selectItem(item.target_id)}
  else if(item.target_type==='compare'){const ids=item.target_id.split('|');comparison.value=await post<CompareModel>('/compare',{cohort_a:ids[0],cohort_b:ids[1]});view.value='compare'}
  else view.value='search'
 }
 async function saveReview(note=''){
  if(!model.value)return
  let target_type:'query'|'item'|'compare'='query',target_id=model.value.scope_id,name=queryKey.value==='all'?'全部查询':query.value,scope_id=model.value.scope_id
  if((view.value==='products'||view.value==='priority')&&detailProduct.value){target_type='item';target_id=detailProduct.value.id;name=detailProduct.value.title}
  if(view.value==='compare'&&comparison.value){target_type='compare';target_id=comparison.value.a.cohort.cohort_id+'|'+comparison.value.b.cohort.cohort_id;scope_id=comparison.value.a.model.scope_id;name='对照：'+comparison.value.a.cohort.name+' / '+comparison.value.b.cohort.name}
  const saved=await post<Review>('/review-items',{scope_id,target_type,target_id,name:name.slice(0,400),note})
  if(note){const merged=diagnosisReviewNote(saved.note,note);if(merged!==saved.note)await request('/review-items/'+saved.id,{method:'PATCH',body:JSON.stringify({expected_version:saved.version,note:merged,status:saved.status})})}
  await loadReviews()
 }
 async function updateReview(item:Review,note:string,status:'pending'|'reviewed'){await request('/review-items/'+item.id,{method:'PATCH',body:JSON.stringify({expected_version:item.version,note,status})});await loadReviews()}
 async function removeReview(item:Review){await request('/review-items/'+item.id+'?expected_version='+item.version,{method:'DELETE'});await loadReviews()}
 return{diagnosisMinPairs,merchantDiagnosis,index,model,snapshots,query,queryKey,focus,itemFocus,view,camera,render,metric,productAxisMode,productXAxisMode,categoryAxisMode,topK,minPairs,splitPolicy,products,detailProduct,categoryProducts,categoryProductsKey,productTotal,eligibleTotal,visiblePairs,queries,reviews,comparison,loading,error,mode,compareLoading,category,sceneModel,sceneLegend,load,select,findQueries,refreshProducts,selectItem,setCategory,showProduct,setView,refreshCategory,freezeCompare,sameGroup,loadReviews,openReview,saveReview,updateReview,removeReview}
})

