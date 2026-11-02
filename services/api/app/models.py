from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

class StrictModel(BaseModel):model_config=ConfigDict(extra='forbid')
class ScopeInput(StrictModel):
    snapshot_id:str=Field(min_length=1,max_length=100)
    exact_query_keys:list[str]=Field(default_factory=list,max_length=20)
    split_policy:list[str]=Field(default_factory=list,max_length=20)
class CohortInput(StrictModel):
    scope_id:str=Field(min_length=1,max_length=100)
    name:str=Field(min_length=1,max_length=80)
class CompareInput(StrictModel):
    cohort_a:str
    cohort_b:str
class ReviewInput(StrictModel):
    scope_id:str
    target_type:Literal['query','item','compare']
    target_id:str=Field(min_length=1,max_length=300)
    name:str=Field(min_length=1,max_length=400)
    note:str=Field(default='',max_length=2000)
class ReviewUpdate(StrictModel):
    expected_version:int=Field(ge=1)
    note:str=Field(max_length=2000)
    status:Literal['pending','reviewed']
class ImportInput(StrictModel):
    registered_file_ids:list[str]=Field(min_length=1,max_length=1)
    adapter_id:Literal['normalized-v1']='normalized-v1'
    consent_metadata:dict[str,bool]=Field(default_factory=dict)
class ExportInput(StrictModel):
    scope_id:str|None=None
    cohort_a:str|None=None
    cohort_b:str|None=None
    format:Literal['json','csv']='json'
    target:Literal['scope','review','compare','evidence']='scope'
    item_id:str|None=Field(default=None,max_length=200)
    category_id:str|None=Field(default=None,max_length=200)
