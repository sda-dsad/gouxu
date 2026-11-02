"""HTTP checks against the explicit synthetic fixture; never select real snapshots."""
import argparse, http.cookiejar, json, urllib.request

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', default='http://localhost:8080')
    base = p.parse_args().base_url.rstrip('/')
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def get(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(base + path, data=data,
            headers={'Content-Type': 'application/json', 'x-gouxu-request': '1'})
        with opener.open(req, timeout=30) as response:
            return json.load(response)
    assert get('/healthz')['status'] == 'ok'
    demo = next(s for s in get('/api/v1/snapshots')['snapshots']
                if s['data_mode'] == 'synthetic' and s['counts']['requests'] == 336)
    model = get('/api/v1/scopes', {'snapshot_id': demo['snapshot_id']})
    assert (model['requests'], model['E'], model['C'], model['P']) == (336, 1722, 533, 118)
    assert sum(c['E'] for c in model['categories']) == model['E']
    rows = get('/api/v1/scopes/' + model['scope_id'] + '/items?limit=200')['items']
    assert len(rows) == 28 and sum(r['E'] for r in rows) == 1722
    assert sum(r['C'] for r in rows) == 533 and sum(r['P'] for r in rows) == 118
    print('PASS: synthetic HTTP health, snapshot, scope and category/product conservation')

if __name__ == '__main__':
    main()
