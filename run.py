#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
需求挖掘流水线 —— 编排入口（两队列架构）

  供给队列：GitHub Trending + Search  → 找到"强但门槛高"的仓库/技术方向
  需求队列：GitHub Issues + HN 评论    → 找到真实用户原话式的抱怨与付费意愿
  交叉验证：对供给队列的头部仓库，去 HN 搜讨论量，确认不是纯技术自嗨

用法：
  python run.py                     # 全流程
  python run.py --no-llm            # 只跑到规则过滤，零成本看漏斗
  python run.py --top-llm 15        # 控制送进 LLM 的条数（控成本）
  python run.py --seeds 6           # 对前 6 个仓库做 Issues 深挖

退出码：0 正常；2 有关键信源健康检查失败（页面结构变更等），必须人工介入。
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hunter import sources, filter as flt, llm, store, browser  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")

CFG = {
    "min_stars": 80,
    "min_text_len": 120,
    "hn_queries": [
        "self-hosted too complex",
        "no web interface CLI only",
        "willing to pay tool",
        "I would pay for",
        "why is there no tool for",
        "setup is a nightmare",
        "manually every time",
    ],
}


def collect(args, health):
    raw = []
    if not args.hn_only:
        for since in ("daily", "weekly"):
            try:
                rs, h = sources.github_trending(since=since, language=args.lang)
                raw += rs
                health.append(h)
            except Exception as e:
                health.append({"source": f"github_trending:{since}", "count": 0,
                               "ok": False, "note": f"抓取异常 {e}"})
        try:
            rs, h = sources.github_search_new_rising(days=args.days)
            raw += rs
            health.append(h)
        except Exception as e:
            health.append({"source": "github_search", "count": 0,
                           "ok": False, "note": f"抓取异常 {e}"})
    try:
        rs, h = sources.hn_pain_points(CFG["hn_queries"], days=args.hn_days)
        raw += rs
        health.append(h)
    except Exception as e:
        health.append({"source": "hn", "count": 0, "ok": False, "note": f"{e}"})

    # Reddit：走本地代理 + RSS 端点（HTML 会被 403，见 sources.py 注释）
    if args.reddit:
        try:
            subs = [s.strip() for s in (args.reddit_subs or "").split(",") if s.strip()]
            rs, h = sources.reddit_rss(subs or None)
            raw += rs
            health.append(h)
        except Exception as e:
            health.append({"source": "reddit", "count": 0, "ok": False,
                           "note": f"异常 {e}"})

    # 浏览器通道：补官方 API 覆盖不到的站点（无 API 的社区页面）
    browser_probe = []
    if args.browser:
        for key in [s.strip() for s in (args.browser_sites or "").split(",") if s.strip()]:
            if key not in browser.SITES:
                health.append({"source": f"browser:{key}", "count": 0, "ok": False,
                               "note": f"未配置的站点，可用：{list(browser.SITES)}"})
                continue
            try:
                rs, h = browser.collect_site(key)
                raw += rs
                health.append(h)
                browser_probe.append({"site": key, "ok": h["ok"], "note": h["note"]})
            except Exception as e:
                health.append({"source": f"browser:{key}", "count": 0, "ok": False,
                               "note": f"浏览器通道异常 {e}"})
    return raw, browser_probe


