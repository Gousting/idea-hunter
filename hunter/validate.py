# -*- coding: utf-8 -*-
"""验证闭环：把"建议动作"变成可以直接执行的验证包，并把结果记进台账。

为什么要这一层（P0-2）：
现在报告止于"建议动作"一句话（如"本周人工核验 2-3 条原帖"），
但**核验什么、去哪问、怎么判定通过**全是空的，于是没有任何闭环：
没人知道推荐的方向后来有没有被验证，也没法度量"我们有没有推荐错"。
竞品的做法（DDMarketer）是每个 gap 附可跑的验证包——这是我们"最后一公里"的短板。

验证包的四要素（缺一不可，否则无法执行）：
  1. 去哪问   —— 从该方向证据的**原生平台**反查具体社区，而不是笼统说"去社区问"
  2. 问什么   —— 固定五问（现状 / 痛感 / 已付费行为 / 愿意付多少 / 谁决策）
  3. 怎么说   —— 可直接复制的 DM 与发帖脚本（英文为主，中文社区给中文版）
  4. 怎么判定 —— 明确的通过 / 待续 / 否决阈值 + 时间盒 + 样本来源要求

判定标准的取舍：用"**已在为此付费或明确预算**"而不是"他说有意思"。
表达兴趣几乎无成本（我们自己的痛点分析里"会怀疑"清单第一条就是结论强度 > 证据），
只有已经掏钱或明确报了预算的才算证据。阈值取 ≥2 个独立受访者，
且必须来自 ≥2 个不同社区——防止单一社区的同温层自我强化。
"""
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
LOG = os.path.join(OUT, "validation_log.json")

# 平台 → 具体可执行的社区查找方式（不是"去社区问"这种废话）
COMMUNITY = {
    "hackernews": "Ask HN 发帖（标题模板见脚本）+ 相关 Show HN 帖的评论区追问",
    "reddit": "从证据帖反查它所在的 subreddit，再到该 sub 发帖；另看 r/SaaS 每周"
              "\"what are you working on\" 帖",
    "producthunt": "竞品的 PH 页面评论区 + 其差评/退款讨论",
    "lobsters": "该讨论帖的评论区（Lobsters 评论质量高，适合问技术细节）",
    "stackoverflow": "该 tag 下的高浏览问题评论区 + 未回答问题的提问者",
    "github_trending": "相关仓库的 Issues / Discussions（找 workaround 与抱怨）",
    "github_search": "同类项目的 Issues（尤其 labeled bug/feature-request）",
    "devto": "文章评论区 + 作者本人的联系方式",
    "lesswrong": "该帖评论区（适合问方法论质疑，不适合问采购）",
    "indeed": "同类招聘帖的公司（说明有人出钱做这件事）→ 找该岗位负责人",
    "upwork": "同类岗位的发包方（已经在为这件事付钱的人）",
    "twitter": "相关讨论串的参与者",
    "xiaohongshu": "相关笔记的评论区（中文消费场景）",
}
# 无平台证据时的兜底渠道
FALLBACK = "竞品差评区（G2 / Capterra / Trustpilot / 应用商店）+ 相关行业微信群/论坛"

QUESTIONS = [
    ("现状", "你们现在怎么处理这件事？用什么工具、还是纯手工？"),
    ("痛感", "上一次因为它出问题是什么时候？造成什么后果？"),
    ("已付费行为", "有没有为它花过钱（工具/外包/人力）？大概多少？"),
    ("WTP", "如果有个东西能解决它，你愿意每月付多少？"),
    ("决策链", "这类支出谁拍板？走什么流程？"),
]

DM_EN = """Hi {name} — I saw your post about {topic} ({url}).
I'm researching how teams actually handle this today (not selling anything).
Three quick questions if you have 2 minutes:
1) What do you use for it now, and what breaks?
2) Have you paid for a tool or contractor for this? Roughly how much?
3) If something solved it end-to-end, what would it be worth per month to you?
Happy to share what I learn from others — thanks!"""

