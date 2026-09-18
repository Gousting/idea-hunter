# -*- coding: utf-8 -*-
"""平台优先视图：各平台在热什么，再跨平台汇总。

为什么需要这个模块（用户提的架构问题）：
原先所有数据都要先过「痛点/付费构式」门槛，过不了就丢，再塞进 28 个预设方向。
结果是 lobsters / devto / 知乎 / LessWrong 的热榜几乎一条都留不下来（实测 0 条），
用户看到的是"我预设方向的证据"，而不是"各平台在热什么"。

本模块走**独立的第二条轨道**：
  不做需求门槛、不做方向归类，直接按**平台原生热度**排序，以平台为单位呈现。

关键设计：热度口径必须按平台定制 —— 各站的"热"不是同一个量：
  HN / Lobsters  : 点数（认同）×2 + 评论数（讨论规模）×3
  DEV.to / LW    : 评论数×3（这两站没公开点数）
  知乎            : 回答数
  Stack Overflow : 浏览数 + 回答数×10（没人回答的高浏览问题才是真痛点）
  Product Hunt   : 投票数
  GitHub         : 日均涨星
  Reddit         : 评论赞同合计 + 评论数×3
统一口径会把量纲不同的东西相加，那是假精确。
"""
import math
import re

# 英文停用词（只做主题词提取，不求穷尽）
STOP = set("""
a an the and or but if then than that this these those is are was were be been being
to of in on for with without from by as at into over under about after before
you your we our they their it its his her he she i me my mine us them
how why what when where which who whom whose will would can could should may might must
do does did done doing have has had having not no nor so such only own same too very
just now also more most other some any all both each few many much
new use used using make makes made get gets got getting one two three
via via get got let lets still even ever never always
show ask tell need want like good bad best better
hn show-hn ask-hn
""".split())

# 无意义的通用词（出现在任何一个技术平台热榜里都不构成"主题"）
GENERIC = set("""
llm llms ai model models tool tools app apps data code software project release
version update updated week month year today day time thing things stuff people
work working works way ways make making made need needs needed help question
api dev google remote everybody something anything anything everything
first second third last next new old good better best
anyone anybody built made make give take look looks really actually
still even much less least lot bit kind sort etc
""".split())

# 缩写残留（"don't"→don、"isn't"→isn 这类会被切出来当主题词，实测混进过结果）
CONTRACTIONS = set("""
don doesn didn isn aren wasn weren hasn haven hadn won wouldn couldn shouldn
can cant won wont that thats there theres youre youve youll theyre theyve
im ive ill id lets its hes shes whats hows whos
""".split())


def _en_tokens(text):
    toks = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", (text or "").lower())
    return [t for t in toks
            if t not in STOP and t not in GENERIC and t not in CONTRACTIONS
            and len(t) >= 3 and not t.endswith("n't")]


# 中文功能词 n-gram（滑窗会切出这些，但它们不构成主题）
ZH_STOP = set("""什么 怎么 如何 为何 为什么 怎么样 可以 我们 他们 她们 你们 自己
现在 已经 一个 这个 那个 这些 那些 不是 没有 就是 还是 因为 所以 但是 而且
如果 这样 那样 一直 一下 时候 事情 问题 感觉 觉得 真的 好像 然后 其实 可能
应该 需要 比较 非常 特别 只是 不过 很多 有些 全部 所有 以及 关于 对于 通过
看待 何看 如何看 何看待 是什么 有哪些 怎么样 是什么 意味着 引发 热议 回应 宣布
""".split())


def _zh_ngrams(text):
    """中文按 2-3 字滑窗取词。没有分词库，只能这样——粗糙但可复算，
    且只用于"跨平台主题发现"这个粗粒度用途，不用于结论。"""
    chars = re.findall(r"[\u4e00-\u9fff]+", text or "")
    out = []
    for seg in chars:
        for n in (2, 3):
            for i in range(len(seg) - n + 1):
                g = seg[i:i + n]
                if g not in ZH_STOP:
                    out.append(g)
    return out


def heat_of(source, r):
    """平台原生热度。口径按站定制 —— 见模块 docstring。"""
    h = r.get("heat") or {}
    score = h.get("score") or r.get("score") or r.get("points") or r.get("ups") or 0
    com = h.get("comments") or r.get("comments") or r.get("num_comments") or 0
    cscore = h.get("comment_score") or r.get("comment_score_sum") or 0
    try:
        score, com, cscore = int(score), int(com), int(cscore)
    except Exception:
        score = com = cscore = 0

    if source == "reddit":
        return cscore + com * 3
    if source in ("hn", "lobsters"):
        return score * 2 + com * 3
    if source in ("devto", "lesswrong"):
        return com * 3 + score
    if source == "zhihu":
        # 知乎有中文单位热度（"1160 万热度"），没有就退回回答数
        return int(h.get("heat_num") or 0) or int(h.get("answers") or 0) * 10
    if source == "stackoverflow":
        return int(h.get("views") or 0) + int(h.get("answers") or 0) * 10
    if source == "producthunt":
        # PH 的 today 榜**不返回票数**（只有 rank），只能用排名做代理——
        # 这不是真热度，是序数，所以标注在报告口径里。
        v = int(h.get("votes") or 0)
        if v:
            return v * 5
        rank = int(h.get("rank") or 0)
        return max(1, 26 - rank) * 5 if rank else 0
    if source in ("github_trending", "github_search"):
        return int(r.get("star_velocity") or r.get("stars_window") or r.get("stars_total") or 0)
    if source in ("twitter", "xiaohongshu"):
        return int(score) * 2 + com * 3
    if source == "indeed":
        return 0  # 招聘帖没有讨论热度，它属于需求证据轨道
    if source == "browser":
        return score * 2 + com * 3
    return score * 2 + com * 3


