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


def infer(rec):
    """取记录的获取路径；老缓存没有该字段时按字段特征推断。

    推断规则（按可靠度排序）：
      · 有 comment_score_sum/comment_count → 评论区深读
      · HN 有 query 字段 → Algolia 关键词检索；无 query → opencli 原生热榜
      · 只有检索形态的源 → 关键词检索
      · 其余 → 原生榜
    """
    p = rec.get("path")
    if p:
        return p
    src = rec.get("source")
    if rec.get("comment_score_sum") is not None or rec.get("comment_count") is not None:
        return DEEP
    if src == "hn":
        return KEYWORD if rec.get("query") else PLATFORM
    if src in KEYWORD_SOURCES:
        return KEYWORD
    return PLATFORM


def is_native(rec):
    """能否作为"独立发现"的证据（原生榜或源自原生榜的评论深读）。"""
    return infer(rec) in NATIVE_FAMILY


def counts(records):
    """返回 (原生家族条数, 关键词条数, 原生榜贡献率)。"""
    n_kw = sum(1 for r in records if infer(r) == KEYWORD)
    n_nat = len(records) - n_kw
    return n_nat, n_kw, (n_nat / len(records) if records else 0.0)