POST_EN = """Ask HN: How do you handle {topic} today?

I keep running into the same problem: {pain_one_line}

Before building anything I want to understand the current reality, so:
- What do you use now?
- What have you actually paid for (tool, contractor, headcount)?
- What would make you switch?

I'll summarise everything I learn in the thread."""

DM_ZH = """你好，我看到你关于{topic}的帖子（{url}）。
我在调研大家现在实际怎么处理这件事，不推销。
想请教三个问题（两分钟即可）：
1）你现在用什么方式做？哪里最卡？
2）有没有为它花过钱（工具/外包/人力）？大概多少？
3）如果有产品能完整解决，你觉得每月值多少钱？
我会把调研结论同步给你，谢谢！"""


def _communities(row):
    out = []
    for src in row.get("native_sources") or []:
        c = COMMUNITY.get(src)
        if c:
            out.append(f"{src} → {c}")
    if not out:
        out.append(f"（无原生平台证据）{FALLBACK}")
    return out


def _ascii_ratio(x):
    return sum(1 for c in (x or "") if ord(c) < 128) / max(len(x or ""), 1)


def _evidence(row):
    """取一条代表性证据：英文标题（给英文脚本用）、原文片段（当痛点描述）、原帖链接。"""
    items = row.get("items") or []
    titles = [(r.get("title") or "").strip() for r in items]
    texts = [" ".join((r.get("text") or "").split()) for r in items]
    links = [r.get("url") for r in items if r.get("url")]
    topic_en = next((t for t in titles if len(t) > 15 and _ascii_ratio(t) > 0.85), "")
    topic_zh = row.get("name", "")
    # 痛点描述优先用证据正文（作者的原话），不要用趋势理由（那是我的分析，不是当事人的话）
    pain = next((t for t in texts if _ascii_ratio(t) > 0.85 and len(t) > 40), "")
    if not pain:
        pain = next((t for t in texts if len(t) > 40), "")
    return topic_en, topic_zh, pain[:170], (links[0] if links else "")


def build_kit(row, window_label):
    """为一个方向生成验证包。返回 Markdown 行列表 + 结构化 dict。

    脚本里必须用**当事人自己的原话**（证据正文）当痛点描述，不能用我的分析结论——
    否则发出去像推销，对方第一句就看出来你不是在调研。
    """
    topic_en, topic_zh, pain, ref_url = _evidence(row)
    topic_en = topic_en or topic_zh
    topic = f"{topic_zh}（{topic_en}）" if topic_en and topic_en != topic_zh else topic_zh
    kit = {
        "direction": row.get("name"),
        "window": window_label,
        "target": row.get("who_pays") or "见建议结论中的付费方",
        "communities": _communities(row),
        "questions": QUESTIONS,
        "criteria": {
            "pass": "≥2 个独立受访者已在为此付费，或给出明确预算",
            "pending": "1 个受访者符合上述标准",
            "reject": "0 个受访者符合（记录原因：不需要 / 已有免费替代 / 不愿付费）",
        },
        "budget": "5 个受访者 / 3 天内；受访者必须来自 ≥2 个不同社区（避免同温层）",
        "scripts": {"dm_en": DM_EN, "post_en": POST_EN, "dm_zh": DM_ZH},
        "topic": topic, "topic_en": topic_en, "topic_zh": topic_zh,
        "pain_one_line": pain or "（先读证据原帖，摘一句当事人的原话填在这里）",
        "ref_url": ref_url or "（填证据原帖链接）",
    }
    L = [f"**{row['name']}**　建议档位：{row.get('advice', '—')}　趋势：{row.get('trend_level', '—')}",
         "",
         f"- **验证目标**：{kit['target']}",
         f"- **去哪问**：" + "；".join(kit["communities"])]
    if row.get("evidence_links"):
        L.append("- 先读这些原帖（含具体抱怨）：" + " · ".join(
            f"[{e['title'][:36]}]({e['url']})" for e in row["evidence_links"][:3]))
    L.append("- **问什么**（五问，按顺序问，别跳）：")
    for i, (k, q) in enumerate(QUESTIONS, 1):
        L.append(f"  {i}. [{k}] {q}")
    L += ["- **怎么判定**：",
          f"  - 通过 = {kit['criteria']['pass']}",
          f"  - 待续 = {kit['criteria']['pending']}",
          f"  - 否决 = {kit['criteria']['reject']}",
          f"- **样本与时间盒**：{kit['budget']}",
          "", "<details><summary>可直接复制的脚本（DM / 发帖，中英双语）</summary>", "",
          "```text", DM_EN.format(name="<对方名字>", topic=kit["topic_en"],
                                  url=kit["ref_url"]), "```", "",
          "```text", POST_EN.format(topic=kit["topic_en"],
                                    pain_one_line=kit["pain_one_line"]), "```", "",
          "```text", DM_ZH.format(topic=kit["topic_zh"], url=kit["ref_url"]), "```", "",
          "</details>", ""]
    return L, kit


