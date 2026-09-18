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

from hunter import (sources, filter as flt, directions as dr, opencli as oc, llm,  # noqa: E402
                    advice, paths, validate as vd, resilience as rz)

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

# 第二批 opencli 适配器（2026-09-17）。
# 公开源挂今日窗口（热门问题/文章是"当下"）；需要登录的挂今日+本周，频率刻意压低。
SO_TAGS = ["api", "automation"]            # SO 热门问题 = 未满足需求
LB_TAGS = ["ai", "devops"]                 # lobsters 标签
DT_TAGS = ["webdev", "ai"]                 # DEV.to 标签
INDEED_QUERIES = ["automation", "data scraping"]   # 招聘 = 企业付费意愿
TW_QUERIES = ['"is there a tool" lang:en -filter:replies']   # X 原生操作符透传
XHS_QUERIES = ["效率工具", "自动化办公"]     # 小红书搜索词


def _native_fails(health):
    """本批采集里失败的原生榜源（用于并排展示原生率，避免误读为口径退化）。"""
    NATIVE_KEYS = ("github_trending", "github_search", "lobsters", "devto",
                   "lesswrong", "stackoverflow", "producthunt", "reddit")
    out, seen = [], set()
    for h in health:
        if h.get("ok") or h.get("skipped"):
            continue
        src = h.get("source", "")
        if any(k in src for k in NATIVE_KEYS):
            b = src.split("[")[0]
            if b not in seen:
                seen.add(b)
                out.append(b)
    return out


# ---------------------------------------------------------------- 判定方式声明
# 判定方式必须按**实际命中率**标注，不能只看"有没有传 --annotations"。
# 2026-09-18 修复：原实现是
#     if args.annotations: classify_mode = "agent-语义分类（Claude 直读原文）"
# 与命中数完全脱钩 —— 传一个空的 {} 也会声称用了语义分类，而榜单实际 100% 来自
# 关键词签名。同时 apply_annotations() 返回的 hit 计数被直接丢弃，覆盖率无人知晓。
#
# 实现已抽到 hunter/mode.py：这份口径**报告与看板必须共用**。
# 此前两处各写一份，直接导致同一次运行的两份产出互相矛盾
# （看板说"关键词签名（含部分 agent 语义标注）"、报告说"agent-语义分类"）。
# 第一次修复时我只是把逻辑从看板搬进报告 —— 那仍然是一式两份，边界很快又分叉：
# 报告修好了"零命中要说过期"，看板仍在 0% 覆盖时说"含部分语义标注"。
# 教训：诚实性逻辑必须共享同一份代码，不能各写一份看起来一样的实现。
from hunter.mode import (SEMANTIC_MODES, MODE_AGENT, MODE_PARTIAL,  # noqa: E402
                         is_semantic as _is_semantic,
                         classify_mode as _classify_mode,
                         coverage_line as _coverage_line)