def hot_by_platform(records, per_platform=6):
    """按平台分组，各取热度 top N。返回 [(source, [recs])]。"""
    by = {}
    for r in records:
        src = r.get("source")
        if not src or r.get("error"):
            continue
        r["_heat"] = heat_of(src, r)
        by.setdefault(src, []).append(r)
    out = []
    for src, items in by.items():
        items.sort(key=lambda x: -x["_heat"])
        out.append((src, items[:per_platform]))
    out.sort(key=lambda kv: -sum(x["_heat"] for x in kv[1]))
    return out


def platform_terms(platform_hot, top_k=6):
    """每个平台自己的高频主题词 —— "这个平台在热什么"的直接答案。

    为什么要单独算：跨平台交叉需要足够大的样本，而热榜每条标题只有几个词，
    实测每平台 6 条时全库 182 个词里**没有一个跨平台出现**。所以先给出
    平台内的高频词（可用性好），跨平台交叉作为附加信息（有则报，无则说无）。
    """
    out = {}
    for src, items in platform_hot:
        cnt = {}
        for r in items:
            text = f"{r.get('title') or ''} {r.get('topic_text') or ''}"
            for t in set(_en_tokens(text)) | set(_zh_ngrams(text)):
                cnt[t] = cnt.get(t, 0) + 1
        out[src] = sorted(cnt.items(), key=lambda kv: -kv[1])[:top_k]
    return out


def cross_topics(platform_hot, min_platforms=2, top_k=12):
    """跨平台主题：同一个关键词出现在 ≥2 个平台才算"共振主题"。

    这是数据驱动的汇总（不预设主题表），但必须承认它是**粗粒度关键词法**：
    同义不同词不会被合并，中文用 n-gram 会有碎词。只用于"哪里在共振"的提示。
    """
    topic_plat = {}   # 词 -> {平台: 平台内热度合计}
    for src, items in platform_hot:
        for r in items:
            text = f"{r.get('title') or ''} {r.get('topic_text') or ''}"
            for t in set(_en_tokens(text)) | set(_zh_ngrams(text)):
                topic_plat.setdefault(t, {})
                topic_plat[t][src] = topic_plat[t].get(src, 0) + max(r["_heat"], 1)
    rows = []
    for t, plats in topic_plat.items():
        if len(plats) >= min_platforms:
            rows.append({"topic": t, "platforms": sorted(plats),
                         "n_platforms": len(plats),
                         "heat": sum(plats.values())})
    rows.sort(key=lambda x: (-x["n_platforms"], -x["heat"]))
    return rows[:top_k]


def render_markdown(platform_hot, topics, label, collected_n, terms=None):
    """平台为主的报告：每个平台一段热点榜，最后跨平台主题。"""
    L = [f"# 各平台热点汇总 · {label}", "",
         f"（本窗口采集 {collected_n} 条；**不做需求门槛、不做方向归类**，"
         f"直接按平台原生热度排序——这一节回答的是\"各平台在热什么\"，"
         f"不是\"哪些方向有需求\"）", "",
         "> 热度口径按平台定制：HN/Lobsters=点数×2+评论×3；DEV.to/LessWrong=评论×3；"
         "知乎=回答数；SO=浏览数+回答×10；Product Hunt=投票×5；GitHub=日均涨星。"
         "各站量纲不同，**跨平台只比排名不比数值**。", ""]
    terms = terms or {}
    for src, items in platform_hot:
        L += [f"## {src}（{len(items)} 条）", ""]
        if terms.get(src):
            L.append("平台高频词：" + "、".join(f"{t}（{n}）" for t, n in terms[src]))
            L.append("")
        L += [
              "| # | 标题 | 平台热度 | 链接 |", "|---:|---|---:|---|"]
        for i, r in enumerate(items, 1):
            t = (r.get("title") or "").replace("|", "/")[:76]
            L.append(f"| {i} | {t} | {r['_heat']} | [打开]({r.get('url', '')}) |")
        L.append("")
    L += ["## 跨平台主题（出现在 ≥2 个平台的关键词）", ""]
    if not topics:
        L += ["_本轮各平台热榜**没有词汇交叉**：每平台标题只有几个词，样本量不足以"
              "支撑跨平台词频重合。要看共振，要么扩大每平台样本（--limit 提高到 25），"
              "要么改用语义聚类（把同义不同词合并）——关键词法在这里已到上限。_", ""]
    else:
        L += ["关键词法，粗粒度：同义不同词不会合并，中文用 n-gram 会有碎词。"
              "它的价值是提示\"哪里在共振\"，不是下结论。", "",
              "| 主题 | 平台数 | 出现平台 | 热度合计 |", "|---|---:|---|---:|"]
        for t in topics:
            L.append(f"| **{t['topic']}** | {t['n_platforms']} | "
                     f"{'、'.join(t['platforms'])} | {t['heat']} |")
        L.append("")
    return "\n".join(L)
