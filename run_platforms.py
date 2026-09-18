#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""平台优先报告：抓各平台的热榜，按平台组织，再跨平台汇总。

与 run_windows.py 的分工（这是两件事，别混）：
  run_windows.py   —— 需求轨道：过需求门槛 → 归到 28 类方向 → 输出"该看哪个方向"
  run_platforms.py —— 热点轨道：不做门槛、不做归类 → 输出"各平台在热什么"

用法：
  python run_platforms.py              # 各平台热榜（快，约 3-5 分钟）
  python run_platforms.py --deep       # 再深读评论区（慢，+6-10 分钟）
  python run_platforms.py --limit 8    # 每平台取前 8 条
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "out")

from hunter import sources, opencli as oc, platforms as pf  # noqa: E402

SO_TAGS = ["automation", "api"]
REDDIT_SUBS = ["SaaS", "microsaas", "SideProject"]
DEVTO_TAGS = ["webdev"]


def collect_hot(limit=6, health=None):
    """只抓各平台的'热榜'类接口 —— 不做需求门槛，全量保留。"""
    raw = []
    H = health if health is not None else []

    def add(name, fn, deep=False):
        """deep=True 的源只在 --deep 时取（耗时）。"""
        try:
            rs, h = fn()
            raw.extend(rs or [])
            H.append({"source": h.get("source", name), "count": h.get("count", len(rs or [])),
                      "ok": h.get("ok", True), "note": (h.get("note") or "")[:90]})
        except Exception as e:
            H.append({"source": name, "count": 0, "ok": False, "note": str(e)[:90]})

    # GitHub
    add("github_trending:daily", lambda: sources.github_trending(since="daily"))
    add("github_search:3d", lambda: sources.github_search_new_rising(days=3, min_stars=15,
                                                                    per_page=50))
    # 公共热榜（无需登录）
    add("opencli:hn:show", lambda: oc.hackernews("show", 25))
    add("opencli:hn:ask", lambda: oc.hackernews("ask", 25))
    add("opencli:producthunt", lambda: oc.producthunt_today())
    add("opencli:lobsters", lambda: _raw_norm("lobsters", ["lobsters", "hot", "--limit", "25"], "hot"))
    add("opencli:devto", lambda: _raw_norm("devto", ["devto", "top", "--limit", "25"], "top"))
    add("opencli:lesswrong", lambda: oc.lesswrong_top(20))
    # 两个免登录弱等效热榜（P0-3 接入）：掘金=中文技术热榜，
    # bluesky=社交热门话题（实测偏新闻，如实标注"弱等效"）
    add("opencli:juejin:hot", lambda: _juejin_hot())
    add("opencli:bluesky:trending", lambda: sources.bluesky_trending(20))
    for t in SO_TAGS:
        add(f"opencli:stackoverflow#{t}",
            lambda tt=t: oc.stackoverflow_tag(tt, 20))
    # 需登录（未登录会给出明确 AUTH_REQUIRED，不静默）
    add("opencli:reddit", lambda: _raw_norm("reddit", ["reddit", "subreddit", "SaaS",
                                                      "--sort", "hot", "--limit", "25"], "SaaS"))
    add("opencli:zhihu", lambda: oc.zhihu_hot(20))
    add("opencli:indeed", lambda: oc.indeed_search("automation"))
    return raw


def _juejin_hot():
    """掘金热榜：原生热度=浏览+点赞×3，需自行折算进 heat.score（否则热度为 0）。"""
    d, m = oc.run(["juejin", "hot", "--limit", "25"], timeout=120)
    rows = oc._rows(d)
    out = []
    for r in rows:
        rec = oc._norm("juejin", r, "juejin:hot")
        h = rec.get("heat") or {}
        h["score"] = int(h.get("views") or 0) + int(h.get("votes") or 0) * 3
        rec["heat"] = h
        out.append(rec)
    return out, {"source": "opencli:juejin:hot", "count": len(rows), "ok": m["ok"],
                 "note": "免登录弱等效（中文技术热榜）"}


def _raw_norm(src, argv, site):
    d, m = oc.run(argv)
    rows = oc._rows(d)
    return [oc._norm(src, r, site) for r in rows], \
        {"source": f"opencli:{src}:{site}", "count": len(rows), "ok": m["ok"],
         "note": m["note"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15,
                    help="每平台取前 N 条（跨平台词频交叉需要足够样本，"
                         "实测 6 条时全库无一个跨平台词）")
    ap.add_argument("--deep", action="store_true", help="额外深读评论区（慢）")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    health = []
    print("采集各平台热榜 …")
    raw = collect_hot(args.limit, health)

    if args.deep:
        print("深读评论区 …")
        for name, fn in [("hn:deep:show", lambda: oc.hackernews_deep("show", 2)),
                         ("lobsters:deep", lambda: oc.lobsters_deep(2)),
                         ("so:deep", lambda: oc.stackoverflow_deep("automation", 2))]:
            try:
                rs, h = fn()
                raw.extend(rs or [])
                health.append({"source": h["source"], "count": h["count"],
                               "ok": h["ok"], "note": (h.get("note") or "")[:90]})
            except Exception as e:
                health.append({"source": name, "count": 0, "ok": False, "note": str(e)[:90]})

    # 按平台热度排序取头部
    hot = pf.hot_by_platform(raw, per_platform=args.limit)
    terms = pf.platform_terms(hot)
    topics = pf.cross_topics(hot)

    print()
    for src, items in hot:
        top = items[0] if items else None
        print(f"  {src:<26} {len(items):>2} 条  热度最高 "
              f"{(top['_heat'] if top else 0):>6}  {(top.get('title') or '')[:40] if top else ''}")
    print("\n各平台高频词：")
    for src, _ in hot[:6]:
        print(f"  {src:<22} " + "、".join(f"{t}({n})" for t, n in terms.get(src, [])[:5]))
    print("\n跨平台主题（≥2 平台）："
          + ("、".join(t["topic"] for t in topics[:8]) if topics else "无（样本量不足，见报告说明）"))

    ts = time.strftime("%Y%m%d-%H%M")
    md = pf.render_markdown(hot, topics, "各平台热榜", len(raw), terms)
    mp = os.path.join(OUT, f"platforms_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write(md)

    data = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "collected": len(raw),
            "terms": {k: [{"t": t, "n": n} for t, n in v] for k, v in terms.items()},
            "platforms": [{"source": s, "items": [
                {"title": (r.get("title") or "")[:160], "url": r.get("url", ""),
                 "heat": r["_heat"], "source": r.get("source")}
                for r in items]} for s, items in hot],
            "topics": topics, "health": health}
    jp = os.path.join(OUT, f"platforms_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"\n耗时 {int(time.time() - t0)}s")
    print("报告 ->", mp)
    print("JSON ->", jp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
