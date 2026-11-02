"""Pure, dependency-free reference calculations; not a completed production backend."""
from __future__ import annotations
from collections import Counter
from typing import Any, Iterable

FIELDS = ('impressed_item_ids', 'clicked_item_ids', 'purchased_item_ids')


def id_string(value: Any) -> str:
    if isinstance(value, bool) or value is None or isinstance(value, (float, list, dict)):
        raise ValueError(f'Invalid identifier type: {type(value).__name__}')
    result = str(value).strip()
    if not result:
        raise ValueError('Empty identifier')
    return result


def id_set(values: Any) -> set[str]:
    """Two explicitly supported list encodings; unknown shapes fail closed."""
    if not isinstance(values, list):
        raise ValueError('Missing/null/non-list feedback is NOT an empty list')
    result = set()
    for value in values:
        if isinstance(value, dict):
            if set(value) != {'item_id'}:
                raise ValueError('Unknown nested item encoding')
            value = value['item_id']
        result.add(id_string(value))
    return result


def validate_request(row: dict) -> None:
    if not isinstance(row, dict) or not isinstance(row.get('query'), str):
        raise ValueError('query must be a string')
    for field in FIELDS:
        id_set(row.get(field))
    # Empty query is preserved and reported separately, not invented.


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def metrics(rows: Iterable[dict]) -> dict:
    """Units: deduplicated (source request row, item) pairs; not event hits/orders."""
    rows = list(rows)
    counts = Counter(requests=len(rows))
    queries: set[str] = set()
    products: set[str] = set()
    for row in rows:
        validate_request(row)
        queries.add(row['query'])
        i, c, p = (id_set(row[field]) for field in FIELDS)
        cm, pm = c & i, p & i
        products |= i | c | p
        counts.update(exposed_pairs=len(i), clicked_pairs=len(cm),
                      purchased_pairs=len(pm), clicked_requests=int(bool(cm)),
                      purchased_requests=int(bool(pm)),
                      orphan_click_pairs=len(c-i), orphan_purchase_pairs=len(p-i),
                      purchase_without_click_pairs=len(pm-cm),
                      exposed_without_click_pairs=len(i-cm),
                      triple_pairs=len(i & c & p), empty_exposure_requests=int(not i),
                      duplicate_list_entries=sum(len(row[f])-len(id_set(row[f])) for f in FIELDS),
                      empty_query_requests=int(not row['query'].strip()))
    out = dict(counts)
    for key in ('exposed_pairs','clicked_pairs','purchased_pairs','clicked_requests',
                'purchased_requests','orphan_click_pairs','orphan_purchase_pairs',
                'purchase_without_click_pairs','exposed_without_click_pairs',
                'triple_pairs','empty_exposure_requests','duplicate_list_entries','empty_query_requests'):
        out.setdefault(key, 0)
    out.update(unique_queries=len(queries), unique_items=len(products),
               pair_click_rate=ratio(out['clicked_pairs'],out['exposed_pairs']),
               pair_purchase_feedback_rate=ratio(out['purchased_pairs'],out['exposed_pairs']),
               request_click_rate=ratio(out['clicked_requests'],out['requests']),
               request_purchase_feedback_rate=ratio(out['purchased_requests'],out['requests']))
    return out


def by_item(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, Counter] = {}
    for row in rows:
        validate_request(row)
        i, c, p = (id_set(row[f]) for f in FIELDS)
        for item in i | c | p:
            out.setdefault(item, Counter()).update(exposed=int(item in i),
                clicked=int(item in i and item in c), purchased=int(item in i and item in p),
                orphan_click=int(item in c and item not in i),
                orphan_purchase=int(item in p and item not in i))
    return {k: {**dict(v), 'click_rate':ratio(v['clicked'],v['exposed']),
                'purchase_rate':ratio(v['purchased'],v['exposed'])} for k,v in out.items()}


def category_flows(rows: list[dict], items: list[dict]) -> dict:
    """A nonnegative cross-tab of query × L1 category, not a behavioral funnel."""
    lookup = {id_string(item['item_id']): item for item in items}
    flows = Counter()
    unknown = 0
    for row in rows:
        validate_request(row)
        for item_id in id_set(row['impressed_item_ids']):
            item = lookup.get(item_id)
            category = str(item.get('category_level1_id', 'UNKNOWN')) if item else 'UNKNOWN'
            if not item or category in ('UNKNOWN','None',''):
                category='UNKNOWN'; unknown += 1
            flows[(row['query'],category)] += 1
    total = sum(flows.values())
    return {'edges':[{'query':q,'category_id':c,'value':v} for (q,c),v in sorted(flows.items())],
            'total':total,'unknown_pairs':unknown,'metadata_coverage':ratio(total-unknown,total)}


def co_click(rows: list[dict], item_a: str, item_b: str) -> dict:
    """Same-request common click. Not co-purchase, not causal substitutability."""
    a=b=ab=0
    for row in rows:
        validate_request(row)
        clicked=id_set(row['clicked_item_ids']) & id_set(row['impressed_item_ids'])
        a+=item_a in clicked; b+=item_b in clicked; ab+=(item_a in clicked and item_b in clicked)
    return {'n_requests':len(rows),'a_requests':a,'b_requests':b,'both_requests':ab,
            'jaccard':ratio(ab,a+b-ab)}
