# -*- coding: utf-8 -*-
"""平台依赖对冲：能力级覆盖矩阵 + 失败回填 + 合规登记。

为什么按"能力"而不是按"源"组织（P0-3 的核心视角）：
用户要的不是"45 个源里 40 个成功"，而是"我需要的能力有没有拿到数据"。
一个源失败不等于能力缺失——只要等效源还在，能力就是 covered。
反过来，源成功率 95% 但唯一提供某能力的源挂了，那才是真缺口。

实测背景（2026-09-18）：
  · GummySearch 在 $35K MRR / 1 万付费用户的盈利状态下被 Reddit API 政策逼停，
    2026-12 删库；Reddit 2026-05 起对未认证 .json 访问返 403。
  · 我们自己的 upwork 通道 100% 失败（4/4），twitter 需登录（2/2），xhs 超时。
  · 三个失败源里有三个**恰好是付费需求与创始人原话**这两个最值钱的能力 → 必须对冲。

对冲动作：
  1. 付费需求 → github_bounties（免登录，金额写在 issue 里）+ r/forhire（官方 RSS）
  2. 中文需求 → juejin hot（免登录，弱等效：偏技术，非消费社区）
  3. 创始人原话 → bluesky trending（免登录，**弱等效**：只有热门话题且偏新闻，不能搜帖）
  4. 已知不可用的源默认跳过而不计入失败（跳过≠失败，否则失败率被永久污染）

关于"弱等效"的诚实标注：弱等效只保证"这条能力不至于完全空白"，
不保证质量等价。报告里逐条标出弱在哪，不做成"已覆盖"就完事。
"""
import time

# 能力 → 主源 / 等效源（免登录优先）/ 说明
CAPABILITIES = {
    "开源供给（在做什么）": {
        "primary": ["github_trending", "github_search"],
        "equivalent": [],
        "note": "官方 API + 公开页面，无登录依赖",
    },
    "技术讨论与痛点原话": {
        "primary": ["hn", "lobsters", "devto", "lesswrong"],
        "equivalent": [],
        "note": "全部免登录（HN Algolia 公开搜索 / Lobsters / DEV.to / LessWrong）",
    },
    "付费需求（有人出钱做事）": {
        "primary": ["upwork", "indeed"],
        "equivalent": ["github_bounties", "reddit:forhire"],
        # 等价源名必须与 _logical() 的产出完全一致，否则明明采到了却算缺口（实测踩过）
        "note": "主源都要登录态且 upwork 100% 失败；等效源免登录且金额可核（赏金写在 issue 里）",
    },
    "创始人原话与发声": {
        "primary": ["reddit", "twitter"],
        "equivalent": [],
        "weak": ["bluesky:trending"],
        "note": "reddit 有官方 RSS 免登录通道；twitter 需登录 → bluesky 仅弱等效（无关键词搜帖）",
    },
    "中文需求信号": {
        "primary": ["xiaohongshu"],
        "equivalent": ["juejin:hot"],
        # zhihu 单列：它能"采到数据"但实测是新闻榜，对软件选品零价值——
        # 覆盖 ≠ 有价值，所以它不算真覆盖（否则会掩盖"中文需求其实是空的"）。
        "weak": ["zhihu"],
        "note": "xhs 需登录且常超时；zhihu 采得到但零价值（新闻榜）；juejin 免登录但偏技术（弱等效）",
    },
    "新发布产品（竞品情报）": {
        "primary": ["producthunt"],
        "equivalent": [],
        "note": "仅有公开页面通道；无等效源（潜在单点）",
    },
}

