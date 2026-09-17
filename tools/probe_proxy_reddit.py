# -*- coding: utf-8 -*-
"""
探测：Reddit 在哪些代理节点下可达。

背景：Reddit 会封机房/VPN IP 段。当前节点出口 67.159.48.xxx（已脱敏）（新加坡 FDCservers，
hosting:true proxy:true）被判定为 Blocked。所以逐个换节点实测。

安全设计：
  - 会先记录当前选中节点，测完无条件恢复
  - 不打印 secret
  - 单节点请求超时 12s，总耗时可控
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CTRL = "http://127.0.0.1:9097"
PROXY = "http://127.0.0.1:7897"
REDDIT = "https://old.reddit.com/r/SaaS/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

# 优先测试"更像住宅"的节点：家宽/原生/住宅/IEPL/专线
PREFER = re.compile(r"(家宽|住宅|原生|IEPL|IPLC|专线|Premium|Residential)", re.I)


def find_secret():
    base = os.path.join(os.environ["APPDATA"],
                        "io.github.clash-verge-rev.clash-verge-rev")
    for fn in ("clash-verge.yaml", "config.yaml"):
        p = os.path.join(base, fn)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            m = re.search(r'^\s*secret:\s*"?([^"\s]+)', f.read(), re.M)
            if m:
                return m.group(1)
    raise SystemExit("未找到 Clash secret")


def api(secret, path, method="GET", body=None):
    req = urllib.request.Request(
        CTRL + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {secret}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip() else {}


def test_reddit():
    op = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
    req = urllib.request.Request(REDDIT, headers={"User-Agent": UA})
    try:
        with op.open(req, timeout=14) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        code = e.code
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:60]}"
    title = ""
    m = re.search(r"<title>([^<]*)", body)
    if m:
        title = m.group(1).strip()
    if code == 200 and "Blocked" not in title and len(body) > 5000:
        return 200, f"OK title={title[:50]} len={len(body)}"
    return code, f"title={title[:40]} len={len(body)}"


def main():
    secret = find_secret()
    allp = api(secret, "/proxies").get("proxies", {})
    groups = {k: v for k, v in allp.items()
              if v.get("type") in ("Selector", "URLTest")}
    gname = next((g for g in ("🚀节点选择", "🐟漏网之鱼", "GLOBAL") if g in groups), None)
    if not gname:
        raise SystemExit(f"未找到可用选择器组，已有：{list(groups)}")
    g = groups[gname]
    original = g.get("now")
    nodes = g.get("all", [])
    print(f"使用组：{gname}　当前节点：{original}　可选 {len(nodes)} 个\n")

    preferred = [n for n in nodes if PREFER.search(n)]
    others = [n for n in nodes if n not in preferred]
    candidates = (preferred[:6] + others[:8])[:14]

    results = []
    try:
        for n in candidates:
            try:
                api(secret, f"/proxies/{urllib.parse.quote(gname)}",
                    "PUT", {"name": n})
                time.sleep(1.6)
                code, info = test_reddit()
                ok = "✅" if code == 200 else "❌"
                print(f"{ok} {n[:44]:<46} {code}　{info}")
                results.append((n, code))
            except Exception as e:
                print(f"⚠️ {n[:44]:<46} 切换失败 {type(e).__name__}")
    finally:
        if original:
            api(secret, f"/proxies/{urllib.parse.quote(gname)}", "PUT",
                {"name": original})
            time.sleep(1)
            print(f"\n已恢复原节点：{original}")

    good = [n for n, c in results if c == 200]
    print(f"\n可用节点 {len(good)}/{len(results)}")
    for n in good:
        print("  ✓", n)


if __name__ == "__main__":
    main()
