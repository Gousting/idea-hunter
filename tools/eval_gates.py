#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
门槛对照实验：验证"能不能靠关键词把需求侧精度做起来"。

结论导向的问题：如果多加几层正则就能得到可用的需求清单，那 AI 过滤只是锦上添花；
如果不能，AI 过滤就是结构性必需——这直接决定方案该把工程投入放在哪一层。

指标说明（重要，别把它当精度）：
  "主题相关"是一个代理指标：判定信号短语附近 140 字符内是否出现工具/软件类名词。
  它不能证明这条抱怨真的是需求，只能排除"完全跑题"。
  真实质量必须人工抽查，脚本会在最后输出抽样供人工核对。
"""
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hunter import sources  # noqa: E402

UA = {"User-Agent": "idea-hunter/0.1"}

TOOL_NOUN = re.compile(
    r"\b(app|tool|software|service|saas|cli|library|sdk|dashboard|gui|ui|"
    r"api|plugin|extension|integration|automation|script|platform|website|"
    r"self[- ]hosted|docker|team|plan|subscription|license)\b", re.I)

G1 = re.compile(r"willing to pay|would pay|happy to pay|i'?d pay|paid (version|plan)", re.I)
G2 = re.compile(r"\b(i|we)\b[^.!?\n]{0,50}?\b(would|'d|will|happy|gladly|willing|'?ll)\b"
                r"[^.!?\n]{0,25}?\bpay\b", re.I)
G3 = re.compile(r"\b(i|we)\b[^.!?\n]{0,50}?\b(would|'d|will|happy|gladly|willing|'?ll)\b"
                r"[^.!?\n]{0,25}?\bpay\b[^.!?\n]{0,60}?\b(for|to)\b", re.I)

QUERIES_GENERIC = ["willing to pay", "I would pay for", "happy to pay", "take my money"]
# 垂直场景短语：**必须用 1-2 个短词扇出，不能写自然语言长句**。
#
# 2026-09-18 修复：原实现是三条长句，实测命中数为
#     "invoice reconciliation tool too manual"    → 0 条
#     "self-hosted monitoring setup too complex"  → 0 条
#     "no web interface command line only"        → 6 条
# 也就是"垂直场景"这一臂**实际是死的**，样本 100% 来自上面 4 个通用付费短语。
# 后果：实验只证明了「通用短语的精度天花板低」，没有测到「场景化短语是否更好」——
# 而后者恰恰是本实验想要反驳的那个替代方案，属于论证结构上缺了对照组。
# 而这条教训本文档实验 3 自己写过（"用 1-2 个短词 + numericFilters，别写自然语言长句"），
# 脚本却违反了它。
#
# 替换后实测召回（同口径，100 条上限）：34 / 98 / 100 / 98 / 100 条可用评论。
# 改动后两个臂都有真实样本，"垂直短语是否优于通用短语"才第一次被真正测到。
QUERIES_VERTICAL = [
    "reconciliation manual",     # 对账靠手工
    "self-hosted complex",       # 自托管太复杂
    "command line only",         # 只有 CLI、没有 GUI
    "manual data entry",         # 手工录入
    "too complex to set up",     # 配置门槛高
]


def fetch(q, days=365, per_page=100):
    cut = int(time.time()) - days * 86400
    url = ("https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote(q)
           + f"&tags=comment&hitsPerPage={per_page}&numericFilters=created_at_i>{cut}")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        import json
        d = json.loads(r.read().decode("utf-8"))
    out = []
    for h in d.get("hits", []):
        t = re.sub(r"<[^>]+>", " ", h.get("comment_text") or "")
        t = " ".join(urllib.parse.unquote(t).split())
        if len(t) >= 120:
            out.append({"text": t, "title": h.get("story_title") or "",
                        "url": f"https://news.ycombinator.com/item?id={h.get('objectID')}"})
    return out, d.get("nbHits", 0)


def near_tool(text, m, win=140):
    a, b = max(0, m.start() - win), min(len(text), m.end() + win)
    return bool(TOOL_NOUN.search(text[a:b]))


def evalgate(recs, pat):
    hit = []
    for r in recs:
        ms = list(pat.finditer(r["text"]))
        if ms:
            hit.append((r, any(near_tool(r["text"], m) for m in ms)))
    n = len(hit)
    ok = sum(1 for _, x in hit if x)
    return n, ok, hit


def main():
    recs = []
    arm = {}
    print("拉取 HN 评论（通用付费短语 + 垂直场景短语）...")
    for label, qs in (("通用", QUERIES_GENERIC), ("垂直", QUERIES_VERTICAL)):
        for q in qs:
            r, nb = fetch(q)
            print(f"  [{label}] {q:<40} 返回 {len(r):>3} 条 / 命中 {nb}")
            recs += r
            arm[label] = arm.get(label, 0) + len(r)
            time.sleep(0.8)
    # 自检：某一臂为空，说明查询写坏了，实验会退化成单臂（实测踩过：三条长句里
    # 两条返回 0 条 → 样本 100% 来自通用臂 → 测不到"垂直短语是否更好"这个对照组）。
    # 这种情况必须报警，不能静默继续给出结论。
    dead = [k for k, v in arm.items() if v == 0]
    print("\n各臂原始样本：" + "　".join(f"{k} {v} 条" for k, v in arm.items()))
    if dead:
        print(f"  ❌ {'、'.join(dead)}臂返回 0 条 —— 查询词很可能写成了自然语言长句。"
              "HN Algolia 多词是 AND 语义，请改用 1-2 个短词扇出。"
              "**此状态下结论只覆盖单臂，不能当作完整对照实验。**")
    # 去重
    seen, uniq = set(), []
    for r in recs:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        uniq.append(r)
    print(f"\n去重后样本量：{len(uniq)}\n")

    print(f"{'门槛':<46}{'通过条数':>8}{'主题相关':>10}{'相关率':>9}")
    print("-" * 74)
    names = {
        "G1 裸词面：willing to pay 等": G1,
        "G2 + 第一人称购买构式": G2,
        "G3 + 明确支付对象 (...pay for X)": G3,
    }
    results = {}
    for name, pat in names.items():
        n, ok, hit = evalgate(uniq, pat)
        rate = (ok / n * 100) if n else 0
        results[name] = (n, ok, rate)
        print(f"{name:<46}{n:>8}{ok:>10}{rate:>8.1f}%")

    n, ok, hit = evalgate(uniq, G3)
    print("\n抽样核对（G3 通过且被判定相关的样本，请人工看是否真的是需求）：")
    pool = [h for h in hit if h[1]][:6]
    for r, _ in pool:
        i = r["text"].lower().find("pay")
        s = max(0, i - 130)
        print(f"\n  · {r['title'][:78]}")
        print(f"    ...{r['text'][s:s + 240]}...")
        print(f"    {r['url']}")

    print("\n【结论】各层门槛的相对提升已量化。若 G3 的相关率仍显著低于可接受水平，")
    print("则说明'靠关键词做需求筛'不成立，AI 语义过滤是结构性必需，而非优化项。")


if __name__ == "__main__":
    main()