# 源 → 机制与合规状态（如实登记，不美化）
COMPLIANCE = {
    "github_trending": ("官方公开页面", "低"),
    "github_search": ("官方 API（未认证，有速率限制）", "低"),
    "github_bounties": ("官方 API 搜索（label:bounty）", "低"),
    "hn": ("Algolia 公开搜索 API / 官方页面", "低"),
    "lobsters": ("公开页面 / 公开 API", "低"),
    "devto": ("公开 API", "低"),
    "lesswrong": ("公开 API", "低"),
    "stackoverflow": ("公开页面", "低"),
    "juejin:hot": ("公开页面", "低-中"),
    "bluesky:trending": ("公开 API（AT Protocol）", "低"),
    "reddit": ("官方 RSS（/r/x/.rss，个人研究用）+ 登录态读帖", "中"),
    "producthunt": ("公开页面（登录态交互）", "中"),
    "indeed": ("浏览器登录态 + 页面渲染", "中-高"),
    "upwork": ("浏览器登录态", "中-高"),
    "twitter": ("浏览器登录态", "中-高"),
    "xiaohongshu": ("浏览器登录态", "中-高"),
    "zhihu": ("浏览器登录态", "中-高"),
}

# 已知不可用 / 需人工恢复的源：默认跳过（跳过≠失败，否则失败率被永久污染）
SKIP_DEFAULT = {
    "upwork": "适配器侧故障（多次 exitCode 1，与站点改版有关）→ 已由 github_bounties + r/forhire 覆盖",
    "twitter": "需在 Chrome 登录 X 后可用 → 登录即恢复，当前由 bluesky:trending 弱覆盖",
}

# 逻辑源名归一（health 里的 source 带查询前缀，如 opencli:indeed[automation]）
def base_of(src):
    """把 health 里的源名归一成能力表里的逻辑名。

    坑：health 里的名字带窗口/查询后缀（github_trending:daily、github_search:3d、
    opencli:hn:show），不剥干净就会让"开源供给"这类能力永远匹配不上、被误判成缺口。
    """
    s = (src or "").split("[")[0]
    if s.startswith("opencli:"):
        s = s[len("opencli:"):]
    if s.startswith("github_count") or s.startswith("github_mature"):
        return "github_count"
    if s.startswith("github_bount"):
        return "github_bounties"
    if s.startswith("bluesky"):
        return "bluesky"
    if s.startswith("juejin"):
        return "juejin"
    # 只保留第一段（github_trending / github_search / hn / reddit ...）
    return s.split(":")[0]


def _logical(src):
    """把 health 的 source 名映射到能力表里用的逻辑名。"""
    b = base_of(src)
    low = (src or "").lower()
    if b == "reddit" and "forhire" in low:
        return "reddit:forhire"
    if b == "github_search" and "bount" in low:
        return "github_bounties"
    if "bluesky" in low:
        return "bluesky:trending"
    if "juejin" in low:
        return "juejin:hot"
    return b


def assess(health):
    """按能力评估覆盖状态：covered / degraded / lost。

    规则：
      · 能力的任一源成功 → 该能力 covered（degraded 若成功的只是弱等效）
      · 全部失败 → lost
      · 被跳过的源（SKIP_DEFAULT）不计为失败，单独列出
    """
    ok_of, fail_of, skip_of = {}, {}, {}
    for h in health:
        name = _logical(h.get("source"))
        cnt = h.get("count", 0)
        # 显式标记跳过的条目直接进 skip（不再靠"失败且从未成功"去猜）
        if h.get("skipped"):
            skip_of[name] = skip_of.get(name, 0) + 1
            continue
        if (not h.get("ok")) and cnt == 0:
            fail_of[name] = fail_of.get(name, 0) + 1
        else:
            # 计"该源成功了第几次"，**不是**采到了几条。
            # 原先用 max(cnt,1) 累加，分母被采集条数放大，失败率被稀释成 0%——
            # 实测踩过：xhs 两个窗口全挂，硬失败率却显示 2%→0%。这是指标自我美化，
            # 分母口径必须与分子（失败次数）同级：都是"源次"。
            ok_of[name] = ok_of.get(name, 0) + 1
    for k in SKIP_DEFAULT:
        if k in fail_of and k not in ok_of:
            skip_of[k] = fail_of.pop(k)

    rows = []
    for cap, spec in CAPABILITIES.items():
        weak = spec.get("weak") or []
        prim_ok = [s for s in spec["primary"] if s in ok_of]
        prim_fail = [s for s in spec["primary"] if s in fail_of and s not in prim_ok]
        eq_ok = [s for s in spec["equivalent"] if s in ok_of]
        weak_ok = [s for s in weak if s in ok_of]
        removed = [s for s in spec["primary"] if s in skip_of]
        if prim_ok:
            state = "covered"
        elif eq_ok:
            state = "degraded"      # 主源不可用，等效源撑着
        elif weak_ok:
            state = "degraded"      # 只有弱源（能采到但价值低）→ 也算降级
        else:
            state = "lost"
        eq_ok = eq_ok + [f"{w}(弱)" for w in weak_ok]
        rows.append({
            "capability": cap, "state": state,
            "primary_ok": prim_ok, "primary_failed": prim_fail,
            "skipped": removed, "equivalent_ok": eq_ok, "note": spec["note"],
        })

    total = len(rows)
    lost = sum(1 for r in rows if r["state"] == "lost")
    degraded = sum(1 for r in rows if r["state"] == "degraded")
    # 缺口 = 完全没拿到数据的能力占比（degraded 不算缺口，但有质量折扣）
    gap = lost / total if total else 0.0
    hard_fail = sum(fail_of.values())
    total_entries = hard_fail + sum(ok_of.values())
    return {
        "rows": rows, "n_capabilities": total, "lost": lost, "degraded": degraded,
        "gap_rate": gap, "hard_fail_entries": hard_fail,
        "fail_rate": hard_fail / total_entries if total_entries else 0.0,
        "skipped": skip_of,
    }


