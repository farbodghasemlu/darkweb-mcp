import copy
import json
import time
from collections import OrderedDict
class MemoryCache:
    def __init__(self, ttl: int, entries: int, max_bytes: int):
        self.ttl, self.entries, self.max_bytes, self.size = ttl, entries, max_bytes, 0
        self.items = OrderedDict()
    def _remove(self, key):
        self.size -= self.items.pop(key)[2]
    def get(self, key):
        if key not in self.items:
            return None
        expires, value, _ = self.items[key]
        if expires <= time.monotonic():
            self._remove(key)
            return None
        self.items.move_to_end(key)
        return copy.deepcopy(value)
    def put(self, key, value):
        if not self.ttl:
            return
        size = len(json.dumps(value, ensure_ascii=False).encode())
        if size > self.max_bytes:
            return
        for k in list(self.items):
            if self.items[k][0] <= time.monotonic() or k == key:
                self._remove(k)
        while self.items and (len(self.items) >= self.entries or self.size + size > self.max_bytes):
            self._remove(next(iter(self.items)))
        self.items[key] = (time.monotonic() + self.ttl, copy.deepcopy(value), size)
        self.size += size
    def clear(self):
        self.items.clear()
        self.size = 0
