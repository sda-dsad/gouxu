"""Bounded, process-local results for an immutable snapshot's SQL reads."""
from collections import OrderedDict
import copy
import json
import threading


class QueryResultCache:
    def __init__(self, entries=96, byte_budget=4 * 1024 * 1024, max_rows=200):
        self.entries = entries
        self.byte_budget = byte_budget
        self.max_rows = max_rows
        self._values = OrderedDict()
        self._pending = {}
        self._bytes = 0
        self._lock = threading.Lock()

    def get_or_compute(self, key, compute):
        while True:
            with self._lock:
                if key in self._values:
                    value, _ = self._values[key]
                    self._values.move_to_end(key)
                    return copy.deepcopy(value)
                event = self._pending.get(key)
                if event is None:
                    event = self._pending[key] = threading.Event()
                    break
            event.wait()
        try:
            value = compute()
            # Exports and large enumerations must never fill the result cache.
            size = len(json.dumps(value, ensure_ascii=False).encode('utf-8')) if len(value) <= self.max_rows else self.byte_budget + 1
            if size <= min(self.byte_budget, 512 * 1024):
                stored = copy.deepcopy(value)
                with self._lock:
                    while self._values and (len(self._values) >= self.entries or self._bytes + size > self.byte_budget):
                        _, (_, previous) = self._values.popitem(last=False)
                        self._bytes -= previous
                    if self.entries > 0:
                        self._values[key] = (stored, size)
                        self._bytes += size
            return value
        finally:
            with self._lock:
                self._pending.pop(key, None)
                event.set()