def summary_md(res, target_gap=0.20, target_fail=0.10):
    """报告章节：能力覆盖矩阵 + 失败率 + 合规登记。"""
    L = ["## 源健康与依赖对冲（P0-3）", "",
         f"**能力覆盖缺口 {res['gap_rate']:.0%}**（目标 <{target_gap:.0%}："
         f"{'✅ 达标' if res['gap_rate'] < target_gap else '❌ 未达标'}）　·　"
         f"**硬失败率 {res['fail_rate']:.0%}**（目标 <{target_fail:.0%}："
         f"{'✅ 达标' if res['fail_rate'] < target_fail else '❌ 未达标'}）", "",
         f"（能力 {res['n_capabilities']} 项：covered {res['n_capabilities']-res['lost']-res['degraded']} · "
         f"degraded {res['degraded']} · lost {res['lost']}｜"
         f"**跳过 {len(res['skipped'])} 个已知不可用源**，跳过不计失败——"
         "所以「失败率低」必须与「跳过几个」一起读，单看失败率是粉饰）", "",
         "> 口径：按**能力**而不是按源统计。一个源失败不等于能力缺失；"
         "唯一提供某能力的源挂了才是缺口。已知不可用的源（upwork/twitter）**跳过而不计入失败**——"
         "否则失败率被永久污染，真实退化会被掩盖。", "",
         "| 能力 | 状态 | 主源可用 | 主源失败 | 等效源撑着 | 已知跳过 | 说明 |",
         "|---|---|---|---|---|---|---|"]
    label = {"covered": "✅ 正常", "degraded": "⚠️ 降级（仅等效源）", "lost": "❌ 缺口"}
    for r in res["rows"]:
        L.append(f"| **{r['capability']}** | {label[r['state']]} | "
                 f"{'、'.join(r['primary_ok']) or '—'} | {'、'.join(r['primary_failed']) or '—'} | "
                 f"{'、'.join(r['equivalent_ok']) or '—'} | {'、'.join(r['skipped']) or '—'} | {r['note']} |")
    L += ["", "### 采集机制与合规登记", "",
          "| 源 | 采集机制 | 合规风险 |", "|---|---|---|"]
    for src, (mech, risk) in COMPLIANCE.items():
        L.append(f"| {src} | {mech} | {risk} |")
    L += ["", "> 风险判读：官方 API/RSS = 低；登录态自动化 = 中-高（可能违反站点自动化条款，"
          "且有账号风险）。**GummySearch 的前车之鉴**：它是在盈利状态（$35K MRR）下被"
          "Reddit API 政策逼停的，说明「业务健康」保护不了「依赖单一平台」这一结构性风险。", ""]
    if res["skipped"]:
        L += ["> 已跳过（待恢复）：" + "；".join(
            f"{k}——{v}" for k, v in res["skipped"].items()) + "", ""]
    return L
