import concurrent.futures
import sys
import threading
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.query_cache import QueryResultCache


class QueryCacheTests(unittest.TestCase):
    def test_callers_cannot_mutate_cached_rows_and_parameters_are_distinct(self):
        cache = QueryResultCache()
        calls = []
        def run(key):
            return cache.get_or_compute(key, lambda: calls.append(key) or [{'E': 9, 'ids': ['a']}])
        first = run(('sql', ('scope-a',)))
        first[0]['E'] = 1
        first[0]['ids'].append('b')
        self.assertEqual(run(('sql', ('scope-a',))), [{'E': 9, 'ids': ['a']}])
        run(('sql', ('scope-b',)))
        self.assertEqual(len(calls), 2)

    def test_same_query_in_flight_is_computed_once(self):
        cache = QueryResultCache()
        entered, release = threading.Event(), threading.Event()
        calls = []
        def compute():
            calls.append(1)
            entered.set()
            if not release.wait(3):
                raise TimeoutError('test did not release query')
            return [{'E': 14}]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [pool.submit(cache.get_or_compute, 'same', compute) for _ in range(4)]
            self.assertTrue(entered.wait(3))
            release.set()
            self.assertEqual([j.result(timeout=3) for j in jobs], [[{'E': 14}]] * 4)
        self.assertEqual(len(calls), 1)

    def test_failed_query_can_retry(self):
        cache = QueryResultCache()
        def bad():
            raise ValueError('query failed')
        with self.assertRaises(ValueError):
            cache.get_or_compute('key', bad)
        self.assertEqual(cache.get_or_compute('key', lambda: [{'E': 2}]), [{'E': 2}])

    def test_entry_and_byte_limits_evict_and_large_results_are_not_retained(self):
        cache = QueryResultCache(entries=2, byte_budget=100, max_rows=2)
        calls = []
        def run(key, value):
            return cache.get_or_compute(key, lambda: calls.append(key) or value)
        for key in ['a', 'b', 'c']:
            run(key, [{'n': 1}])
        run('a', [{'n': 1}])
        self.assertEqual(calls.count('a'), 2)
        for value in [[{}, {}, {}], [{'text': 'x' * 101}]]:
            before = len(calls)
            run('large', value)
            run('large', value)
            self.assertEqual(len(calls), before + 2)
        self.assertLessEqual(cache._bytes, 100)
        self.assertLessEqual(len(cache._values), 2)

    def test_snapshot_instances_never_share_results(self):
        first, second = QueryResultCache(), QueryResultCache()
        self.assertEqual(first.get_or_compute('same SQL', lambda: [{'E': 1}]), [{'E': 1}])
        self.assertEqual(second.get_or_compute('same SQL', lambda: [{'E': 7}]), [{'E': 7}])
