# -*- coding: utf-8 -*-
"""
方向聚合层：把散的候选（帖子/issue/仓库）聚合成"可做的方向"，并按时间窗排名。

为什么需要这一层：
用户要的不是"12 条帖子"，而是"今天/本周/本月有哪些值得看的方向"。
一条帖子是噪音，同一个方向上有 N 条独立证据才是信号。

聚合方式：人工维护的方向 taxonomy（关键词签名）+ 打分。
为什么不用聚类算法：无监督聚类在几百条短文本上产物不稳定、方向名也不可读，
而"独立开发者能做的产品方向"本身是有限且可枚举的，用签名匹配更可控、可解释。

打分维度（都可追溯到具体的证据条数，不是黑箱）：
  evidence      该方向命中的候选条数
  diversity     信源多样性（不同信源数）—— 单一信源里反复出现的很可能是同温层
  wtp           带第一人称付费构式的条数
  supply        该方向在 GitHub 上的仓库热度（条数 + 日均涨星）
"""
import math
import re
import time

from . import paths as _paths   # 证据获取路径（原生榜 / 关键词检索 / 评论深读）

# (方向名, 关键词签名, GitHub 检索词)
# 注意：所有短词必须加 \b 词边界。踩过的坑——
#   `feed` 会命中 "feedback"、`rag` 会命中 "storage"、
#   `bi` 会命中 "billing"、`ci` 会命中 "pricing"…
# 词边界缺失会让方向归类大面积错乱，且错得很难察觉（列表看起来仍然"合理"）。
DIRECTIONS = [
    ("支付与账单", r"(stripe|paddle|lemonsqueezy|\bbilling\b|invoice|subscription|dunning|"
                r"checkout|payment|refund|\btax\b|\bvat\b|收款|账单)", "billing payment"),
    ("获客与 SEO", r"(\bseo\b|\bserp\b|backlink|keyword rank|organic traffic|landing page|"
                r"cold email|outbound|lead gen|acquisition|\bgrowth\b)", "seo analytics"),
    ("客服与工单", r"(helpdesk|support ticket|zendesk|intercom|customer support|"
                r"knowledge base|support bot)", "helpdesk support"),
    ("数据采集与解析", r"(scrap|crawl|data extraction|pdf extract|\bocr\b|\brss\b|"
                 r"feed reader|parsing|data mining)", "scraper parser"),
    ("AI 代理与自动化", r"(\bagents?\b|\bllms?\b|\bprompts?\b|\brag\b|embedding|\bmcp\b|"
                  r"workflow automat|automation|automate|orchestrat|"
                  r"function calling|tool use)", "llm agent"),
    ("自托管与部署", r"(self[- ]host|docker|kubernetes|\bdeploy|homelab|\bnas\b|"
                 r"compose|reverse proxy|\bvps\b|server setup)", "self-hosted deploy"),
    ("监控与可观测", r"(monitoring|observab|metric|uptime|\balert|logging|\bapm\b|"
                 r"tracing|status page)", "monitoring observability"),
    ("视频与音频处理", r"(video|ffmpeg|subtitle|caption|transcrib|transcription|podcast|"
                  r"\baudio\b|thumbnail|screen record)", "video ffmpeg"),
    ("邮件与通知", r"(\bsmtp\b|deliverab|email deliver|inbox|mailbox|"
                 r"notification|webhook|push notif)", "email smtp"),
    ("协作与项目管理", r"(project management|kanban|issue track|team collab|"
                  r"notion|slack|standup|sprint|\bcrm\b)", "project management"),
    ("电商与跨境", r"(shopify|amazon seller|etsy|product listing|inventory|dropship|"
                r"fulfill|storefront|product feed|cross[- ]border)", "ecommerce inventory"),
    ("内容创作与分发", r"(blog|\bcms\b|newsletter|content market|social schedul|"
                  r"repurpose|publishing|content calendar)", "cms publishing"),
    ("本地化与翻译", r"(\bi18n\b|\bl10n\b|translat|localiz|multi[- ]lang)", "i18n localization"),
    ("表单与调研", r"(form builder|survey|questionnaire|typeform|intake form)", "form survey"),
    ("财务与记账", r"(bookkeep|accounting|expense|receipt|reconcil|ledger|"
                r"cash flow|financial report)", "accounting expense"),
    ("招聘与 HR", r"(hiring|recruit|applicant|\bats\b|employee onboard|"
                r"payroll|\bhr\b tool)", "recruiting hr"),
    ("安全与合规", r"(\bgdpr\b|soc ?2|compliance|credentials?|vulnerab|"
                r"penetration|\bauth\b|\bsso\b|\bsbom\b)", "security compliance"),
    ("代码质量与 CI", r"(ci/cd|test coverage|\blint|code review|"
                  r"static analy|refactor|dependency|\bcve\b)", "ci code quality"),
    ("报表与可视化", r"(dashboard|reporting|\bbi\b|visuali[sz]|chart|spreadsheet|"
                 r"csv export)", "dashboard reporting"),
    ("用户反馈与留存", r"(churn|retention|user feedback|\bnps\b|feature request|"
                  r"product analytics)", "churn retention"),
    ("文档与知识库", r"(documentation|docs site|wiki|knowledge manage|"
                 r"readme|api docs|style guide)", "documentation docs"),
    ("集成与 API 网关", r"(integration|webhook sync|zapier|api gateway|"
                   r"middleware|connector|\betl\b|\bipaas\b)", "integration api"),
    ("文件与存储同步", r"(file sync|\bstorage\b|backup|dropbox|google drive|\bs3\b|"
                  r"file version|dedup)", "file sync backup"),
    ("价格与竞品情报", r"(pricing page|competitor|price monitor|market intel|"
                  r"track competitor|price track)", "pricing monitor"),
    ("时间与日程管理", r"(calendar|schedul|booking|appointment|time track|"
                  r"timesheet|reschedul)", "calendar scheduling"),
    ("浏览器扩展与效率", r"(browser extension|chrome extension|userscript|"
                   r"bookmark|tab manag|clipboard)", "browser extension"),
    ("终端与开发者效率", r"(\bcli\b|terminal|\btui\b|neovim|\bvim\b|emacs|"
                   r"dotfile|keyboard|launcher|developer tool)", "cli developer tool"),
    ("育儿与生活服务", r"(parenting|babysit|childcare|elder care|"
                   r"pet care|meal plan|\bfitness\b|health track)", "lifestyle utility"),
]

