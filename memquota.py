"""memquota.py：租户配额（按租户记账、过期+LRU 回收、准入拒绝、快照恢复）。"""
from __future__ import annotations

import heapq
import json
import os
from collections import OrderedDict

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memquota_snapshot.json")


class Quota:
    def __init__(self, tenant_quota: int = 100, low_ratio: float = 0.5):
        self.tenant_quota = tenant_quota
        self.low_ratio = low_ratio
        self.tenants = {}
        self.rejected = 0
        self.evicted = 0
        self.clock = 0

    def _tenant(self, name: str, create: bool = False) -> dict:
        state = self.tenants.get(name)
        if state is None and create:
            state = {"used": 0, "items": {}, "lru": OrderedDict(), "expiry": []}
            self.tenants[name] = state
        return state

    def _drop_if_empty(self, name: str) -> None:
        state = self.tenants.get(name)
        if state is not None and not state["items"]:
            del self.tenants[name]

    def _remove(self, name: str, key: str) -> dict:
        state = self.tenants[name]
        entry = state["items"].pop(key)
        state["lru"].pop(key, None)
        state["used"] -= entry["size"]
        self._drop_if_empty(name)
        return entry

    def _reclaim(self, name: str, now: int) -> int:
        """先回收过期项，再按最久未访问回收，直到用量低于低水位。返回回收条数。"""
        state = self.tenants.get(name)
        if state is None:
            return 0
        target = self.low_ratio * self.tenant_quota
        count = 0
        heap = state["expiry"]
        while heap and heap[0][0] <= now:
            expire_at, _, key = heapq.heappop(heap)
            entry = state["items"].get(key)
            if entry is None or entry["expire_at"] != expire_at:
                continue
            self._remove(name, key)
            count += 1
            state = self.tenants.get(name)
            if state is None:
                return count
        while state["used"] >= target and state["lru"]:
            self._remove(name, next(iter(state["lru"])))
            count += 1
            state = self.tenants.get(name)
            if state is None:
                break
        return count

    def put(self, tenant: str, key: str, size: int, expire_at: int = None) -> dict:
        self.clock += 1
        state = self._tenant(tenant, create=True)
        if key in state["items"]:
            self._remove(tenant, key)
            state = self._tenant(tenant, create=True)
        if state["used"] + size > self.tenant_quota:
            self.evicted += self._reclaim(tenant, self.clock)
            state = self._tenant(tenant, create=True)
        if state["used"] + size > self.tenant_quota:
            self.rejected += 1
            self._drop_if_empty(tenant)
            return {"used": state["used"], "rejected": True}
        state["items"][key] = {"size": size, "used_at": self.clock, "expire_at": expire_at}
        state["lru"][key] = None
        if expire_at is not None:
            heapq.heappush(state["expiry"], (expire_at, self.clock, key))
        state["used"] += size
        return {"used": state["used"]}

    def get(self, tenant: str, key: str, at: int = None) -> dict:
        self.clock += 1
        state = self.tenants.get(tenant)
        if state is None or key not in state["items"]:
            return {"found": False}
        entry = state["items"][key]
        entry["used_at"] = self.clock
        state["lru"].move_to_end(key)
        return {"found": True, "size": entry["size"]}

    def evict(self, tenant: str, now: int = 0) -> dict:
        count = self._reclaim(tenant, now)
        self.evicted += count
        state = self.tenants.get(tenant)
        return {"evicted": count, "used": state["used"] if state else 0}

    def persist(self) -> str:
        blob = json.dumps({
            "tenant_quota": self.tenant_quota,
            "low_ratio": self.low_ratio,
            "rejected": self.rejected,
            "evicted": self.evicted,
            "clock": self.clock,
            "tenants": {
                name: {"used": state["used"], "items": state["items"]}
                for name, state in self.tenants.items()
            },
        })
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as handle:
            handle.write(blob)
        return blob

    def restore(self, blob: str) -> dict:
        data = json.loads(blob)
        self.tenant_quota = data["tenant_quota"]
        self.low_ratio = data["low_ratio"]
        self.rejected = data["rejected"]
        self.evicted = data["evicted"]
        self.clock = data["clock"]
        self.tenants = {}
        for name, saved in data["tenants"].items():
            state = {"used": saved["used"], "items": dict(saved["items"]),
                     "lru": OrderedDict(), "expiry": []}
            for key in sorted(state["items"], key=lambda k: state["items"][k]["used_at"]):
                state["lru"][key] = None
            for key, entry in state["items"].items():
                if entry["expire_at"] is not None:
                    heapq.heappush(state["expiry"], (entry["expire_at"], entry["used_at"], key))
            self.tenants[name] = state
        return self.stats()

    def recover(self) -> dict:
        self.restore(self.persist())
        return self.stats()

    def stats(self) -> dict:
        return {"used": {name: state["used"] for name, state in self.tenants.items()},
                "rejected": self.rejected, "evicted": self.evicted,
                "tenant_quota": self.tenant_quota, "low_ratio": self.low_ratio,
                "items": sum(len(state["items"]) for state in self.tenants.values())}
