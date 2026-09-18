#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把热榜付费潜力分析渲染成报告，并供看板读取。

为什么要单独渲染层：分析内容（agent 判断）与热榜数据（爬取结果）是两种东西，
前者会随判断更新、后者会随采集更新，混在一个文件里没法各自迭代。

用法：
  python tools/render_analysis.py            # 取最新 platforms_*.json + platform_analysis.json
"""
import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

TIER_LABEL = {"A": "A 级 · 付费路径明确", "B": "B 级 · 有可能需验证",
              "C": "C 级 · 无付费路径（明确排除）"}


def latest(pattern):
    c = sorted(glob.glob(os.path.join(OUT, pattern)))
    return c[-1] if c else None


def main():
    ap_path = os.path.join(OUT, "platform_analysis.json")
    if not os.path.isfile(ap_path):
        print("缺 out/platform_analysis.json（先跑 tools/write_platform_analysis.py）")
        return 2
    with open(ap_path, encoding="utf-8") as f:
        ana = json.load(f)
    pf_path = latest("platforms_*.json")
    pf = {}
    if pf_path:
        with open(pf_path, encoding="utf-8") as f:
            pf = json.load(f)

    items = ana["items"]
    L = ["# 热榜内容的付费潜力分析", "",
         f"生成时间：{ana.get('generated_at', '')}　·　"
         f"分析对象：{pf.get('collected', '—')} 条平台热榜（{len(pf.get('platforms', []))} 个平台）", "",
         "## 判断口径", "",
         ana.get("note", ""), "",
         "四个必答问题：**谁付钱**（具体角色）· **付费触发点**（新增支出还是旧预算搬家）· "
         "**现有供给**（有没有人做成、是不是云厂商自己在做）· **能否 2-4 周做出 MVP**。", "",
         "---", ""]

    # 判断层与规则层共用同一套 supply_risk 判据（见 write_platform_analysis.repo_risks）。
    # 为什么必须在报告顶部说清楚：判断层是手写散文，曾把规则层已判定刷星高危、
    # 并且已从方向报告里丢弃的仓库（jev-ultrafast 等）称为「本轮最强爆发信号」。
    # 自动层拒绝、手写层推荐 —— 这种矛盾不能只留在生成脚本的 stdout 里。
    n_high = sum(1 for i in items
                 if any(r.get("level") == "high" for r in (i.get("repo_risks") or [])))
    if n_high:
        L += [f"> ⚠ **风险提示：{n_high} 条判断引用了项目自己判定为「刷星高危」的仓库**"
              "（逐条标注在下方）。判断层与规则层共用同一套 `supply_risk` 判据 —— "
              "被规则层丢弃的仓库，不应该在判断层被当作正面信号推荐。", ""]

    for tier in ("A", "B", "C"):
        group = [i for i in items if i["tier"] == tier]
        if not group:
            continue
        L += [f"## {TIER_LABEL[tier]}（{len(group)} 项）", ""]
        for it in group:
            L += [f"### {it['title']}　<span>付费潜力 {it['pay']}/5</span>", "",
                  f"- **为什么上榜**：{it['why_hot']}",
                  f"- **谁付钱**：{it['who_pays']}",
                  f"- **付费触发点**：{it['trigger']}",
                  f"- **现有供给**：{it['supply']}",
                  f"- **结论**：{it['verdict']}",
                  f"- **建议动作**：{it['action']}"]
            if it.get("urls"):
                L.append("- 相关链接：" + " · ".join(f"[原帖]({u})" for u in it["urls"]))
            risky = [r for r in (it.get("repo_risks") or []) if r.get("level") == "high"]
            if risky:
                L.append("- ⚠ **本条引用的仓库触发了项目自己的反刷星高危阈值**：")
                for r in risky:
                    L.append(f"  - [{r['repo']}](https://github.com/{r['repo']})"
                             f"　★{r.get('stars')}　创建 {r.get('created_at')}"
                             f"　—— {'；'.join(r.get('flags') or [])}")
                L.append("  - 这些仓库会被规则层直接丢弃。**引用它们之前必须人工核查增长曲线**，"
                         "否则等于把一个已被自己的风控拒绝的对象推荐给读者。")
            unk = [r for r in (it.get("repo_risks") or []) if r.get("level") == "unknown"]
            if unk:
                L.append(f"- （有 {len(unk)} 个仓库的风险数据取不到，**未经核查**）")
            L.append("")
        L.append("")

    L += ["---", "", "## 两个方法层面的结论", "",
          "1. **付费潜力 ≠ 热度，今天的样本里近乎负相关**。热度榜首是知乎体育新闻（1163 万）和 "
          "HN 的 e-ink 相框（5313），而付费潜力最高的 MCP 工具在 Product Hunt 上热度只有 125。"
          "按热度挑方向会系统性地挑错。", "",
          "2. **该问的不是\"热不热\"，而是\"付费环节是不是新生成的\"**。A 级的四项"
          "（AEO、MCP 测试、独立开发者获客、AI 用量管理）全部来自**新增支出或新入口**；"
          "而 C 级的热门条目要么与软件无关（新闻、哲学），要么是无付费主体的开源项目。", ""]

    ts = time.strftime("%Y%m%d-%H%M")
    mp = os.path.join(OUT, f"analysis_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("分析报告 ->", mp)

    # 供看板读取（精简版）
    dash = {"generated_at": ana.get("generated_at", ""), "note": ana.get("note", ""),
            "items": [{k: it.get(k) for k in
                       ("tier", "pay", "title", "who_pays", "trigger", "supply",
                        "verdict", "action", "urls", "repo_risks")} for it in items]}
    dp = os.path.join(OUT, "platform_analysis_dashboard.json")
    with open(dp, "w", encoding="utf-8") as f:
        json.dump(dash, f, ensure_ascii=False, indent=1)
    print("看板数据 ->", dp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