def _evidence_composition(rows):
    """算「本窗口第一名」的证据构成 —— 替代原先写死的那段口径警告。

    2026-09-18 修复：原实现在 run_windows.py 里硬编码了一段
    "本周榜第一的「8 条证据」实际 = 4 条 HN 评论 + 2 个 GitHub 仓库 + 1 个 Trending
    + 1 个 Reddit 帖"。它与本轮数据无关：只跑今日窗口时，报告照样输出这句。
    一份以"口径诚实"为卖点的报告，最显眼的那句诚实声明是写死的，比不写更糟。
    """
    if not rows:
        return None
    s = rows[0]
    cnt = {}
    for r in s.get("items", []):
        src = r.get("source") or "?"
        cnt[src] = cnt.get(src, 0) + 1
    shown = sum(cnt.values())
    total = s.get("evidence", 0) + s.get("hot", 0)
    parts = "、".join(f"{v} 条 {k}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1]))
    return {"name": s["name"], "evidence": s.get("evidence", 0),
            "hot": s.get("hot", 0), "total": total, "parts": parts,
            "truncated": shown < total}


def _native_breakdown_md(rows, undecl):
    """原生率的信源明细（折叠）—— 头条验收指标必须能被读者按信源审计。

    2026-09-18 新增：原先只给一个百分数。而"原生榜"这个身份此前是由 paths.infer()
    的默认值发放的（默认返回 PLATFORM），新信源忘了声明 path 就白拿原生身份，
    等于指标可以自证达标。现在默认取保守侧，并在这里把构成摊开：
    读者能一眼看到 74% 是哪些源撑起来的、其中多少是"弱原生"。
    """
    if not rows:
        return ""
    L = ["<details><summary>原生率的信源明细（点击展开审计）</summary>", "",
         "| 信源 | 原生榜 | 其中弱原生 | 关键词检索 |", "|---|---:|---:|---:|"]
    for b in rows:
        L.append(f"| {b['source']} | {b['native']} | {b['weak']} | {b['keyword']} |")
    L += ["", "> **弱原生** = 排序由平台给，但**入池门槛或榜单范围由作者设定**"
              "（github_search 的 created/stars 门槛、reddit 的子版块清单、"
              "browser 的站点清单）。它们比 GitHub Trending 这类纯算法榜弱一档，"
              "读原生率时应把这部分单独看。", ""]
    if undecl:
        items = "、".join(f"{k}（{v} 条）" for k, v in
                          sorted(undecl.items(), key=lambda kv: -kv[1]))
        L += [f"> ⚠ **未登记获取路径的信源：{items}** —— 已按保守口径计入关键词检索。"
              "新增信源请到 `hunter/paths.py` 的 `SOURCE_PATH` 登记，"
              "否则它不会（也不应该）自动获得「原生榜」身份。", ""]
    L.append("</details>")
    return "\n".join(L)


def _forhire():
    """r/forhire：有人出钱找人做事（RSS 官方端点，免登录）—— Upwork 的等效源。

    注意 health 的 source 被改写成 reddit:forhire：reddit_rss 返回的名字就是
    "reddit"，不改写会和主 reddit 列表混成一个键，能力表认不出这条等效源。
    """
    # 重试 2 次：实测首次可能因代理侧 SSL EOF 失败（UNEXPECTED_EOF_WHILE_READING），
    # 重试即通。等效源存在的意义就是"顶上去"，不能因为一次握手失败就当它不可用。
    last = None
    for i in range(3):
        try:
            rs, h = sources.reddit_rss(["forhire"], spacing=0)
            if rs:
                h = dict(h)
                h["source"] = "reddit:forhire"
                if i:
                    h["note"] = f"{h.get('note', '')}（第 {i+1} 次重试成功）"[:90]
                return rs, h
            last = h
        except Exception as e:
            last = {"source": "reddit:forhire", "count": 0, "ok": False,
                    "note": f"{type(e).__name__}: {str(e)[:70]}"}
        time.sleep(3)
    h = dict(last or {})
    h["source"] = "reddit:forhire"
    h.setdefault("count", 0)
    h["ok"] = False
    return [], h


def _juejin():
    """掘金热榜（免登录）—— 中文需求的弱等效（偏技术，非消费社区）。"""
    from hunter import opencli as _oc
    d, m = _oc.run(["juejin", "hot", "--limit", "20"], timeout=120)
    rows = _oc._rows(d)
    out = []
    for r in rows:
        rec = _oc._norm("juejin", r, "juejin:hot")
        # 掘金的原生热度是浏览/点赞/评论，_norm 只捕到 views；补成综合热度，
        # 否则同样会因热度不足被热点通道丢掉（与 bluesky 同一类坑）。
        h = rec.get("heat") or {}
        h["score"] = int(h.get("views") or 0) + int(h.get("votes") or 0) * 3
        rec["heat"] = h
        out.append(rec)
    return out, {"source": "opencli:juejin:hot", "count": len(rows), "ok": m["ok"],
                 "note": "免登录弱等效（中文技术热榜，非消费社区）"}


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
            if args.enable_dead:
                # Upwork 是"近期发布的活"，只对短窗口有意义
                for q in UPWORK_QUERIES:
                    oc_sources.append((f"upwork:{q[:16]}",
                                       lambda qq=q: oc.upwork_search(qq, 30)))
            else:
                # 已知不可用（适配器侧故障）→ 跳过，不计失败。
                # 付费需求能力由 github_bounties + r/forhire 覆盖（见 resilience）。
                for q in UPWORK_QUERIES:
                    health.append({"source": f"opencli:upwork[{q[:16]}]", "count": 0,
                                   "ok": False, "skipped": True,
                                   "note": rz.SKIP_DEFAULT["upwork"][:70]})
        # ---- 免登录等效源（P0-3 依赖对冲）----
        if w["label"] in ("今日", "本周"):
            # 付费需求：GitHub 开放赏金（金额写在 issue 里）+ r/forhire（官方 RSS）
            oc_sources.append(("github_bounties", lambda: sources.github_bounties(per_page=40)))
            oc_sources.append(("reddit:forhire", lambda: _forhire()))
        if w["label"] == "今日":
            # 中文弱等效 + 创始人弱等效（都免登录，价值有限但保证不空白）
            oc_sources.append(("juejin:hot", lambda: _juejin()))
            oc_sources.append(("bluesky:trending", lambda: sources.bluesky_trending(20)))
        if w["label"] == "今日":
            oc_sources += [("producthunt:today", lambda: oc.producthunt_today()),
                           ("hn:show", lambda: oc.hackernews("show", 25)),
                           ("hn:ask", lambda: oc.hackernews("ask", 25))]
        # ---- 第二批适配器（2026-09-17 接入）----
        # 公开源（无需登录）：热门问题/文章都是"当下"，挂今日窗口
        if w["label"] == "今日":
            for t in SO_TAGS:
                oc_sources.append((f"stackoverflow#{t}",
                                   lambda tt=t: oc.stackoverflow_tag(tt, 20)))
            for t in LB_TAGS:
                oc_sources.append((f"lobsters#{t}",
                                   lambda tt=t: oc.lobsters_tag(tt, 15)))
            for t in DT_TAGS:
                oc_sources.append((f"devto#{t}",
                                   lambda tt=t: oc.devto_tag(tt, 15)))
            oc_sources.append(("lesswrong:top-week",
                               lambda: oc.lesswrong_top(10)))
            # 论坛评论深读：列表页只有热度数字，**抱怨都在评论区**。
            # 按评论数/赞数挑帖深读，评论赞同数即"多少人认同这个抱怨"。
            oc_sources += [("hn:deep:show", lambda: oc.hackernews_deep("show", 2)),
                           ("lobsters:deep", lambda: oc.lobsters_deep(2)),
                           ("so:deep:automation",
                            lambda: oc.stackoverflow_deep("automation", 2))]
        # 需要登录的源：未登录时适配器报 AUTH_REQUIRED，health 可见，不静默
        if w["label"] in ("今日", "本周"):
            for q in INDEED_QUERIES:
                oc_sources.append((f"indeed:{q[:16]}",
                                   lambda qq=q: oc.indeed_search(qq)))
            if args.enable_dead:
                for q in TW_QUERIES:
                    oc_sources.append((f"twitter:{q[:20]}",
                                       lambda qq=q: oc.twitter_search(qq)))
            else:
                for q in TW_QUERIES:
                    health.append({"source": f"opencli:twitter[{q[:20]}]", "count": 0,
                                   "ok": False, "skipped": True,
                                   "note": rz.SKIP_DEFAULT["twitter"][:70]})
            for q in XHS_QUERIES:
                oc_sources.append((f"xhs:{q[:12]}",
                                   lambda qq=q: oc.xhs_search(qq, 15)))
            oc_sources.append(("zhihu:hot", lambda: oc.zhihu_hot(15)))
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
    ap.add_argument("--enable-dead", action="store_true",
                    help="强制尝试已知不可用的源（upwork/twitter）；默认跳过，"
                         "跳过不计入失败率（否则真实退化会被永久失败掩盖）")
    ap.add_argument("--no-upwork", action="store_true",
                    help="跳过 Upwork（需在 Chrome 里登录过 upwork.com）")
    ap.add_argument("--llm", action="store_true",
                    help="用 LLM 做语义方向分类与付费信号提取（需 DEEPSEEK_API_KEY，"
                         "未配置时自动回退关键词签名）")
    ap.add_argument("--annotations", default="",
                    help="agent 标注文件（JSON：source_id 前 44 字符 -> [方向, wtp, pain]），"
                         "由 Claude 直读原文后写入，优先级高于 --llm")
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
    classify_mode = "关键词签名"

    # agent 标注：Claude 直读原文后的语义分类，优先级最高（见 tools/write_agent_annotations.py）
    # 注意：这里**不再**无条件设置 classify_mode。判定方式必须按实际命中率算，
    # 见 _classify_mode() 的说明（原实现在这里虚标过）。
    ann = {}
    if args.annotations:
        with open(args.annotations, encoding="utf-8") as f:
            ann = json.load(f)

    def apply_annotations(records):
        hit = 0
        for r in records:
            a = ann.get((r.get("source_id") or "")[:44])
            if a:
                r["direction"] = a[0] if a[0] != "无" else None
                r["llm_wtp"] = a[1]
                r["llm_pain"] = a[2]
                hit += 1
        return hit

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
        # 先恢复 health：循环内要用它算"原生源失败数"（放循环后会拿到空列表）
        health = blob.get("health", [])
        print(f"从缓存重聚合：{src}")
        for k, v in blob.get("windows", {}).items():
            if k not in keys:
                continue
            kept = v.get("kept", [])
            ann_hits = 0
            if ann:
                ann_hits = apply_annotations(kept)
            elif args.llm:
                _n, _m = llm.classify_batch(kept)
                classify_mode = _m if _n else "关键词签名（LLM 不可用）"
            stat = dr.aggregate(kept)
            rows = dr.top_directions(stat, n=args.top, min_evidence=args.min_evidence)
            done, errs = dr.attach_crowding(stat, rows, sources.github_count,
                                            cache=crowd_cache)
            crowd_errs += errs
            dr.attach_supply(rows, sources.github_mature_count, cache=crowd_cache)
            dr.attach_real_cases(rows, sources.github_mature, cache=crowd_cache)
            results[k] = {"label": v.get("label", k), "raw": v.get("raw", len(kept)),
                          "kept": len(kept), "stat": stat, "rows": rows,
                          "records": kept, "path_stats": paths.counts(kept),
                          "ann_hits": ann_hits,
                          "native_breakdown": paths.breakdown(kept),
                          "undeclared": paths.undeclared(kept),
                          "native_fail": _native_fails(health)}
            print(f"  [{v.get('label', k)}] {len(kept)} 条 → {len(rows)} 个方向"
                  f"（拥挤度已补 {done} 个；语义标注命中 {ann_hits}/{len(kept)}）")
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
            ann_hits = 0
            if ann:
                ann_hits = apply_annotations(kept)
            elif args.llm:
                _n, _m = llm.classify_batch(kept)
                classify_mode = _m if _n else "关键词签名（LLM 不可用）"
            stat = dr.aggregate(kept)
            rows = dr.top_directions(stat, n=args.top, min_evidence=args.min_evidence)
            done, errs = dr.attach_crowding(stat, rows, sources.github_count,
                                            cache=crowd_cache)
            crowd_errs += errs
            dr.attach_supply(rows, sources.github_mature_count, cache=crowd_cache)
            dr.attach_real_cases(rows, sources.github_mature, cache=crowd_cache)
            results[k] = {"label": w["label"], "raw": len(uniq), "kept": len(kept),
                          "stat": stat, "rows": rows, "records": kept,
                          "path_stats": paths.counts(kept),
                          "ann_hits": ann_hits,
                          "native_breakdown": paths.breakdown(kept),
                          "undeclared": paths.undeclared(kept),
                          "native_fail": _native_fails(health)}
            cache[k] = {"label": w["label"], "raw": len(uniq), "kept": kept}
            print(f"  {len(uniq)} 条 → 规则层 {len(kept)} 条 → {len(stat)} 个候选方向 "
                  f"→ 输出 {len(rows)} 个（拥挤度已补 {done} 个；"
                  f"语义标注命中 {ann_hits}/{len(kept)}）")
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

    # 判定方式按**实际命中率**定，而不是"有没有传 --annotations"。
    # 传了标注文件但命中率很低（标注是上一轮数据、缓存已换）时，必须如实降级标注。
    ann_hit_total = sum(v.get("ann_hits", 0) for v in results.values())
    kept_total = sum(v.get("kept", 0) for v in results.values())
    if ann:
        classify_mode = _classify_mode(ann, ann_hit_total, kept_total)
        if kept_total:
            print(f"  语义标注覆盖 {ann_hit_total}/{kept_total} 条"
                  f"（{ann_hit_total / kept_total:.0%}）"
                  f"→ 判定方式记为「{classify_mode}」")
        else:
            print("  本窗口无留存记录")

    # 建议与趋势：必须在**所有窗口**都算完后做（趋势要看跨窗口的增速与共振）
    adv_map = advice.annotate({v["label"]: v["rows"] for v in results.values()})
    hot = sorted((a for a in adv_map.items() if a[1]["trend"]["level"] == "高"),
                 key=lambda kv: -kv[1]["trend"]["score"])
    if hot:
        print("  趋势高（可能爆发）：" + "、".join(n for n, _ in hot[:5]))

    # 验证闭环（P0-2）：给够格方向生成可执行验证包，并读台账算北极星
    rows_by_window = {v["label"]: v["rows"] for v in results.values()}
    kit_md, kits = vd.build_kits(rows_by_window)
    vstats = vd.stats()
    rz_res = rz.assess(health)
    rz_summary = rz.summary_md(rz_res)
    vqueue = vd.pending_queue(rows_by_window)
    with open(os.path.join(OUT, "resilience.json"), "w", encoding="utf-8") as f:
        json.dump({"rows": rz_res["rows"], "gap_rate": rz_res["gap_rate"],
                   "fail_rate": rz_res["fail_rate"], "skipped": rz_res["skipped"],
                   "degraded": rz_res["degraded"], "lost": rz_res["lost"],
                   "n_capabilities": rz_res["n_capabilities"],
                   "compliance": rz.COMPLIANCE},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "validation_kits.json"), "w", encoding="utf-8") as f:
        json.dump({"kits": kits, "stats": vstats, "queue": vqueue},
                  f, ensure_ascii=False, default=str)

    ts = time.strftime("%Y%m%d-%H%M")
    rp = os.path.join(OUT, f"directions_{ts}.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(render(results, health, args, classify_mode,
                       kit_md=kit_md, vstats=vstats, rz_summary=rz_summary,
                       ann_hit=ann_hit_total, kept_total=kept_total,
                       ann_used=bool(ann)))
    jp = os.path.join(OUT, f"directions_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   # 判定方式必须落盘：看板要"描述这次运行"，而不是自己重新猜一遍。
                   # 此前看板无条件加载 out/agent_annotations.json 并自行判定，
                   # 于是同一次采集的两个产物会给出不同的判定方式（看板按 40% 覆盖
                   # 标"含部分语义标注"，报告因为没传 --annotations 标"关键词签名"）。
                   # 记录在这里之后，两边只有一个事实来源。
                   "classify": {"mode": classify_mode,
                                "ann_used": bool(ann),
                                "ann_hit": ann_hit_total,
                                "kept": kept_total},
                   "windows": {k: {"label": v["label"], "raw": v["raw"],
                                   "kept": v["kept"],
                                   "path_stats": list(v.get("path_stats") or []),
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


def render(results, health, args, classify_mode="关键词签名", kit_md=None,
           vstats=None, rz_summary=None, ann_hit=0, kept_total=0, ann_used=False):
    semantic = _is_semantic(classify_mode)
    L = ["# 值得看的方向 Top10 · 按时效性分层", "",
         f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}", ""]
    # 北极星放最前面：按项目自己的判据（"必须有验证闭环，否则整条流水线的产出等于零"），
    # 它是全局最重要的一条状态，不该藏在报告末尾的章节里。
    if vstats:
        ok = "✅ 达标" if vstats["north_star"] >= vstats["target"] else "❌ 未达标"
        L += [f"> **北极星（近 {vstats['window_days']} 天验证通过方向数）："
              f"{vstats['north_star']} / 目标 ≥{vstats['target']}　{ok}**　"
              "—— 在它达标之前，下面的榜单只是「候选」，不是结论。", ""]
    L += ["**判定口径**：把散点候选聚合成「方向」后按证据强度排序。",
          f"方向判定方式：**{classify_mode}**。"
          + ("各方向语义等距，不存在签名宽度偏差。"
             if semantic else
             "关键词模式下签名宽度不等（AI 方向最宽），跨方向证据数不可直接比热度。")]
    cov = _coverage_line(ann_hit, kept_total, ann_used=ann_used)
    if cov:
        L.append(cov)
    L += ["",
          "证据数 = 该方向在本时间窗内的独立候选条数（同一候选只计入一个方向，避免重复计数）。", "",
          f"（GitHub 查询缓存：{sources.cache_stats()['entries']} 条已缓存 / "
          f"{sources.cache_stats()['fresh']} 条新鲜——限流时过期旧值会被兜底使用并标记）", "",
          "**两条证据通道**：需求证据（过痛点/付费构式门槛）与平台热点证据"
          "（原生榜+热度达标，不走门槛）。**共振只统计原生榜**——"
          "关键词检索命中是同一个查询在多个平台的回声，不等于独立发现。", "",
          "**评分** = 证据数×1.0 + 信源多样性×0.8 + 付费信号×1.2 + 仓库热度×1.5 + 仓库数×0.4", "",
          "**强度**：≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。弱信号不等于没价值，"
          "但只有一条独立证据时不足以支撑判断 —— 它需要在下个窗口复现才算成立。", "",
          "**口径警告（读榜单前必读）**：", "",
          "1. **各方向的关键词签名宽度不等** —— " + (
              "本条不适用于纯语义分类模式（各方向语义等距）。" if semantic else
              "「AI 代理与自动化」的签名最宽（agent/llm/prompt/mcp/rag/automation…"
              "近 10 组高频词），而「支付与账单」等方向命中面窄。**宽签名天然抓得多，"
              "跨方向的证据数不能直接当热度比较**——头部方向的领先幅度要看折扣。")]
    # 第 2 条按**本轮实际数据**生成。原实现是硬编码字符串（写死"本周榜第一的 8 条证据
    # = 4 条 HN + 2 个 GitHub 仓库 + 1 个 Trending + 1 个 Reddit 帖"），
    # 只跑今日窗口时也照样输出，等于用一句与数据无关的话冒充口径说明。
    comp = _evidence_composition(next(iter(results.values()))["rows"]) if results else None
    if comp:
        L.append(f"2. **绝对证据数很小**。本窗口榜第一的「{comp['name']}」= "
                 f"{comp['evidence']} 条需求证据 + {comp['hot']} 条热点证据"
                 f"（{comp['parts']}" + ("，此处仅列前 12 条" if comp["truncated"] else "")
                 + "），排名对一两条记录的波动敏感，别把「第一」读成「优势巨大」。")
    else:
        L.append("2. **绝对证据数很小**：本窗口没有可归类的方向，无法给出证据构成。")
    L += ["3. **各平台采集相互独立**（HN/Reddit/Upwork 的查询都是写死的常量，"
          "不存在用 GitHub 结果去搜其他平台的循环），"
          "但 Reddit 样本量小（规则层拦截后每周仅个位数），其\"投票权\"有限。", "",
          "---", ""]
    for k, v in results.items():
        L += [f"## {v['label']}", "",
              dr.render_window(v["label"], v["rows"], len(v["stat"]), v["raw"],
                               path_stats=v.get("path_stats"),
                               native_fail=v.get("native_fail")),
              "", _native_breakdown_md(v.get("native_breakdown"),
                                       v.get("undeclared")),
              "", dr.platform_view(v.get("records", [])),
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

    if rz_summary:
        L += ["", *rz_summary]
    L += ["", "## 验证闭环（P0-2）", ""]
    if vstats:
        # 北极星的标题行已挪到报告开头（那里才是它该在的位置），这里只留明细。
        L += [f"（北极星见报告开头）待续 {len(vstats['pending'])} 个 · "
              f"否决 {len(vstats['rejected'])} 个 · "
              f"误杀复活 {len(vstats['resurrected'])} 个 · 误杀率 "
              f"{'—' if vstats['mistake_rate'] is None else format(vstats['mistake_rate'], '.0%')}）", "",
              "> 判定标准：**通过 = ≥2 个独立受访者已在为此付费或给出明确预算**。"
              "表达\"有意思\"不算证据。", "",
              "> 记录方式：`python tools/validation.py log \"<方向>\" --result pass "
              "--intents 3 --note \"...\"`；待验证队列：`python tools/validation.py queue`。", ""]
    if kit_md:
        L += ["### 验证包（可直接执行：去哪问 / 问什么 / 怎么判定 / 可复制脚本）", ""] + kit_md
    L += ["## 信源健康", "", "| 信源 | 条数 | 状态 | 备注 |", "|---|---:|---|---|"]
    for h in health:
        st = "⏭ 跳过" if h.get("skipped") else ("✅" if h.get("ok") else "❌")
        L.append(f"| {h['source']} | {h.get('count', 0)} | {st} | {h.get('note', '')} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