def pick_enrich_targets(seeds, n):
    """挑选 Issues 深挖对象。

    关键教训：不能挑"最新最火"的仓库去挖 issue —— 刚建三周的项目根本没积累
    用户抱怨，挖出来必然是空的（首版实测 4 个仓库全部 0 条）。
    真正有挖掘价值的是"已跑了一段时间、有真实用户流量、且积累了未解决诉求"的项目。
    """
    import math
    scored = []
    for s in seeds:
        oi = s.get("open_issues") or 0
        age = flt._age_days(s.get("created_at")) or 999
        # 太新的项目：没有 issue 历史，除非已有相当量级的 issue
        if age < 60 and oi < 10:
            continue
        v = math.log10(oi + 1) * 2.0
        v += 1.0 if (s.get("license") in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC")) else 0
        v += min((s.get("stars_total") or 0) / 2000.0, 2.0)
        s["_enrich_score"] = round(v, 2)
        scored.append(s)
    scored.sort(key=lambda x: -x["_enrich_score"])
    # 兜底：若全部被过滤（今日榜单全是新项目），退回按原分排序取头部
    return scored[:n] if scored else seeds[:min(n, 2)]


def enrich(seeds, n, health):
    """对供给队列头部仓库做 Issues 深挖 —— 方法论里最关键、也最容易被跳过的一步。"""
    out = []
    picked = []
    for s in pick_enrich_targets(seeds, n):
        repo = s.get("repo")
        if not repo:
            continue
        issues, err = sources.github_issues(repo)
        if err:
            health.append({"source": f"issues:{repo}", "count": 0, "ok": False, "note": err})
            continue
        # issue 记录继承仓库的协议/风险元数据，否则打分时看不到商用障碍
        for it in issues:
            it["license"] = s.get("license")
            it["stars_total"] = s.get("stars_total")
            it["forks"] = s.get("forks")
            it["risk_flags"] = s.get("risk_flags")
            it["supply_risk"] = s.get("supply_risk")
            it["seed_repo_url"] = s.get("url")
        out += issues
        picked.append({"repo": repo, "url": s.get("url"),
                       "issues_found": len(issues),
                       "license": s.get("license"),
                       "stars": s.get("stars_total"),
                       "risk": s.get("risk_flags")})
        time.sleep(6.5)  # search API 未认证 10/min，认证 30/min
    health.append({"source": "github_issues", "count": len(out),
                   "ok": len(out) > 0, "note": f"深挖 {len(picked)} 个仓库"})
    return out, picked


def cross_validate(seeds, n=5):
    """交叉验证：技术方向在社区到底有没有人讨论、有多少。防"技术自嗨"。"""
    res = []
    for s in seeds[:n]:
        repo = (s.get("repo") or "").split("/")[-1]
        if not repo:
            continue
        r = sources.hn_search(repo)
        r["repo"] = s.get("repo")
        res.append(r)
        time.sleep(0.8)
    return res


def select_for_llm(demand, top, per_source_min=2):
    """按信源配额挑选送进 LLM 的记录。

    为什么不能只按全局分数排序：召回量大的信源（HN）会靠"条数多"把 LLM 预算
    全部挤占，导致信噪比更高的信源（Issues / 浏览器深读）一条都进不去。
    实测就是这么发生的：top12 全是 HN，而质量更高的通道 0 条。
    所以先给每个信源保底名额，剩下的再按分数抢。
    """
    by_src = {}
    for r in demand:
        by_src.setdefault(r["source"], []).append(r)
    picked, used = [], set()
    for src, items in by_src.items():
        for r in items[:per_source_min]:
            if len(picked) >= top:
                break
            picked.append(r)
            used.add(id(r))
    rest = [r for r in demand if id(r) not in used]
    for r in rest:
        if len(picked) >= top:
            break
        picked.append(r)
    picked.sort(key=lambda x: -x.get("prefilter_score", 0))
    return picked[:top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--top-llm", type=int, default=12)
    ap.add_argument("--seeds", type=int, default=5, help="Issues 深挖的仓库数")
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--hn-days", type=int, default=120)
    ap.add_argument("--hn-only", action="store_true")
    ap.add_argument("--lang", default="")
    ap.add_argument("--browser", action="store_true",
                    help="启用浏览器通道，补官方 API 覆盖不到的站点")
    ap.add_argument("--browser-sites", default="indiehackers,hn_ask",
                    help="浏览器通道站点，逗号分隔")
    ap.add_argument("--reddit", action="store_true",
                    help="启用 Reddit RSS（需本地代理）")
    ap.add_argument("--reddit-subs", default="SaaS,microsaas,SideProject",
                    help="Reddit 子版块，逗号分隔；限流很紧，别超过 4 个")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    health = []
    raw, browser_probe = collect(args, health)

    st = store.Store(os.path.join(ROOT, "data", "hunter.sqlite3"))
    fresh, seen = st.split_new(raw)
    funnel = {"raw": len(raw), "dedup_removed": seen, "fresh": len(fresh)}

    kept, dropped = flt.rule_filter(fresh, CFG)
    seeds = [k for k in kept if k.get("record_type") == "supply"]
    demand = [k for k in kept if k.get("record_type") == "demand"]
    funnel.update({"seeds": len(seeds), "demand_after_rules": len(demand),
                   "dropped_L1_L2": len(dropped)})

    issues, picked = ([], [])
    if not args.hn_only and seeds:
        issues, picked = enrich(seeds, args.seeds, health)
        if issues:
            issues_new, _ = st.split_new(issues)
            issues_f, issues_dropped = flt.rule_filter(issues_new, CFG)
            demand += issues_f
            dropped += issues_dropped
    funnel["issue_records"] = len(issues)
    funnel["demand_total"] = len(demand)

    xval = cross_validate(seeds, n=5) if seeds else []

    demand.sort(key=lambda x: -x.get("prefilter_score", 0))
    to_score = select_for_llm(demand, args.top_llm)
    scored, mode = [], "skipped"
    if not args.no_llm:
        for r in to_score:
            obj, mode = llm.score(r)
            scored.append({**r, "judge": obj})
    funnel["sent_to_llm"] = 0 if args.no_llm else len(to_score)

    ts = time.strftime("%Y%m%d-%H%M")
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "funnel": funnel, "health": health, "llm_mode": mode,
        "browser_probe": browser_probe,
        "scored": sorted(scored, key=lambda x: -(x["judge"].get("total") or 0)),
        "seed_repos": seeds[:20], "enriched": picked, "cross_validation": xval,
        "dropped_sample": dropped[:40],
    }
    jp = os.path.join(OUT, f"candidates_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    rp = os.path.join(OUT, f"report_{ts}.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(render(payload))
    st.close()

    print(f"\n漏斗: {json.dumps(funnel, ensure_ascii=False)}")
    print(f"LLM 模式: {mode}")
    for h in health:
        print(f"  {'OK ' if h['ok'] else '!! '}{h['source']:<26} {h['count']:>4} 条  {h['note']}")
    print(f"\nJSON -> {jp}\n报告 -> {rp}")
    return 2 if [h for h in health if not h["ok"]] else 0


def render(p):
    L = [f"# 需求挖掘日报 {p['generated_at']}", "",
         f"LLM 模式：`{p['llm_mode']}`", "",
         f"**漏斗**：{' → '.join(f'{k} {v}' for k, v in p['funnel'].items())}", "",
         "## 一、信源健康检查", "", "| 信源 | 条数 | 状态 | 备注 |", "|---|---:|---|---|"]
    for h in p["health"]:
        L.append(f"| {h['source']} | {h['count']} | {'✅' if h['ok'] else '❌'} | {h['note']} |")

    L += ["", "## 二、需求候选（带原文证据，按总分排序）", ""]
    if not p["scored"]:
        L.append("_未执行 LLM 打分（--no-llm）_")
    for i, c in enumerate(p["scored"], 1):
        j = c["judge"]
        L += [f"### {i}. {(c.get('title') or '')[:110]}　`总分 {j.get('total')}`", "",
              f"来源 `{c['source']}`　[原文]({c['url']})",
              "" if not c.get("repo") else f"　　关联仓库：`{c['repo']}`　协议 {c.get('license') or '未知'}",
              f"- 评分：购买意图 **{j.get('buyer_intent')}/5**　付费意愿 **{j.get('wtp_signal')}/5**　"
              f"MVP可行性 **{j.get('mvp_feasibility')}/5**　竞争 **{j.get('competition')}/5**",
              f"- 痛点摘要：{j.get('pain_summary', '')}",
              f"- 引用核验：{j.get('_quotes_verified', '-')}/{j.get('_quotes_total', '-')}"
              f"　可复用内核：{j.get('reusable_core')}"]
        for q in (j.get("evidence_quotes") or [])[:3]:
            L.append(f"  > {q}")
        if j.get("kill_reason"):
            L.append(f"- ⚠️ {j['kill_reason']}")
        L.append("")

    L += ["## 三、供给侧对象（可作为内核复用的上升仓库）", "",
          "| 仓库 | ★ | 日均涨星 | fork/star | 协议 | 风险标记 |",
          "|---|---:|---:|---:|---|---|"]
    for s in p["seed_repos"][:15]:
        stars = s.get("stars_total") or 0
        forks = s.get("forks") or 0
        L.append(f"| [{s['repo']}]({s['url']}) | {stars} | {s.get('star_velocity', '-')} | "
                 f"{(forks / stars if stars else 0):.3f} | {s.get('license') or '未声明'} | "
                 f"{'；'.join(s.get('risk_flags') or []) or '—'} |")

    L += ["", "## 四、Issues 深挖结果", "", "| 仓库 | 命中的高讨论度 issue | 协议 |", "|---|---:|---|"]
    for e in p["enriched"]:
        L.append(f"| {e['repo']} | {e['issues_found']} | {e.get('license') or '未声明'} |")

    L += ["", "## 五、社区交叉验证（防技术自嗨）", "",
          "| 关键词 | 近一年 HN 讨论量 | 结论 |", "|---|---:|---|"]
    for c in p["cross_validation"]:
        verdict = ("⚠️ 社区几乎无讨论：技术自嗨，需求侧待验证" if c["count"] < 5
                   else ("✅ 有真实讨论" if c["count"] >= 20 else "一般，需人工看内容"))
        L.append(f"| {c.get('repo') or c['term']} | {c['count']} | {verdict} |")

    probe = p.get("browser_probe") or []
    if probe:
        L += ["", "## 六、浏览器通道（补官方 API 覆盖不到的站点）", "",
              "| 站点 | 状态 | 说明 |", "|---|---|---|"]
        for b in probe:
            L.append(f"| {b['site']} | {'✅' if b['ok'] else '❌'} | {b['note']} |")

    L += ["", "## 七、被规则层拦截的样本（前 40 条）", "", "| 环节 | 原因 | 对象 |", "|---|---|---|"]
    for d in p["dropped_sample"]:
        L.append(f"| {d.get('drop_stage')} | {d.get('drop_reason')} | "
                 f"{(d.get('title') or d.get('repo') or d.get('url') or '')[:70]} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