_DIR_C = [(name, re.compile(pat, re.I), kw) for name, pat, kw in DIRECTIONS]
_NAME2KW = {name: kw for name, _, kw in DIRECTIONS}

# 拥挤度分级（阈值来自 2026-09-17 的实测分布，stars:>50 过滤）：
#   llm+agent 3297 / browser+extension 1097 / video+ffmpeg 762 /
#   monitoring+observability 277 / self-hosted+deploy 180 / calendar 75 /
#   scraper+parser 48 / billing+payment 37 / seo+analytics 22 / ci+code+quality 17
CROWD_LEVELS = [(1000, "红海"), (300, "拥挤"), (80, "中等"), (0, "稀疏")]


def crowd_level(n):
    if n is None:
        return "未知"
    for th, label in CROWD_LEVELS:
        if n >= th:
            return label
    return "稀疏"


def opportunity_tag(evidence, market):
    """机会象限：热度（证据数）× 拥挤度（存量项目数）。

    热度高不等于有机会 —— 一个方向证据很多、同时存量项目也很多，
    说明那是已被挤满的赛道。机会 = 高热度 + 低拥挤。
    """
    hot = evidence >= 3
    if market is None:
        return "拥挤度未知"
    crowded = market >= 300
    if hot and not crowded:
        return "★ 值得看"
    if hot and crowded:
        return "已拥挤：需差异化切入"
    if not hot and not crowded:
        return "待验证"
    return "红海"


