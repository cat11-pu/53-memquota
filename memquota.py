"""memquota.py：租户配额（基线：全局计数、不回收、不拒绝）。"""
from __future__ import annotations


class Quota:
    def __init__(self, tenant_quota: int = 100, low_ratio: float = 0.5):
        self.tenant_quota = tenant_quota
        self.low_ratio = low_ratio
        self.items = {}
        self.used = {}
        self.rejected = 0
        self.evicted = 0
        self.clock = 0

    def put(self, tenant: str, key: str, size: int, expire_at: int = None) -> dict:
        """基线：只看全局，不按租户也不回收。"""
        self.clock += 1
        self.items[(tenant, key)] = {"size": size, "used_at": self.clock, "expire_at": expire_at}
        self.used[tenant] = self.used.get(tenant, 0) + size
        return {"used": self.used[tenant]}

    def get(self, tenant: str, key: str, at: int = None) -> dict:
        self.clock += 1
        entry = self.items.get((tenant, key))
        if entry is None:
            return {"found": False}
        entry["used_at"] = self.clock
        return {"found": True, "size": entry["size"]}

    def evict(self, tenant: str, now: int = 0) -> dict:
        raise NotImplementedError("回收还没实现")

    def recover(self) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"used": dict(self.used), "rejected": self.rejected, "evicted": self.evicted,
                "tenant_quota": self.tenant_quota, "low_ratio": self.low_ratio,
                "items": len(self.items)}
