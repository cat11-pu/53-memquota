"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/ops.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    puts = []
    for step in spec["ops"]:
        if step["op"] == "get":
            call("POST", base + "/get", json.dumps(step).encode())
        else:
            puts.append(parse(call("POST", base + "/put", json.dumps(step).encode())[1]))
    stats = parse(call("GET", base + "/")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("各次写入后的用量 =", [item.get("used") for item in puts])
    print("被拒绝的写入 =", stats.get("rejected"))
    print("回收的条数 =", stats.get("evicted"))
    print("最终各租户用量 =", stats.get("used"))
    print("配额 =", stats.get("tenant_quota"))
    print("回收水位比例 =", stats.get("low_ratio"))
    print("恢复后的用量 =", recovered.get("used"))
    print("恢复后的回收计数 =", recovered.get("evicted"))
    print("不变量（各租户用量不超配额） =", spec["quota_invariant"])
    print("租户数 =", spec["tenants"])
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
