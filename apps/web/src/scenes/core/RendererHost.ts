import * as THREE from 'three'
import type {CameraPreset,ScopeModel,CompareModel,View,Product} from '../../domain/types'
import {axisPercent,exposureScale,markerClusters,productScale,scalePosition,type ProductAxisMode,type ProductScale} from './productLayout'
import {categoryScale,type CategoryScale} from './categoryScale'
export interface Label{id?:string;text:string;x:number;y:number;kind:string;color?:string;aria?:string;members?:string[]}
export class RendererHost{
 readonly scene=new THREE.Scene();readonly camera=new THREE.OrthographicCamera(-9,9,6,-6,.1,100)
 readonly renderer:THREE.WebGLRenderer;readonly data=new THREE.Group();readonly raycaster=new THREE.Raycaster();readonly observer:ResizeObserver
 readonly box=new THREE.BoxGeometry(1,1,1);readonly sphere=new THREE.SphereGeometry(.15,20,12)
 readonly ring=new THREE.CylinderGeometry(.3,.3,.02,32);readonly plane=new THREE.PlaneGeometry(1,1)
 points:{id?:string;text:string;position:THREE.Vector3;kind:string;color?:string;aria?:string;members?:string[]}[]=[]
 productAxis:ProductScale=productScale([],'click','auto');productFocus:string|null=null
 productXAxis:ProductScale=exposureScale([],1,'auto')
 categoryAxis:CategoryScale=categoryScale([],1,'auto')
 zoom=1;preset:CameraPreset='overview';profile:View='search';frame=0;lost=false;models=0;frames:number[]=[];lowQuality=false
 readonly target=new THREE.Vector3(0,2.5,0)
 constructor(readonly host:HTMLElement,readonly update:(labels:Label[])=>void,readonly pick:(id:string)=>void,readonly fallback:()=>void){
  this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'default'})
  this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));this.renderer.setClearColor(0x000000,0);this.renderer.outputColorSpace=THREE.SRGBColorSpace
  this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=THREE.PCFShadowMap
  host.appendChild(this.renderer.domElement);this.renderer.domElement.setAttribute('aria-hidden','true')
  this.scene.add(this.data,new THREE.HemisphereLight(0xffffff,0xcbd4c6,2.5))
  const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(-4,10,7);light.castShadow=true
  light.shadow.mapSize.set(1024,1024);Object.assign(light.shadow.camera,{left:-10,right:10,top:10,bottom:-10,near:.1,far:30});light.shadow.bias=-.001;this.scene.add(light)
  this.observer=new ResizeObserver(()=>this.draw());this.observer.observe(host)
  this.renderer.domElement.addEventListener('click',this.onClick);this.renderer.domElement.addEventListener('webglcontextlost',this.onLost)
  document.addEventListener('visibilitychange',this.visibility);this.setCamera('overview',false)
 }
 readonly onLost=(event:Event)=>{event.preventDefault();this.lost=true;cancelAnimationFrame(this.frame);this.fallback()}
 readonly visibility=()=>{if(document.hidden){cancelAnimationFrame(this.frame);this.setCamera(this.preset,false)}else this.draw()}
 readonly onClick=(event:MouseEvent)=>{const r=this.host.getBoundingClientRect();this.raycaster.setFromCamera(new THREE.Vector2((event.clientX-r.left)/r.width*2-1,-(event.clientY-r.top)/r.height*2+1),this.camera);const found=this.raycaster.intersectObjects(this.data.children,true).find(x=>typeof x.object.userData.id==='string');if(found)this.pick(found.object.userData.id)}
 material(color:string){return new THREE.MeshStandardMaterial({color,roughness:.52,metalness:.06})}
 mesh(x:number,y:number,z:number,w:number,h:number,d:number,color:string,id?:string){const mesh=new THREE.Mesh(this.box,this.material(color));mesh.position.set(x,y,z);mesh.scale.set(w,h,d);mesh.castShadow=true;mesh.receiveShadow=true;if(id)mesh.userData.id=id;this.data.add(mesh);return mesh}
 label(x:number,y:number,z:number,text:string,kind:string,id?:string,color?:string,aria?:string,members?:string[]){this.points.push({id,text,kind,color,aria,members,position:new THREE.Vector3(x,y,z)})}
 outline(x:number,z:number,w:number,d:number,color:string){const points=[new THREE.Vector3(x-w/2,.012,z-d/2),new THREE.Vector3(x+w/2,.012,z-d/2),new THREE.Vector3(x+w/2,.012,z+d/2),new THREE.Vector3(x-w/2,.012,z+d/2),new THREE.Vector3(x-w/2,.012,z-d/2)];this.data.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color})))}
 clear(){for(const obj of [...this.data.children]){this.data.remove(obj);obj.traverse(node=>{if(node instanceof THREE.Mesh||node instanceof THREE.Line){const m=node.material;Array.isArray(m)?m.forEach(x=>x.dispose()):m.dispose();if(![this.box,this.sphere,this.ring,this.plane].some(g=>g===node.geometry))node.geometry.dispose()}})}this.points=[]}
 setData(model:ScopeModel,focus:string|null,view:View='search',metric:'click'|'purchase_feedback'='click',comparison:CompareModel|null=null,axisMode:ProductAxisMode='auto',xAxisMode:ProductAxisMode='auto',searchAxis:CategoryScale=categoryScale(model.categories,model.scale_spec.search_max,'auto')){
  const changed=this.profile!==view;this.profile=view;this.clear();this.models++
  this.productFocus=view==='products'&&focus?'item:'+focus:null;this.productAxis=productScale(model.products,metric,axisMode)
  this.productXAxis=exposureScale(model.products,model.scale_spec.item_max,xAxisMode)
  this.categoryAxis=searchAxis
  const ground=view==='products'?-.23:0
  this.mesh(0,-.16+ground,0,17,.3,4.6,'#e6e9df');this.mesh(0,-.025+ground,0,17,.05,4.6,'#f9faf5')
  if(view==='products')this.products(model,focus,metric);else if(view==='compare'&&comparison)this.compare(comparison,focus);else this.search(model,focus)
  if(changed)this.setCamera(this.preset,false);else this.draw()
 }
 search(model:ScopeModel,focus:string|null){
  const count=model.categories.length,step=Math.min(2,14/Math.max(1,count))
  for(const [i,c]of model.categories.entries()){
   const x=(i-(count-1)/2)*step,h=c.E/this.categoryAxis.max*5
   if(h>0){this.mesh(x,h/2,0,step*.62,h,1.05,c.color,'cat:'+c.id);const cap=new THREE.Mesh(this.plane,new THREE.MeshStandardMaterial({color:'#fff',side:THREE.DoubleSide,roughness:.7}));cap.rotation.x=-Math.PI/2;cap.position.set(x,h+.003,0);cap.scale.set(step*.45,.74,1);this.data.add(cap)}
   if(c.id===focus)this.outline(x,0,step*.8,1.4,'#193e37')
   this.label(x,h+.43,0,c.E.toLocaleString('zh-CN'),'value','cat:'+c.id,c.textColor,c.name+'，'+c.E+'条曝光配对')
   this.label(x,-.02,1.35,c.name,'category','cat:'+c.id,c.id===focus?'#193e37':'#526a5b')
  }
  for(const tick of this.categoryAxis.ticks)this.label(-8.1,tick/this.categoryAxis.max*5,0,tick.toLocaleString('zh-CN'),'axis')
  this.label(-7,5.65,0,'曝光配对数 · 条','axis-title')
 }
 groups(model:ScopeModel,metric:'click'|'purchase_feedback'){
  const grouped=new Map<string,Product[]>()
  for(const p of model.products){const value=metric==='click'?p.click_rate:p.purchase_rate;if(value==null||p.E===0)continue;const key=p.E+':'+value;grouped.set(key,[...(grouped.get(key)??[]),p])}
  return [...grouped.values()]
 }
 products(model:ScopeModel,focus:string|null,metric:'click'|'purchase_feedback'){
  for(const tick of this.productXAxis.ticks){
   const x=-6.2+scalePosition(tick,this.productXAxis)*12.4
   this.mesh(x,2.58,-.5,.012,5.15,.012,'#e5eadf');this.label(x,-.52,0,tick.toLocaleString('zh-CN'),'axis')
  }
  for(let i=0;i<=5;i++){
   const y=i/5*5.15
   this.mesh(0,y,-.5,12.4,.012,.012,'#e5eadf');this.label(-7.0,y,-.5,axisPercent(this.productAxis.ticks[i]!),'axis')
  }
  this.label(-5.0,5.65,-.5,metric==='click'?'匹配点击占比 ↑':'购买反馈占比 ↑','axis-title');this.label(4.6,-.96,0,'曝光配对数（条）→','axis-title')
  for(const members of this.groups(model,metric)){
   const p=members.find(p=>p.id===focus)??members[0],v=(metric==='click'?p.click_rate:p.purchase_rate)!,x=-6.2+scalePosition(p.E,this.productXAxis)*12.4,y=v/this.productAxis.max*5.15
   if(y>0)this.mesh(x,y/2,0,.016,y,.016,'#d4dece')
   const sphere=new THREE.Mesh(this.sphere,this.material(p.color??model.categories.find(c=>c.id===p.displayCategoryId)?.color??'#a3ada6'));sphere.position.set(x,y,0);sphere.castShadow=true;sphere.userData.id='item:'+p.id;this.data.add(sphere)
   if(p.id===focus){const ring=new THREE.Mesh(new THREE.RingGeometry(.2,.235,32),new THREE.MeshBasicMaterial({color:'#193e37',side:THREE.DoubleSide}));ring.position.set(x,y,.19);this.data.add(ring)}
   const code=members.length>1?'×'+members.length:p.index.toString(36).toUpperCase().padStart(2,'0')
   this.label(x,y,0,code,'dot','item:'+p.id,undefined,p.title+'，曝光'+p.E+'条，'+(metric==='click'?'点击':'购买反馈')+'占比'+(v*100).toFixed(1)+'%'+(members.length>1?'，同坐标'+members.length+'件':''),members.map(p=>'item:'+p.id))
  }
  if(!model.products.length)this.label(0,2.5,0,'没有达到显示门槛的商品','empty')
 }
 compare(model:CompareModel,focus:string|null){
  const step=Math.min(2,14/Math.max(1,model.categories.length))
  model.categories.forEach((c,i)=>{const x=(i-(model.categories.length-1)/2)*step
   for(const [value,dx,color]of[[c.a,-.32,this.tint(c.color,.6)],[c.b,.32,c.color]] as [number|null,number,string][]){const h=(value??0)*5.2;if(h>0)this.mesh(x+dx,h/2,0,.46,h,.8,color,'cat:'+c.id)}
   const format=(v:number|null)=>v==null?'—':(100*v).toFixed(1)+'%'
   this.label(x,Math.max(c.a??0,c.b??0)*5.2+.43,0,format(c.a)+' / '+format(c.b),'compare-value','cat:'+c.id,c.textColor)
   this.label(x,-.02,1.35,c.name,'category','cat:'+c.id)
   if(c.id===focus)this.outline(x,0,1.25,1.2,'#193e37')
  })
  for(let i=0;i<=4;i++)this.label(-8.1,i*1.3,0,i*25+'%','axis')
  this.label(-6.0,5.9,0,'本组曝光配对占比','axis-title');this.label(0,-.02,2,'A 浅色 / B 原色 · 同一量尺','axis-title')
 }
 tint(hex:string,t:number){const color=new THREE.Color(hex);color.lerp(new THREE.Color('#fff'),t);return '#'+color.getHexString()}
 setCamera(preset:CameraPreset,animate=true){
  this.preset=preset;cancelAnimationFrame(this.frame)
  const offsets={overview:this.profile==='products'?new THREE.Vector3(0,1.7,16):new THREE.Vector3(2.8,6.4,12),front:new THREE.Vector3(0,.001,15),top:new THREE.Vector3(0,13,4)},end=this.target.clone().add(offsets[preset]),start=this.camera.position.clone()
  if(!animate||document.hidden||matchMedia('(prefers-reduced-motion: reduce)').matches){this.camera.position.copy(end);this.camera.lookAt(this.target);this.draw();return}
  const t0=performance.now(),tick=(t:number)=>{const k=Math.min(1,(t-t0)/420);this.camera.position.lerpVectors(start,end,1-(1-k)**3);this.camera.lookAt(this.target);this.draw();if(k<1)this.frame=requestAnimationFrame(tick)};this.frame=requestAnimationFrame(tick)
 }
 draw(){
  if(this.lost||document.hidden)return;const start=performance.now(),rect=this.host.getBoundingClientRect();if(!rect.width||!rect.height)return
  const aspect=rect.width/rect.height,v=(this.profile==='products'?Math.max(3.7,8.0/aspect):Math.max(5.9,9.2/aspect))/this.zoom;Object.assign(this.camera,{left:-v*aspect,right:v*aspect,top:v,bottom:-v})
  this.camera.updateProjectionMatrix();this.renderer.setSize(rect.width,rect.height,false);this.renderer.render(this.scene,this.camera)
  const labels:Label[]=this.points.map(p=>{const pos=p.position.clone().project(this.camera);return{id:p.id,text:p.text,x:(pos.x+1)*rect.width/2,y:(1-pos.y)*rect.height/2,kind:p.kind,color:p.color,aria:p.aria,members:p.members}})
  const dots=labels.filter((p):p is Label&{id:string;members:string[]}=>p.kind==='dot'&&!!p.id&&!!p.members)
  this.update([...labels.filter(p=>p.kind!=='dot'),...markerClusters(dots,this.productFocus).map(({anchor,members})=>({...anchor,members,text:members.length>1?'×'+members.length:anchor.text,kind:members.length>1?'dot cluster':'dot',aria:members.length>1?'展开邻近商品，共'+members.length+'件；各商品原始坐标保留':anchor.aria}))])
  this.frames.push(performance.now()-start);if(this.frames.length>90)this.frames.shift()
  if(!this.lowQuality&&this.frames.length>=15){const timings=this.frames.slice(5).sort((a,b)=>a-b);if(timings[Math.floor(timings.length/2)]!>18){this.lowQuality=true;this.renderer.setPixelRatio(1);this.renderer.shadowMap.enabled=false;for(const o of this.data.children)if(o instanceof THREE.Mesh)o.material instanceof THREE.Material&&(o.material.needsUpdate=true)}}
 }
 get info(){const gl=this.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return{engine:'Three.js '+THREE.REVISION,mode:this.lost?'context-lost':'WebGL2',quality:this.lowQuality?'light':'standard',renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),dpr:this.renderer.getPixelRatio(),memory:this.renderer.info.memory,models:this.models,search_axis:this.profile==='search'?this.categoryAxis:null,product_axis:this.profile==='products'?this.productAxis:null,product_x_axis:this.profile==='products'?this.productXAxis:null,draw_submission_ms:this.frames,objects:this.data.children.filter(o=>o.userData.id).map(o=>({id:o.userData.id,position:o.position.toArray(),scale:o.scale.toArray()}))}}
 dispose(){cancelAnimationFrame(this.frame);this.observer.disconnect();document.removeEventListener('visibilitychange',this.visibility);this.renderer.domElement.removeEventListener('click',this.onClick);this.renderer.domElement.removeEventListener('webglcontextlost',this.onLost);this.clear();for(const g of[this.box,this.sphere,this.ring,this.plane])g.dispose();this.renderer.dispose();this.renderer.domElement.remove()}
}

