export type DataMode='synthetic'|'public_real_subset'|'authorized_private'
export type CameraPreset='overview'|'front'|'top'
export type View='search'|'flow'|'structure'|'products'|'priority'|'compare'
export interface Category{id:string;name:string;color:string;textColor:string;E:number;C:number;P:number}
export interface Product{id:string;title:string;categoryId:string;categoryName?:string;displayCategoryId?:string;color?:string;textColor?:string;E:number;C:number;P:number;index:number;click_rate?:number|null;purchase_rate?:number|null}
export interface ScopeModel{
 snapshot_id:string;scope_id:string;metric_version:string;data_mode:DataMode;exact_queries:string[];split_policy:string[];requests:number;E:number;C:number;P:number;orphanC:number;orphanP:number;purchaseWithoutClick:number;categories:Category[];products:Product[];other_categories?:{id:string;name:string;E:number}[];scale_spec:{search_max:number;item_max:number};coverage:{metadata_pairs:number|null};metrics?:{pair_click_rate:number|null;pair_purchase_feedback_rate:number|null}
}
export interface QueryEntry{query:string;requests:number;key:string;E?:number}
export interface SnapshotIndex{
 snapshot_id:string;data_mode:DataMode;metric_version:string;title:string;queries:QueryEntry[];splits?:string[];
 source:{revision?:string;license_status:string;window:string;hashes?:Record<string,string>;sampling?:{unit?:string;percent?:number}};counts:{requests:number;items:number;queries:number};quality:Record<string,unknown>
}
export interface CompareModel{
 snapshot_id:string;scope_id:string;metric_version:string;data_mode:DataMode;
 a:{cohort:{cohort_id:string;name:string;scope_id:string};model:ScopeModel};
 b:{cohort:{cohort_id:string;name:string;scope_id:string};model:ScopeModel};
 categories:(Category&{a:number|null;b:number|null;aE:number;bE:number})[];
 click_delta_pp:number|null;purchase_delta_pp:number|null;overlap_requests:number
}
export interface Review{id:string;scope_id:string;snapshot_id:string;metric_version:string;target_type:'query'|'item'|'compare';target_id:string;name:string;note:string;status:'pending'|'reviewed';version:number;created_at:string;updated_at:string}
export interface Evidence{snapshot_id:string;data_mode:DataMode;metric_version:string;records:{request_id:string;query:string;split:string;source_file:string|null;source_line:number|null;source_sha256:string;time_index:string|null;impressed_item_ids:string[];clicked_item_ids:string[];purchased_item_ids:string[]}[];total:number;cursor:number;next_cursor:number|null;note:string}
export const ratio=(n:number,d:number):number|null=>d===0?null:n/d
export const number=(n:number|null|undefined)=>n==null?'—':n.toLocaleString('zh-CN')
export const percent=(n:number|null|undefined)=>n==null?'—':(100*n).toFixed(1)+'%'
export const rate=(p:{E:number;C:number;P:number},metric:'click'|'purchase_feedback')=>ratio(metric==='click'?p.C:p.P,p.E)
export const delta=(v:number|null)=>v==null?'—':(v>0?'+':'')+v.toFixed(1)

