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


def classify_best(rec):
    """只归入匹配最强的一个方向，返回 (方向名, 强度分) 或 (None, 0)。

    为什么必须单选：多标签会让同一条证据被多个方向重复计数 ——
    实测一个 CLI 仓库同时进了"AI 代理""视频音频""终端效率"三个方向，
    导致证据数虚高、榜单出现重复观感（同一条内容在两个方向下都排第一）。
    方向之间应当互斥，这样"证据数"才是一个诚实的数字。

    强度分算法（避免平票时按分类表顺序瞎选）：
      标题命中 ×3，正文命中 ×1，再乘以命中关键词长度（长关键词更具体）。
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
        s = 0.0
        for m in pat.finditer(title):
            s += 3.0 * len(m.group(0))
        for m in pat.finditer(body):
            s += 1.0 * len(m.group(0))
        if s > best_s:
            best, best_s = name, s
    return best, round(best_s, 2)


def aggregate(candidates):
    """聚合候选 → 方向统计。每条候选只计入一个方向（见 classify_best）。"""
    stat = {}
    for r in candidates:
        name, nhits = classify_best(r)
        if not name:
            continue
        s = stat.setdefault(name, {
            "name": name, "evidence": 0, "sources": set(),
            "wtp": 0, "pain": 0, "items": [], "repos": [],
            "velocity": 0.0,
        })
        s["evidence"] += 1
        s["sources"].add(r.get("source"))
        if r.get("strong_wtp_hits"):
            s["wtp"] += 1
        if r.get("pain_hits"):
            s["pain"] += 1
        if r.get("source") in ("github_trending", "github_search"):
            s["repos"].append(r)
            s["velocity"] += r.get("star_velocity") or 0
        if len(s["items"]) < 12:
            s["items"].append(r)
    for s in stat.values():
        s["diversity"] = len(s["sources"])
        s["score"] = round(
            s["evidence"] * 1.0
            + s["diversity"] * 0.8
            + s["wtp"] * 1.2
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


def _quote(rec, limit=190):
    t = " ".join((rec.get("text") or "").split())
    hits = (rec.get("strong_wtp_hits") or []) + (rec.get("pain_hits") or [])
    if hits:
        k = t.lower().find(hits[0][:18].lower())
        if k > 60:
            t = "…" + t[max(0, k - 80):]
    return t[:limit]


def render_window(window_label, rows, total_dirs, raw_count):
    L = [f"### {window_label} Top {len(rows)} 方向", "",
         f"（本窗口采集 {raw_count} 条，归类出 {total_dirs} 个候选方向）", ""]
    if not rows:
        L.append("_本窗口没有出现可归类的方向，说明信号不足或门槛过严。_")
        return "\n".join(L)
    has_crowd = any("crowd" in s for s in rows)
    if has_crowd:
        L += ["| # | 方向 | 机会 | 证据强度 | 证据数 | 信源数 | 付费信号 | 存量项目 | 拥挤度 | 评分 | 机会分 |",
              "|---:|---|---|---:|---:|---:|---:|---:|---|---:|---:|"]
        for i, s in enumerate(rows, 1):
            L.append(f"| {i} | **{s['name']}** | {s.get('opp_tag', '—')} | "
                     f"{strength(s['evidence'])} | {s['evidence']} | {s['diversity']} | "
                     f"{s['wtp']} | {s.get('market_repos', '—')} | {s.get('crowd', '—')} | "
                     f"{s['score']} | {s.get('opp_score', '—')} |")
    else:
        L += ["| # | 方向 | 证据强度 | 证据数 | 信源数 | 付费信号 | 相关仓库 | 涨星合计 | 评分 |",
              "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
        for i, s in enumerate(rows, 1):
            L.append(f"| {i} | **{s['name']}** | {strength(s['evidence'])} | {s['evidence']} | "
                     f"{s['diversity']} | {s['wtp']} | {len(s['repos'])} | "
                     f"{int(s['velocity'])} | {s['score']} |")
    if has_crowd:
        L += ["", "> **机会象限**：热度（证据数≥3 视为高）× 拥挤度（存量项目≥300 视为拥挤）。"
                  "「★ 值得看」= 高热度 + 低拥挤；「已拥挤」= 高热度 + 红海，需差异化切入。"
                  "拥挤度阈值（红海≥1000 / 拥挤≥300 / 中等≥80 / 稀疏<80）来自实测分布，"
                  "且 GitHub 存量数受关键词选择影响，只作相对比较。"]
    L += ["", "> 强度口径：证据数 ≥5 强 / ≥3 中 / 2 偏弱 / 1 弱。"
              "「弱」不代表没价值，只代表本期只有一条独立证据 —— 需要下期复现才算成立。", ""]

    top = [s for s in rows if s["evidence"] >= 2][:3] or rows[:2]
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
    return "\n".join(L)