def _topic_blob(rec):
    """归类用的文本。

    优先用 topic_text（帖子主题），因为它才是"这个讨论属于什么方向"的依据；
    text 里可能混入了整段评论区，评论区会跑题 —— 实测一条讲"评论被当垃圾删掉"
    的评论把整个帖子带偏到"报表与可视化"。
    没有 topic_text 的记录退回 title + text。
    """
    ctx = rec.get("topic_text")
    if ctx:
        return ctx
    return f"{rec.get('title','')} {rec.get('text','')}"


def classify(rec):
    """判断一条候选属于哪些方向（保留全部匹配，供排查用）。"""
    blob = _topic_blob(rec)
    return [name for name, pat, _ in _DIR_C if pat.search(blob)]


def classify_best(rec, exclude=()):
    """只归入匹配最强的一个方向，返回 (方向名, 强度分) 或 (None, 0)。

    为什么必须单选：多标签会让同一条证据被多个方向重复计数 ——
    实测一个 CLI 仓库同时进了"AI 代理""视频音频""终端效率"三个方向，
    导致证据数虚高、榜单出现重复观感（同一条内容在两个方向下都排第一）。
    方向之间应当互斥，这样"证据数"才是一个诚实的数字。

    强度分算法（避免平票时按分类表顺序瞎选）：
      标题命中 ×3，正文命中 ×1，再乘以命中关键词长度（长关键词更具体）。
    exclude：排除某些方向（见 aggregate 里"招聘帖不能算招聘软件需求"的说明）。

    实测这个加权能纠正两类错误：
      · "Audit AI agent tool-call transcripts …Python CLI" → 归 AI 代理（标题命中）
        而不是终端效率（仅正文出现 CLI）
      · "visualize the stars history" → 归报表与可视化（标题命中 visualize）
        而不是获客与 SEO（正文出现 growth）
    """
    title = rec.get("title") or ""
    body = _topic_blob(rec)
    best, best_s = None, 0.0
    for name, pat, _ in _DIR_C:
        if name in exclude:
            continue
        s = 0.0
        for m in pat.finditer(title):
            s += 3.0 * len(m.group(0))
        for m in pat.finditer(body):
            s += 1.0 * len(m.group(0))
        if s > best_s:
            best, best_s = name, s
    return best, round(best_s, 2)


