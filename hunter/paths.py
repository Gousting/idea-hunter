# -*- coding: utf-8 -*-
"""证据获取路径 —— 判断"多平台共振"是真共振还是假共振。

为什么必须有这个模块（P0-1 的核心）：
原先的"信源多样性/多平台共振"只看**平台名字有几个**，但同一个平台可以有两种
完全不同的取数方式：
  · 原生榜单（platform）：排序由平台决定（热榜、tag 页、subreddit 热帖）——
    多方命中说明"不同平台的人各自在关注"，这是**独立发现**。
  · 关键词检索（keyword）：排序由**我预设的查询词**决定（Algolia 搜 "willing to pay"、
    Indeed 搜 "automation"）——多方命中只说明"我的查询词在多个平台都能捞到东西"，
    这是**同一个查询的回声**，不是独立性。
实测：留存证据里关键词检索占 76%、原生榜仅 24%（HN 一路 Algolia 51 条 vs 原生榜 1 条）。
所以共振必须只统计原生榜、且互不共享查询词（原生榜天然无共享查询词），
关键词命中只能作为"需求证据"，不能作为"共振证据"。

------------------------------------------------------------------ 2026-09-18 修复
原先 infer() 的兜底分支是 `return PLATFORM` —— 默认值取的是**对自己有利**的那一侧：
任何新接入、忘了写 path 的信源，都会白拿"原生榜（真独立发现）"的身份，直接抬高
「原生榜贡献率 ≥40%」这个头条验收指标。默认值本该取保守侧。

改法两条（不改变已有正确分类，只是不再"默认发身份"）：
  1. 兜底改为 `return KEYWORD`。新信源必须**显式登记** SOURCE_PATH 才能算原生。
  2. 未登记的信源会被 undeclared() 列出来，并在报告里如实披露条数 ——
     这样"原生率"是一个可审计的数字，而不是一个由遗漏决定的数字。

另设 WEAK_NATIVE 标记：这类源排序确实由平台给，但**入池门槛或榜单范围由作者设定**
（github_search 的 created:>Nd stars:>M、reddit RSS 的子版块清单、browser 的站点清单）。
它们比 github_trending 这种纯算法榜弱一档。只影响展示口径（报告里单独标注），
不影响归类 —— 标出来是为了让读者知道"原生率里有多少来自弱原生"。
"""
PLATFORM = "platform"   # 平台原生榜单 / 标签页 / 热榜（排序由平台决定）
KEYWORD = "keyword"     # 预设查询词命中（排序由我的查询决定）
DEEP = "deep"           # 评论区深读（源自平台榜单，算原生家族）

NATIVE_FAMILY = (PLATFORM, DEEP)

# 这些源**只有**关键词检索形态（没有可用的原生热榜通道）
KEYWORD_SOURCES = {"indeed", "twitter", "xiaohongshu", "upwork"}

# 这些源有原生热榜形态，且各自的热度门槛（低于门槛不进热点证据）。
# 门槛按各站热度量纲定：HN 是点数、lobsters 是点数、lesswrong/devto 是评论数、
# SO 是浏览+回答、Product Hunt 只有排名代理（125=第1名，仅前 6 名进）。
# zhihu **不在列表内**：实测其热榜是新闻榜（体育/娱乐/股票），
# 对软件选品零价值，放进来只会用噪音稀释信号——这是主动排除，不是遗漏。
HOT_MIN = {"hn": 40, "reddit": 60, "lobsters": 30, "devto": 15,
           "lesswrong": 60, "stackoverflow": 60,
           "producthunt": 95, "browser": 20,
           # 两个免登录弱等效源：热度是代理值（juejin=浏览+点赞×3、
           # bluesky=排名代理），门槛按代理值量纲定，别照搬点数阈值
           "juejin": 60, "bluesky": 30}

LABEL = {PLATFORM: "原生榜", KEYWORD: "关键词检索", DEEP: "评论深读"}