def build_kits(rows_by_window, min_level=3):
    """对所有够格的方向生成验证包：建议档位 ≥min_level（★值得看及以上）。"""
    md, kits, seen = [], [], set()
    for label, rows in rows_by_window.items():
        # 同一方向会在多个窗口出现，验证包只出一份（取最早出现的窗口=最新的今日）。
        # 否则报告里同一个方向会重复三遍（实测踩过），既啰嗦又显得没去重。
        sel = [r for r in rows
               if (r.get("advice_level") or 0) >= min_level and r["name"] not in seen]
        if not sel:
            continue
        md += [f"### {label} 待验证方向（{len(sel)} 个）", ""]
        for r in sel:
            seen.add(r["name"])
            L, kit = build_kit(r, label)
            md += L
            kits.append(kit)
    return md, kits


# ------------------------------------------------------------------ 台账
def load_log():
    if not os.path.isfile(LOG):
        return {"records": []}
    with open(LOG, encoding="utf-8") as f:
        return json.load(f)


def save_log(d):
    os.makedirs(OUT, exist_ok=True)
    with open(LOG, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def add_record(direction, window, result, intents, note="", urls=None, date=None):
    """记一条验证结果。result: pass / pending / reject / resurrect(误杀复活)。"""
    d = load_log()
    rec = {"date": date or time.strftime("%Y-%m-%d"),
           "direction": direction, "window": window, "result": result,
           "paid_intents": int(intents or 0), "note": note,
           "urls": urls or [], "logged_at": int(time.time())}
    d.setdefault("records", []).append(rec)
    save_log(d)
    return rec


def stats(days=7):
    """北极星与误杀率。北极星 = 近 N 天"验证通过"的方向数（去重）。"""
    d = load_log()
    cut = time.time() - days * 86400
    recent = [r for r in d.get("records", []) if r.get("logged_at", 0) >= cut]
    passed = sorted({r["direction"] for r in recent if r["result"] == "pass"})
    pend = sorted({r["direction"] for r in recent if r["result"] == "pending"})
    rej = sorted({r["direction"] for r in recent if r["result"] == "reject"})
    resu = sorted({r["direction"] for r in recent if r["result"] == "resurrect"})
    denom = len(rej) + len(resu)
    return {
        "window_days": days,
        "north_star": len(passed),          # 北极星：近 N 天验证通过方向数
        "target": 1,                        # 目标：每周 ≥1
        "passed": passed, "pending": pend, "rejected": rej, "resurrected": resu,
        "mistake_rate": (len(resu) / denom) if denom else None,   # 误杀率（近似）
        "total_records": len(d.get("records", [])),
    }


def pending_queue(rows_by_window, min_level=3):
    """待验证队列：够格但台账里还没有记录的方向。"""
    d = load_log()
    done = {(r["direction"]) for r in d.get("records", []) if r["result"] != "pending"}
    q, seen = [], set()
    for label, rows in rows_by_window.items():
        for r in rows:
            # 同一方向在多个窗口都会出现：只留第一次（窗口顺序=由近及远），
            # 否则队列里会出现同一个方向的 3 条重复项（实测踩过）。
            if ((r.get("advice_level") or 0) >= min_level
                    and r["name"] not in done and r["name"] not in seen):
                seen.add(r["name"])
                q.append({"direction": r["name"], "window": label,
                          "advice": r.get("advice", ""), "trend": r.get("trend_level", "")})
    return q