def aggregate(candidates):
    """聚合候选 → 方向统计。每条候选只计入一个方向（见 classify_best）。

    方向判定优先级：记录上的 direction 字段（LLM 语义分类写入）>
    关键词签名 classify_best。这样 LLM 模式与关键词模式共用同一套聚合/渲染。
    """
    stat = {}
    for r in candidates:
        # 招聘帖/赏金 issue **不能**归入"招聘与 HR"：它们自己就是"找人做事"的帖子，
        # 把它们当成"招聘软件的需求"是范畴错误（实测：7 条 Indeed/forhire 招聘帖
        # 让"招聘与 HR"以 存量5/成型0 拿到"★建议优先验证"，属于纯人工伪影）。
        # 它们应当按**工作内容**归类（如"数据采集与解析"），并作为该方向的付费证据。
        excl = ("招聘与 HR",) if r.get("record_type") in ("hiring", "bounty") else ()
        name = r.get("direction") or classify_best(r, exclude=excl)[0]
        if name in excl:
            continue
        if not name:
            continue
        s = stat.setdefault(name, {
            "name": name, "evidence": 0, "sources": set(),
            "wtp": 0, "pain": 0, "items": [], "repos": [],
            "velocity": 0.0, "wtp_llm": 0, "hiring": 0,
            "heat_score": 0, "heat_comments": 0,
            "hot": 0, "native_sources": set(), "keyword_sources": set(),
        })
        is_hot = r.get("record_type") == "platform_hot"
        if is_hot:
            s["hot"] += 1            # 平台热点证据（原生榜 + 热度达标）
        else:
            s["evidence"] += 1       # 需求证据（过门槛）
        src = r.get("source")
        s["sources"].add(src)
        # 共振只看"原生榜/源自原生榜的深读"——关键词命中是同一个查询的回声，
        # 不能当独立发现（P0-1 的核心修正）
        if _paths.is_native(r):
            s["native_sources"].add(src)
        else:
            s["keyword_sources"].add(src)
        if r.get("strong_wtp_hits"):
            s["wtp"] += 1
        if (r.get("llm_wtp") or 0) >= 3:
            s["wtp_llm"] += 1
        # 招聘与赏金都算"有人出钱"的直接证据（付费侧），分开记但一起参与判断
        if r.get("record_type") in ("hiring", "bounty"):
            s["hiring"] += 1
        # 讨论热度：评论赞同合计优先（社区认同度），否则退回收/赞数。
        # 回退链必须覆盖各信源的原始字段名——HN Algolia 出的是 points，
        # 老缓存里的记录也没有 heat 字段（不补回退，重算时热度会全是 0）。
        h = r.get("heat") or {}
        hscore = h.get("comment_score") or h.get("score")
        hcomm = h.get("comments")
        if hscore is None:
            hscore = r.get("points") or r.get("score") or r.get("ups")
        if hcomm is None:
            hcomm = r.get("num_comments") or r.get("descendants")
        try:
            s["heat_score"] += int(hscore or 0)
            s["heat_comments"] += int(hcomm or 0)
        except Exception:
            pass
        if r.get("pain_hits") or (r.get("llm_pain") or 0) >= 3:
            s["pain"] += 1
        if r.get("source") in ("github_trending", "github_search"):
            s["repos"].append(r)
            s["velocity"] += r.get("star_velocity") or 0
        if len(s["items"]) < 12:
            s["items"].append(r)
    for s in stat.values():
        s["diversity"] = len(s["sources"])              # 全部平台数（展示用）
        s["resonance"] = len(s["native_sources"])       # 真共振：原生榜独立发现数
        s["native_sources"] = sorted(x for x in s["native_sources"] if x)
        s["keyword_sources"] = sorted(x for x in s["keyword_sources"] if x)
        # 讨论热度合成值：赞同数 + 评论数×3（评论多=讨论规模大，单赞不算讨论）
        s["heat"] = s["heat_score"] + s["heat_comments"] * 3
        # 付费信号取两种来源的并集口径：关键词构式命中 或 LLM 判定 wtp>=3
        s["wtp_total"] = max(s["wtp"], s["wtp_llm"])
        s["score"] = round(
            s["evidence"] * 1.0
            + s["resonance"] * 0.8   # 用真共振替代"平台名字数"
            + s["wtp_total"] * 1.2
            + math.log10(s["velocity"] + 1) * 1.5
            + min(len(s["repos"]), 5) * 0.4, 2)
        s["sources"] = sorted(x for x in s["sources"] if x)
    return stat


def top_directions(stat, n=10, min_evidence=1, require_wtp=False):
    """取 top N。

    关于 min_evidence：设成 2 是本来的想法（"单一提及不算方向"），但实测下来
    会把输出压到只有 4–5 个方向 —— 因为一个窗口内规则层只留 60 多条，
    摊到 28 个方向后多数只有 1 条证据。与其假装凑满 10 个，不如全量排序并
    **显式标注证据强度**，让"弱信号"以它本来的面目出现。
    """
    rows = [s for s in stat.values()
            if s["evidence"] >= min_evidence and (s["wtp"] > 0 or not require_wtp)]
    rows.sort(key=lambda x: -x["score"])
    return rows[:n]


def strength(evidence):
    if evidence >= 5:
        return "强"
    if evidence >= 3:
        return "中"
    if evidence >= 2:
        return "偏弱"
    return "弱（单条证据）"


