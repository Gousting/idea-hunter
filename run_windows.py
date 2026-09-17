#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按时间窗输出「值得看的方向」Top10。

用法：
  python run_windows.py                       # 今天 / 本周 / 本月
  python run_windows.py --windows day,week    # 只跑指定窗口
  python run_windows.py --no-reddit           # 跳过 Reddit（省时间，Reddit 限流很紧）

设计取舍：
  · 不做持久化去重。本脚本定位是"随时跑一次看当下"，同一窗口重复跑应得到一致结果；
    持久化去重会让第二次跑出空结果（那是日更流水线 run.py 的做法，两者定位不同）。
  · 方向聚合用人工维护的关键词签名，不用无监督聚类 —— 几百条短文本上聚类产物不稳定，
    且方向名不可读；"独立开发者能做的方向"本身有限可枚举，签名匹配更可控可解释。
"""
import argparse
import glob as glob_mod
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hunter import sources, filter as flt, directions as dr, opencli as oc  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")

CFG = {"min_stars": 60, "min_text_len": 120}

# 窗口定义：每个信源如何表达"今天/本周/本月"
# 两处必须注意的实测约束：
#  1) min_stars 要随窗口缩放：`created:>1d stars:>60` 实测返回 0 条。
#  2) GitHub 的 created 是**日期粒度**且索引有延迟，窗口过短必然为空：
#     实测 created:>1天前 = 0 条，>2天前 = 31 条，>7天前 = 663 条。
#     所以"今日"窗口在 GitHub 侧用 3 天近似；真正的当日信号来自 Trending daily
#     （GitHub 自己按日计算的，粒度是小时级）。
WINDOWS = {
    "day":   {"label": "今日", "trending": "daily",   "days": 3,  "r": "hot",  "t": "",
              "min_stars": 15},
    "week":  {"label": "本周", "trending": "weekly",  "days": 7,  "r": "top",  "t": "week",
              "min_stars": 60},
    "month": {"label": "本月", "trending": "monthly", "days": 30, "r": "top",  "t": "month",
              "min_stars": 150},
}

HN_QUERIES = [
    "self-hosted too complex",
    "no web interface CLI only",
    "willing to pay tool",
    "why is there no tool for",
    "setup is a nightmare",
    "manually every time",
    "should just work",
]

REDDIT_SUBS = ["SaaS", "microsaas"]

# OpenCLI 通道（复用已登录 Chrome）用到的参数。
# reddit 适配器的 --time 支持 hour/day/week/month/year/all，所以三个窗口都能表达。
OPENCLI_SUBS = ["SaaS", "microsaas", "SideProject"]
OC_TOP_N = 3          # 每个子版块深读几帖（每帖一次浏览器调用，别调太高）
OC_SORT = {"今日": "hot", "本周": "top", "本月": "top"}
OC_TIME = {"今日": "", "本周": "week", "本月": "month"}
# Upwork 查询：找"正在出钱找人做"的事 —— 付费意愿最硬的证据。
UPWORK_QUERIES = ["automation script", "web scraping tool"]


def collect_window(w, args, health):
    raw = []
    # GitHub Trending
    try:
        rs, h = sources.github_trending(since=w["trending"], language=args.lang)
        raw += rs
        health.append({**h, "source": f"github_trending:{w['trending']}"})
    except Exception as e:
        health.append({"source": f"github_trending:{w['trending']}", "count": 0,
                       "ok": False, "note": str(e)[:80]})
    # GitHub Search：新建即起量
    try:
        rs, h = sources.github_search_new_rising(days=w["days"],
                                                 min_stars=w["min_stars"], per_page=50)
        raw += rs
        health.append({**h, "source": f"github_search:{w['days']}d"})
    except Exception as e:
        health.append({"source": f"github_search:{w['days']}d", "count": 0,
                       "ok": False, "note": str(e)[:80]})
    # HN
    try:
        rs, h = sources.hn_pain_points(HN_QUERIES, days=max(w["days"], 1))
        raw += rs
        health.append({**h, "source": f"hn:{w['days']}d"})
    except Exception as e:
        health.append({"source": f"hn:{w['days']}d", "count": 0, "ok": False,
                       "note": str(e)[:80]})
    # Reddit（走本地代理 + RSS）。启用 OpenCLI 时跳过：OpenCLI 能直接按时间窗
    # 抓 Reddit 且能拿评论，RSS 只是"能拿正文"的退路，同时跑纯属浪费（还占限流）。
    if not args.no_reddit and not args.opencli:
        try:
            rs, h = sources.reddit_rss(REDDIT_SUBS, sort=w["r"], window=w["t"], spacing=22)
            raw += rs
            health.append({**h, "source": f"reddit:{w['label']}"})
        except Exception as e:
            health.append({"source": f"reddit:{w['label']}", "count": 0, "ok": False,
                           "note": str(e)[:80]})
    # OpenCLI 通道：复用你已登录的 Chrome。
    # 它的 reddit 适配器支持 --sort/--time，所以**三个窗口都能直接表达**，
    # 而且能用 reddit read 拿到评论（RSS 拿不到的部分）。
    if args.opencli:
        oc_sources = []
        for sub in OPENCLI_SUBS:
            # 深读评论区：按评论数挑帖，而不是按赞数（赞多常是梗图帖）
            oc_sources.append((
                f"reddit:deep:r/{sub}",
                lambda s=sub: oc.reddit_deep(s, top_n=OC_TOP_N,
                                             sort=OC_SORT[w["label"]],
                                             time_filter=OC_TIME[w["label"]])))
        if w["label"] in ("今日", "本周") and not args.no_upwork:
            # Upwork 是"近期发布的活"，只对短窗口有意义
            for q in UPWORK_QUERIES:
                oc_sources.append((f"upwork:{q[:16]}",
                                   lambda qq=q: oc.upwork_search(qq, 30)))
        if w["label"] == "今日":
            oc_sources += [("producthunt:today", lambda: oc.producthunt_today()),
                           ("hn:show", lambda: oc.hackernews("show", 25)),
                           ("hn:ask", lambda: oc.hackernews("ask", 25))]
        for name, fn in oc_sources:
            try:
                rs, h = fn()
                raw += rs
                health.append(h)
            except Exception as e:
                health.append({"source": f"opencli:{name}", "count": 0, "ok": False,
                               "note": str(e)[:90]})
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default="day,week,month")
    ap.add_argument("--no-reddit", action="store_true")
    ap.add_argument("--opencli", action="store_true",
                    help="启用 OpenCLI 通道（复用已登录 Chrome；需 Chrome 打开）")
    ap.add_argument("--no-upwork", action="store_true",
                    help="跳过 Upwork（需在 Chrome 里登录过 upwork.com）")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-evidence", type=int, default=1,
                    help="进入榜单所需的最少证据数；默认 1（输出强度标注，不隐藏弱信号）")
    ap.add_argument("--from-cache", default="", nargs="?", const="latest",
                    help="复用已采集数据只重跑聚合（传路径或留空取最新）")
    ap.add_argument("--lang", default="")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    keys = [k.strip() for k in args.windows.split(",") if k.strip() in WINDOWS]
    results, health = {}, []
    t0 = time.time()
    cache = {}
    crowd_cache = {}  # 同方向跨窗口只查一次存量
    crowd_errs = []

    if args.from_cache:
        # 复用已采集数据，只重跑聚合 —— 调阈值/改分类时不必再等 6 分钟采集
        src = args.from_cache
        if src == "latest":
            cands = sorted(glob_mod.glob(os.path.join(OUT, "window_cache_*.json")))
            if not cands:
                print("未找到缓存文件")
                return 2
            src = cands[-1]
        with open(src, encoding="utf-8") as f:
            blob = json.load(f)
        print(f"从缓存重聚合：{src}")
        for k, v in blob.get("windows", {}).items():
            if k not in keys:
                continue
            kept = v.get("kept", [])
            stat = dr.aggregate(kept)
            rows = dr.top_directions(stat, n=args.top, min_evidence=args.min_evidence)
            done, errs = dr.attach_crowding(stat, rows, sources.github_count,
                                            cache=crowd_cache)
            crowd_errs += errs
            results[k] = {"label": v.get("label", k), "raw": v.get("raw", len(kept)),
                          "kept": len(kept), "stat": stat, "rows": rows}
            print(f"  [{v.get('label', k)}] {len(kept)} 条 → {len(rows)} 个方向"
                  f"（拥挤度已补 {done} 个）")
        health = blob.get("health", [])
    else:
        for k in keys:
            w = WINDOWS[k]
            print(f"\n[{w['label']}] 采集中 …")
            raw = collect_window(w, args, health)
            # 同一批内去重（不落库）
            seen, uniq = set(), []
            for r in raw:
                sid = r.get("source_id")
                if sid and sid in seen:
                    continue
                if sid:
                    seen.add(sid)
                uniq.append(r)
            kept, dropped = flt.rule_filter(uniq, CFG)
            stat = dr.aggregate(kept)
            rows = dr.top_directions(stat, n=args.top, min_evidence=args.min_evidence)
            done, errs = dr.attach_crowding(stat, rows, sources.github_count,
                                            cache=crowd_cache)
            crowd_errs += errs
            results[k] = {"label": w["label"], "raw": len(uniq), "kept": len(kept),
                          "stat": stat, "rows": rows}
            cache[k] = {"label": w["label"], "raw": len(uniq), "kept": kept}
            print(f"  {len(uniq)} 条 → 规则层 {len(kept)} 条 → {len(stat)} 个候选方向 "
                  f"→ 输出 {len(rows)} 个（拥挤度已补 {done} 个）")
        # 存原始数据，供后续快速重聚合
        ts_c = time.strftime("%Y%m%d-%H%M")
        cp = os.path.join(OUT, f"window_cache_{ts_c}.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "windows": cache, "health": health},
                      f, ensure_ascii=False, default=str)
        print(f"缓存 -> {cp}")

    for e in crowd_errs:
        health.append({"source": "github_count(拥挤度)", "count": 0, "ok": False, "note": e})

    ts = time.strftime("%Y%m%d-%H%M")
    rp = os.path.join(OUT, f"directions_{ts}.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(render(results, health, args))
    jp = os.path.join(OUT, f"directions_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "windows": {k: {"label": v["label"], "raw": v["raw"],
                                   "kept": v["kept"],
                                   "directions": [{kk: (sorted(vv) if isinstance(vv, set) else vv)
                                                   for kk, vv in s.items() if kk != "items"}
                                                  for s in v["rows"]]}
                               for k, v in results.items()},
                   "health": health}, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n耗时 {time.time() - t0:.0f}s\n报告 -> {rp}\nJSON -> {jp}")
    bad = [h for h in health if not h.get("ok")]
    for h in bad:
        print(f"  !! {h['source']}: {h.get('note')}")
    return 0


def render(results, health, args):
    L = ["# 值得看的方向 Top10 · 按时效性分层", "",
         f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}", "",
         "**判定口径**：把散点候选聚合成「方向」后按证据强度排序。",
         "证据数 = 该方向在本时间窗内的独立候选条数（同一候选只计入一个方向，避免重复计数）。", "",
         "**评分** = 证据数×1.0 + 信源多样性×0.8 + 付费信号×1.2 + 仓库热度×1.5 + 仓库数×0.4", "",
         "**强度**：≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。弱信号不等于没价值，"
         "但只有一条独立证据时不足以支撑判断 —— 它需要在下个窗口复现才算成立。", "",
         "---", ""]
    for k, v in results.items():
        L += [f"## {v['label']}", "",
              dr.render_window(v["label"], v["rows"], len(v["stat"]), v["raw"]),
              "", "---", ""]

    # 跨窗口对比：哪些方向在三个窗口都出现（= 持续需求，比一次性热点更值得看）
    if len(results) > 1:
        sets = {v["label"]: {s["name"] for s in v["rows"]} for v in results.values()}
        common = set.intersection(*sets.values()) if sets else set()
        L += ["## 跨窗口观察", ""]
        if common:
            L += [f"**三个窗口都出现（持续需求，优先看）**：{'、'.join(sorted(common))}", ""]
        for lab, names in sets.items():
            L.append(f"- {lab}：{len(names)} 个方向 —— {'、'.join(sorted(names)[:12])}")
        L += ["", "> 只在单一窗口出现的，多是短期热点或话题波动；"
                  "跨窗口反复出现的，才更接近可持续的需求。", ""]

    # 机会象限汇总：把各窗口里被标为「★ 值得看」的方向集中列出
    stars = {}
    for k, v in results.items():
        for s in v["rows"]:
            if str(s.get("opp_tag", "")).startswith("★"):
                e = stars.setdefault(s["name"], {"windows": [], "evidence": 0,
                                                 "market": s.get("market_repos")})
                e["windows"].append(v["label"])
                e["evidence"] += s["evidence"]
    L += ["## 机会象限汇总", ""]
    if stars:
        L += ["以下方向在对应窗口同时满足「高热度 + 低拥挤」，是当前最值得先看的一批：", ""]
        for name, e in sorted(stars.items(), key=lambda x: -x[1]["evidence"]):
            L.append(f"- **{name}**　证据 {e['evidence']} 条　存量项目 {e['market']}　"
                     f"出现于 {'、'.join(e['windows'])}")
        L += ["", "> 注意：这只说明「当前信号下相对不拥挤」，不代表验证过需求。"
                  "下一步仍是落地页/预售/冷启动外联的真实付费验证。"]
    else:
        L += ["_本轮没有方向同时满足「高热度 + 低拥挤」。"
              "头部方向都偏拥挤（红海），需要差异化切入，或等下个窗口复现后再看。_"]

    L += ["", "## 信源健康", "", "| 信源 | 条数 | 状态 | 备注 |", "|---|---:|---|---|"]
    for h in health:
        L.append(f"| {h['source']} | {h.get('count', 0)} | "
                 f"{'✅' if h.get('ok') else '❌'} | {h.get('note', '')} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