# ---------------------------------------------------------------- 显式登记表
# 没有登记的源一律按 KEYWORD（保守）。新增信源时必须在这里登记，
# 否则它会静默降级为关键词检索 —— 这是刻意的：漏登记应当导致指标变保守，
# 而不是导致指标变好看。
SOURCE_PATH = {
    # GitHub Trending 是 GitHub 自己的算法榜（时间衰减 + 活跃度，无查询词）
    "github_trending": PLATFORM,
    # GitHub Search：查询 `created:>Nd stars:>M` 由作者参数化 → 弱原生（见 WEAK_NATIVE）
    "github_search": PLATFORM,
    # Issues 深挖：`repo:X is:issue comments:>N sort=comments` —— 仓库与门槛都是我选的，
    # 属于"我的查询决定排序"，如实记为关键词检索（它另有高信源权重 4.0，是另一条轴）
    "github_issue": KEYWORD,
    # Reddit RSS：hot/top 的排序由平台决定，但子版块清单是手选的 → 弱原生
    "reddit": PLATFORM,
    # 浏览器通道：读站点的列表页，排序由站点给，但站点清单是手选的 → 弱原生
    "browser": PLATFORM,
    # HN：Algolia 检索的记录自带 path=keyword（见 sources.hn_pain_points）；
    # opencli 的 show/ask 是原生榜。所以这里给 PLATFORM，检索侧靠自带 path 覆盖。
    "hn": PLATFORM,
    # 以下均为 opencli 原生热榜/标签页（_norm 显式传 path="platform"）
    "lobsters": PLATFORM, "devto": PLATFORM, "lesswrong": PLATFORM,
    "stackoverflow": PLATFORM, "producthunt": PLATFORM, "juejin": PLATFORM,
    "bluesky": PLATFORM, "zhihu": PLATFORM,
}

# 「弱原生」：排序确实由平台给，但入池门槛/榜单范围由作者设定。
# 只用于展示口径（报告里单独标注弱原生条数），不影响 is_native 的判定。
WEAK_NATIVE = {"github_search", "reddit", "browser"}


def infer(rec):
    """取记录的获取路径；没有显式声明时**按保守侧**推断。

    推断顺序（按可靠度）：
      · 记录自带 path 字段 → 直接用它（采集点声明优先，可审计）
      · 有 comment_score_sum/comment_count → 评论区深读
      · HN 有 query 字段 → Algolia 关键词检索；无 query → opencli 原生热榜
      · 在 SOURCE_PATH 登记表里 → 用登记值
      · 其余 → KEYWORD（保守兜底；**不再默认发"原生榜"身份**）
    """
    p = rec.get("path")
    if p:
        return p
    src = rec.get("source")
    if rec.get("comment_score_sum") is not None or rec.get("comment_count") is not None:
        return DEEP
    if src == "hn":
        return KEYWORD if rec.get("query") else PLATFORM
    if src in SOURCE_PATH:
        return SOURCE_PATH[src]
    return KEYWORD


def is_native(rec):
    """能否作为"独立发现"的证据（原生榜或源自原生榜的评论深读）。"""
    return infer(rec) in NATIVE_FAMILY


def is_weak_native(rec):
    """弱原生（门槛由作者设定）—— 报告里单独标注，避免把原生率读得过硬。"""
    return is_native(rec) and rec.get("source") in WEAK_NATIVE


def counts(records):
    """返回 (原生家族条数, 关键词条数, 原生榜贡献率)。"""
    n_kw = sum(1 for r in records if infer(r) == KEYWORD)
    n_nat = len(records) - n_kw
    return n_nat, n_kw, (n_nat / len(records) if records else 0.0)


def undeclared(records):
    """未登记获取路径的信源（会被保守地算作关键词检索）。

    为什么要单独返回：这是给**作者**看的自检信号 —— 新增信源忘了登记时，
    指标会变保守而不是变好看，但也不能让它静默发生。报告里如实披露条数。
    """
    seen = {}
    for r in records:
        src = r.get("source")
        if not src or r.get("path") or src in SOURCE_PATH or src == "hn":
            continue
        seen[src] = seen.get(src, 0) + 1
    return seen


def breakdown(records):
    """按信源给出原生/关键词/弱原生条数 —— 让"原生率"这个头条指标可被读者审计。

    返回 [{source, native, keyword, weak}]，按原生条数降序。
    """
    agg = {}
    for r in records:
        src = r.get("source") or "?"
        a = agg.setdefault(src, {"source": src, "native": 0, "keyword": 0, "weak": 0})
        if is_native(r):
            a["native"] += 1
            if is_weak_native(r):
                a["weak"] += 1
        else:
            a["keyword"] += 1
    return sorted(agg.values(), key=lambda x: (-x["native"], x["source"]))