# ---------------------------------------------------------------- 各平台视角
# 为什么必须分平台看：不同平台的偏差完全不同，混在一起会被平均数糊弄。
#   GitHub       = 供给侧（大家在做什么 ≠ 有人要）
#   HN           = 技术讨论（噪音大，但偶有付费构式）
#   Reddit       = 创始人抱怨（需求侧最真实的口语证据）
#   Product Hunt = 新发布（竞品情报，不是需求）
# 用户明确要求报告按平台区分。
PLATFORM_NAMES = {
    "github_trending": "GitHub Trending（供给侧·热度）",
    "github_search": "GitHub Search（供给侧·新增）",
    "github_issue": "GitHub Issues（用户原话）",
    "hn": "Hacker News（技术讨论）",
    "reddit": "Reddit（创始人社区·需求侧）",
    "producthunt": "Product Hunt（新发布·竞品情报）",
    "upwork": "Upwork（付费需求·最硬）",
    "browser": "浏览器通道（Indie Hackers 等）",
    "stackoverflow": "Stack Overflow（提问=未满足需求）",
    "lobsters": "Lobsters（技术讨论）",
    "devto": "DEV.to（开发者文章）",
    "lesswrong": "LessWrong（理性社区）",
    "indeed": "Indeed（招聘=企业付费）",
    "twitter": "X/Twitter（创始人发声）",
    "zhihu": "知乎（中文需求讨论）",
    "xiaohongshu": "小红书（中文消费需求）",
    "juejin": "掘金（中文技术热榜，弱等效）",
    "bluesky": "Bluesky（热门话题，弱等效）",
    "github_bounty": "GitHub 赏金 Issue（有人挂钱求做）",
}

# 表格里的平台短码（省宽度）
SRC_SHORT = {
    "github_trending": "GT", "github_search": "GS", "github_issue": "GI",
    "hn": "HN", "reddit": "RD", "producthunt": "PH",
    "upwork": "UW", "browser": "BR",
    "stackoverflow": "SO", "lobsters": "LB", "devto": "DT", "lesswrong": "LW",
    "indeed": "IN", "twitter": "TW", "zhihu": "ZH", "xiaohongshu": "XHS",
    "juejin": "JJ", "bluesky": "BSKY", "github_bounty": "B$",
}


def platform_view(records, top_dirs=4):
    """按平台拆开看：每个平台各自发现了什么方向、代表性证据是什么。"""
    by = {}
    for r in records:
        by.setdefault(r.get("source", "?"), []).append(r)
    lines = ["#### 各平台视角", "",
             "> 平台偏差不同，混看会被平均：GitHub 是供给侧（大家在做什么≠有人要），"
             "Reddit 才是需求侧原话，Product Hunt 是竞品情报。"
             "**同一方向出现在多个平台 = 信号更硬**。", ""]
    for src, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        plat = PLATFORM_NAMES.get(src, src)
        stat = {}
        for r in items:
            name = r.get("direction") or classify_best(r)[0]
            if name:
                s = stat.setdefault(name, {"n": 0, "items": []})
                s["n"] += 1
                if len(s["items"]) < 3:
                    s["items"].append(r)
        top = sorted(stat.items(), key=lambda kv: -kv[1]["n"])[:top_dirs]
        lines.append(f"**{plat}**　{len(items)} 条")
        if top:
            # 用平台内占比而非绝对数：样本量不同，绝对数跨平台不可比
            lines.append("- 方向：" + "、".join(
                f"{n}（{v['n']} 条 / 平台内 {v['n']/len(items):.0%}）" for n, v in top))
            r0 = top[0][1]["items"][0]
            lines.append(f"- 代表证据：[{(r0.get('title') or '')[:70]}]({r0.get('url', '')})")
            lines.append(f"  > {_quote(r0, 150)}")
        else:
            lines.append("- 无可归类方向（供给型记录或未覆盖话题）")
        lines.append("")
    return "\n".join(lines)


