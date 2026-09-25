# memquota

纯 Python 标准库的本机服务。

## 起服务

    python3 server.py 8000

浏览器打开 http://127.0.0.1:8000/ 看结果。

## 测试

    python3 -m unittest discover -s tests -v

## 行为

- `put(tenant, key, size, expire_at)` 按租户记账；`get` 更新最后访问时间。
- 写入前若该租户用量加上本次大小超过 `tenant_quota`，先回收再试；仍超额则拒绝（计入 `rejected`，用量不变）。
- 回收顺序：先过期项（`expire_at <= now`），再按最久未访问；回收到用量低于 `low_ratio × 配额` 为止，条数计入 `evicted`。
- `evict(tenant, now)` 手动触发一次回收，返回回收条数与回收后用量。
- `persist()` 落盘快照，`restore(blob)` / `/recover` 恢复用量、回收计数与访问时间。

## 验收自检

    python3 check_http.py
