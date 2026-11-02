export async function request<T>(path:string,options:RequestInit={}):Promise<T>{
 const response=await fetch('/api/v1'+path,{credentials:'same-origin',...options,headers:{'x-gouxu-request':'1',...(options.body&&!(options.body instanceof FormData)?{'Content-Type':'application/json'}:{}),...options.headers}})
 if(!response.ok){let error;try{error=await response.json()}catch{};throw Error(error?.error?.message??'请求失败，请重试')}
 return response.json()
}
export const post=<T>(path:string,data:unknown,signal?:AbortSignal)=>request<T>(path,{method:'POST',body:JSON.stringify(data),signal})
export async function exportFile(body:unknown,onProgress:(text:string)=>void=()=>{}){
 const started=await post<{job_id:string}>('/exports',body)
 for(let n=0;n<180;n++){
  const job=await request<{state:string;progress:{rows?:number;download_url?:string};error_code?:string}>('/exports/'+started.job_id)
  if(job.state==='succeeded'&&job.progress.download_url){const a=document.createElement('a');a.href=job.progress.download_url;a.download='';a.click();return}
  if(job.state==='failed'||job.state==='cancelled')throw Error('导出未完成：'+(job.error_code??job.state))
  onProgress(job.progress.rows!=null?'正在生成 '+job.progress.rows+' 行…':'正在生成导出文件…')
  await new Promise(r=>setTimeout(r,350))
 }
 throw Error('导出仍在处理，请稍后重试')
}