def attach_crowding(stat, rows, count_fn, max_dirs=12, spacing=7, cache=None):
    """给头部方向补拥挤度（GitHub 存量项目数）。

    只对热度 top max_dirs 个方向查询 —— 28 个方向全查一次要 3 分钟以上，
    而排不进头部的方向也轮不到讨论拥挤度。
    count_fn(keywords) -> (total_count|None, err)，由调用方注入以便跨窗口复用缓存。
    """
    done, errs = 0, []
    for i, s in enumerate(rows[:max_dirs]):
        kw = _NAME2KW.get(s["name"])
        if not kw:
            continue
        n = (cache or {}).get(kw)
        if n is None:
            n, err = count_fn(kw)
            if cache is not None:
                cache[kw] = n
            time.sleep(spacing)  # Search API 未认证 10/min
        if n is None:
            errs.append(f"{s['name']}: {err}")
            continue
        s["market_repos"] = n
        s["crowd"] = crowd_level(n)
        s["opp_tag"] = opportunity_tag(s["evidence"], n)
        # 机会分 = 热度分 / log10(存量+10)：越拥挤机会被稀释得越厉害
        s["opp_score"] = round(s["score"] / math.log10(n + 10), 2)
        done += 1
    return done, errs


def attach_supply(rows, count_fn, max_dirs=12, spacing=7, cache=None):
    """挂「已成型产品数」（GitHub stars>1000）——判断"有没有人已经做成"。

    与 crowding（stars>50 存量）是两个口径：存量看"有多少人在做"，
    成型数看"有没有人做大了"。后者为 0 且热度高，才是"讨论热但没成熟产品"。
    """
    done = 0
    for s0 in rows[:max_dirs]:
        kw = _NAME2KW.get(s0["name"])
        if not kw:
            continue
        key = "maturecnt:" + kw
        n = (cache or {}).get(key)
        if n is None:
            n, _ = count_fn(kw)
            if cache is not None:
                cache[key] = n
            time.sleep(spacing)
        s0["mature_products"] = n
        done += 1 if n is not None else 0
    return done


def attach_real_cases(rows, mature_fn, max_dirs=12, spacing=7, cache=None):
    """给头部方向挂上可点开的真实案例。用户诉求：方向只是标签，
    必须能点开真实项目/原帖来验证，否则榜单无法取信。

    两类案例：
      mature   —— GitHub 全量按星标排序的 top3（成熟/被大量关注的项目），
                  与 crowding 共用缓存（key 加 mature: 前缀）；
      evidence —— 本窗口抓到的需求证据帖原链（前 4 条）。
    """
    done, errs = 0, []
    for s in rows[:max_dirs]:
        kw = _NAME2KW.get(s["name"])
        if kw:
            key = "mature:" + kw
            m = (cache or {}).get(key)
            if m is None:
                m, err = mature_fn(kw)
                if cache is not None:
                    cache[key] = m
                time.sleep(spacing)
            if m:
                s["mature"] = m
            else:
                errs.append(f"{s['name']}: 成熟项目查询失败")
        s["evidence_links"] = [{"title": (r.get("title") or "")[:80],
                                "url": r.get("url", ""),
                                "source": r.get("source", "")}
                               for r in s.get("items", [])[:4] if r.get("url")]
        done += 1
    return done, errs


def render_cases(s, idx):
    """单个方向的真实案例两行式（Markdown）。

    注意：链接必须用**半角** `)` 收尾。原实现写成了
        f"[{m['repo']}]({m['url']}）（★{m['stars']}…"
    全角括号 Markdown 不认，导致「成熟/高关注项目」和「本窗口新增仓库」两类链接
    全部不可点击（实测已发布报告里有 30 处）。而这正是"真实案例速查"章节
    存在的唯一理由 —— 用户诉求就是"方向只是标签，必须能点开验证"。
    """
    L = [f"**{idx}. {s['name']}**"]
    if s.get("mature"):
        L.append("- 成熟/高关注项目：" + " · ".join(
            f"[{m['repo']}]({m['url']})（★{m['stars']}，更新 {m['updated'] or '—'}）"
            for m in s["mature"]))
    elif s.get("repos"):
        reps = sorted(s["repos"], key=lambda x: -(x.get("star_velocity") or 0))[:2]
        L.append("- 本窗口新增仓库：" + " · ".join(
            f"[{p['repo']}]({p['url']})（★{p.get('stars_total')}）" for p in reps))
    if s.get("evidence_links"):
        L.append("- 需求证据帖：" + " · ".join(
            f"[{e['title'][:44]}]({e['url']})" for e in s["evidence_links"][:3]))
    return L


def _quote(rec, limit=190):
    t = " ".join((rec.get("text") or "").split())
    hits = (rec.get("strong_wtp_hits") or []) + (rec.get("pain_hits") or [])
    if hits:
        k = t.lower().find(hits[0][:18].lower())
        if k > 60:
            t = "…" + t[max(0, k - 80):]
    return t[:limit]


def render_advice(rows):
    """建议与趋势表。两个轴独立：建议=当下值不值得投入；趋势=变化速率。"""
    if not any(s.get("advice") for s in rows):
        return []
    L = ["#### 建议与趋势", "",
         "**建议结论**看当下值不值得投入（热度 × 拥挤度 × 付费信号）；"
         "**趋势评级**看变化速率（头部仓库涨星速度 × 平台共振 × 窗口加速）。"
         "两者可能背离 —— 很热但停滞、或证据少却在加速，都真实存在。", "",
         "| 方向 | 建议结论 | 趋势 | 支撑理由 | 建议动作 |",
         "|---|---|---|---|---|"]
    for s in rows:
        rs = list(s.get("advice_reasons") or []) + list(s.get("trend_reasons") or [])
        L.append(f"| **{s['name']}** | {s.get('advice', '—')} | "
                 f"{s.get('trend_level', '—')}（{s.get('trend_score', 0)}） | "
                 f"{'；'.join(rs) or '—'} | {s.get('advice_action', '—')} |")
    early = [s for s in rows if s.get("trend_level") == "高" and s.get("evidence", 0) < 3]
    if early:
        L += ["", "**早期加速信号**（趋势高但证据还少 —— 提前占位候选，失败风险也高）：", ""]
        for s in early:
            L.append(f"- **{s['name']}**：{'；'.join(s.get('trend_reasons') or [])}")
    return L


def render_window(window_label, rows, total_dirs, raw_count, path_stats=None,
                  native_fail=None):
    L = [f"### {window_label} Top {len(rows)} 方向", "",
         f"（本窗口采集 {raw_count} 条，归类出 {total_dirs} 个候选方向）", ""]
    if path_stats:
        n_nat, n_kw, rate = path_stats
        flag = "达标" if rate >= 0.40 else "**未达标**"
        L += [f"**原生榜贡献率 {rate:.0%}**（原生 {n_nat} / 关键词 {n_kw}｜目标 ≥40%：{flag}）"
              "　—— 原生榜=排序由平台决定（真独立发现）；关键词检索=排序由我的查询决定"
              "（同一查询的回声，不计入共振）。", ""]
        # 诚实前提：这个比率会被"上游原生源挂掉"直接压低，看起来像方法学退化。
        # 所以必须把原生侧失败数并排写出来（实测：GitHub 搜索被限流时，
        # 本月原生率从 55% 掉到 19%，纯属上游故障而非口径问题）。
        if native_fail:
            L += [f"⚠ **注意**：本窗口有 {len(native_fail)} 个原生源采集失败"
                  f"（{'、'.join(native_fail[:6])}{'…' if len(native_fail) > 6 else ''}）——"
                  "原生率会被上游故障直接压低，读数时必须结合失败情况判断，"
                  "不能当作口径退化。", ""]
    if not rows:
        L.append("_本窗口没有出现可归类的方向，说明信号不足或门槛过严。_")
        return "\n".join(L)
    has_crowd = any("crowd" in s for s in rows)
    if has_crowd:
        L += ["| # | 方向 | 机会 | 强度 | 需求证据 | 热点 | 共振(原生/检索) | 讨论热度 | 付费 | 存量 | 成型 | 拥挤度 | 评分 | 机会分 |",
              "|---:|---|---|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|"]
        for i, s in enumerate(rows, 1):
            nat = "、".join(SRC_SHORT.get(x, x) for x in s.get("native_sources", [])) or "—"
            kw = "、".join(SRC_SHORT.get(x, x) for x in s.get("keyword_sources", [])) or "—"
            L.append(f"| {i} | **{s['name']}** | {s.get('opp_tag', '—')} | "
                     f"{strength(s.get('evidence', 0) + s.get('hot', 0))} | "
                     f"{s.get('evidence', 0)} | {s.get('hot', 0)} | "
                     f"{s.get('resonance', 0)}（{nat} / {kw}） | "
                     f"{s.get('heat', 0)} | {s.get('wtp_total', s.get('wtp', 0))} | "
                     f"{s.get('market_repos', '—')} | {s.get('mature_products', '—')} | "
                     f"{s.get('crowd', '—')} | {s['score']} | {s.get('opp_score', '—')} |")
    else:
        L += ["| # | 方向 | 证据强度 | 证据数 | 平台 | 付费信号 | 相关仓库 | 涨星合计 | 评分 |",
              "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
        for i, s in enumerate(rows, 1):
            plats = "、".join(SRC_SHORT.get(x, x) for x in s.get("sources", []))
            L.append(f"| {i} | **{s['name']}** | {strength(s['evidence'])} | {s['evidence']} | "
                     f"{plats} | {s.get('wtp_total', s.get('wtp', 0))} | {len(s['repos'])} | "
                     f"{int(s['velocity'])} | {s['score']} |")
    if has_crowd:
        L += ["", "> **机会象限**：热度（**仅需求证据**，不含热点；≥3 视为高）× "
                  "拥挤度（存量项目≥300 视为拥挤）。"
                  "「★ 值得看」= 高热度 + 低拥挤；「已拥挤」= 高热度 + 红海，需差异化切入。"
                  "拥挤度阈值（红海≥1000 / 拥挤≥300 / 中等≥80 / 稀疏<80）来自实测分布，"
                  "且 GitHub 存量数受关键词选择影响，只作相对比较。"]
    # 两列的基数不同必须写明：否则同一行出现「强度 中 / 机会 待验证」这类组合，
    # 读者会以为是自相矛盾（实测被问到过）。写明后它就是一个可复核的口径差异。
    L += ["", "> 强度口径：需求证据+热点合计 ≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。"
              "**注意：「强度」与「机会」两列的基数不同** —— 强度含热点证据，"
              "机会只算需求证据，所以同一行出现「强度 中 / 机会 待验证」这类组合是"
              "口径差异，不是矛盾。"
              "「弱」不代表没价值，只代表本期只有一条独立证据 —— 需要下期复现才算成立。", ""]

    top = [s for s in rows if s["evidence"] >= 2][:3] or rows[:2]
    L += render_advice(rows) + [""]
    L += [f"#### {window_label} 主要方向的证据原文", ""]
    for s in top:
        L.append(f"**{s['name']}**　证据 {s['evidence']} 条　信源 {', '.join(s['sources'])}")
        for r in s["items"][:3]:
            L.append(f"- [{r.get('title','')[:78]}]({r.get('url','')})")
            L.append(f"  > {_quote(r)}")
        if s["repos"]:
            reps = sorted(s["repos"], key=lambda x: -(x.get("star_velocity") or 0))[:3]
            L.append(f"- 相关仓库：" + "、".join(
                f"[{p['repo']}]({p['url']})（★{p.get('stars_total')}，日均+"
                f"{p.get('star_velocity') or 0:g}）" for p in reps))
        L.append("")

    # 真实案例速查：每个方向都能点开真实项目与原帖验证（用户诉求）
    if any(s.get("mature") or s.get("evidence_links") for s in rows):
        L += ["#### 真实案例速查", "",
              "成熟项目=GitHub 全量按星标 top3（验证赛道成色）；"
              "需求证据帖=本窗口抓到的原链（验证需求真实性）。", ""]
        for i, s in enumerate(rows, 1):
            if s.get("mature") or s.get("evidence_links") or s.get("repos"):
                L += render_cases(s, i) + [""]
    return "\n".join(L)
