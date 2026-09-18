# -*- coding: utf-8 -*-
"""
过滤层：
  L1 规则硬过滤（免费，先砍量）
  L2 供给侧风险检测（反刷星 / 开源协议 / 资源合集识别）
输出统一 candidate 结构，交给 L3 LLM 打分。
设计原则：所有判断都必须给出可追溯的 reason + evidence，禁止"黑箱结论"。
"""
import re
import time

# ---------------------------------------------------------------- L1 硬过滤词表
# 方法论里点名的"避雷项"：教程/awesome 合集仓库没有变现机会
COLLECTION_PAT = re.compile(
    r"\b(awesome|curated list|collection of|list of|roadmap|tutorial|"
    r"cheat ?sheet|handbook|ebook|e-book|course|learning path|资源汇总|合集)\b", re.I)

# 毫无信息量的噪音行
NOISE_PAT = re.compile(r"^(thanks|thank you|\+1|same here|following|this\.?|"
                       r"lol|nice|agree|congrats)[\s!.,]*$", re.I)

# 需求信号（召回用，不单独作为结论）
PAIN_PAT = re.compile(
    r"(frustrat|annoying|painful|hate (that|when)|waste[sd]? (my )?time|"
    r"manual(ly)?|tedious|too complex|hard to (deploy|set up|configure|install)|"
    r"no (gui|ui|web interface|dashboard)|command[- ]line only|"
    r"self[- ]host(ed|ing)? (is|was) (a )?(pain|nightmare)|"
    r"wish (there was|i could)|looking for (a|an|the) .{0,40}(tool|alternative|service)|"
    r"is there (a|an) .{0,40}(tool|alternative)|any (recommendation|alternative)s?|"
    r"would (gladly )?pay|happy to pay|willing to pay|shut up and take my money|"
    r"paid (version|plan|alternative)|someone should build|"
    r"求推荐|有没有好用的|有没有(什么)?(工具|软件|办法|方法)|太麻烦了?|"
    r"怎么(自动|批量)|如何(自动|批量)|手动.{0,8}(复制|整理|处理|同步|导出))", re.I)

# 付费意愿强信号（权重最高的那一类）
WTP_PAT = re.compile(
    r"(would (gladly |happily )?pay|happy to pay|willing to pay|"
    r"shut up and take my money|take my money|paid (version|plan|tier|"
    r"alternative|option)|worth paying|i'?d pay \$|invoice|budget for|"
    r"hire someone to|looking to (hire|pay)|有付费版|愿意付费)", re.I)

# —— 为什么需要这一层（实测教训）——
# 裸用 WTP_PAT 做采集门槛，精度约等于 0：英文里 "willing to pay" 大量出现在
# "employer is willing to pay thousands for AI tools" 这类与个人购买决策无关的
# 语境中。首版 12 条候选命中 12 条全是这种词面碰撞，属于纯噪音。
# 因此把"付费意愿"的门槛收紧为：必须出现第一人称购买者 + 支付动词的构式。
STRONG_WTP = re.compile(
    r"(\b(i|we|i'?d|we'?d|my (team|company|org))\b[^.!?\n]{0,50}?"
    r"\b(would|'d|will|happy|gladly|willing|can|'?ll)\b[^.!?\n]{0,25}?\bpay\b)"
    r"|(take my money)"
    r"|(\b(pay|paid|paying)\b[^.!?\n]{0,20}?\bfor (a|an|the|this|it)\b[^.!?\n]{0,30}?\b(tool|app|service|software|solution)\b)"
    r"|(\bwhere can i (buy|pay|subscribe)\b)"
    r"|(\bi'?d (happily|gladly)? ?pay \$?\d)",
    re.I)

# 信源专属门槛：问题式/故障式提问（Stack Overflow）与招聘帖（Indeed）。
# SO 实测教训：故障陈述式标题（"Getting forbidden error on selenium chrome"）不含
# how/is there 等问句词，但"报错=被拦=没现成方案"，同样是需求代理。
QUESTION_PAT = re.compile(
    r"\b(how (do|to|can|would) (i|we|you)|why (does|do|is|are)|is there (a|an|any|way)"
    r"|any (way|tool|recommendation)|can i|possible to|alternative to)"
    r"|\b(getting|got|keep getting) .{0,30}error\b"
    r"|\berror (when|on|after|in|with)\b"
    r"|\b(fail(s|ed)? to|not working|stopped working|crash(es|ing)?)\b", re.I)
HIRING_PAT = re.compile(
    r"(we are (looking|searching) for|job (type|description|title)|responsibilities"
    r"|qualifications|full[- ]?time|part[- ]?time|salary|per hour|apply now"
    r"|requirements| hiring |岗位|招聘|薪资)", re.I)


def is_collection(text, repo, topics=None):
    blob = f"{text} {repo} {' '.join(topics or [])}"
    return bool(COLLECTION_PAT.search(blob))


def pain_hits(text):
    return sorted(set(m.group(0).lower() for m in PAIN_PAT.finditer(text or "")))


def wtp_hits(text):
    return sorted(set(m.group(0).lower() for m in WTP_PAT.finditer(text or "")))


def strong_wtp_hits(text):
    """第一人称购买语境 —— 这才是能当门槛用的信号。"""
    return sorted(set(m.group(0).lower()[:60] for m in STRONG_WTP.finditer(text or "")))


# ---------------------------------------------------------------- L2 供给侧风险
# 阈值来源：CMU 等 StarScout 研究（arXiv 2412.13459 / ICSE 2026）
#   零关注者星标账号：真实项目 5–12%，作弊项目 36–76%
#   fork/star 比：健康 0.15–0.25，作弊 < 0.05
# 下面只实现"不需要 token 也能算"的那部分。
REPO_SOURCES = ("github_trending", "github_search")
TEXT_SOURCES = ("hn", "github_issue", "browser", "reddit", "producthunt", "upwork",
                "stackoverflow", "lobsters", "devto", "lesswrong", "indeed",
                "twitter", "zhihu", "xiaohongshu")


def _age_days(created):
    if not created:
        return None
    try:
        return (time.time() - time.mktime(time.strptime(created[:10], "%Y-%m-%d"))) / 86400
    except Exception:
        return None


def supply_risk(rec):
    """对 GitHub 仓库做供给侧风险体检。返回 (risk_level, flags[])"""
    flags = []
    stars = rec.get("stars_total") or 0
    forks = rec.get("forks") or 0
    window = rec.get("stars_window") or 0
    src = rec.get("source")

    if stars >= 50:
        ratio = forks / stars if stars else 0
        if ratio < 0.05:
            flags.append(f"fork/star={ratio:.3f} 低于 0.05（真实项目通常 0.15–0.25）")
        elif ratio < 0.10:
            flags.append(f"fork/star={ratio:.3f} 偏低，需人工确认")

    # 爆发式脉冲：只对 trending 榜（真实时间窗）成立。
    # 注意：search 来的新仓库 window 天然等于总量，拿它算"脉冲"是错的（首版曾全量误报）。
    if src == "github_trending" and stars >= 200 and window:
        burst = window / stars
        if burst > 0.60:
            flags.append(f"窗口内星标占总星标 {burst:.0%}，呈爆发式脉冲")

    # 新建仓库改用"日均增速"，这才是可比口径
    age = _age_days(rec.get("created_at"))
    if src == "github_search" and age and stars:
        v = stars / max(age, 1)
        rec["star_velocity"] = round(v, 1)
        if v > 400:
            flags.append(f"日均涨星 {v:.0f}，远高于自然增长速度（重点核查是否刷星）")
        elif v > 150:
            flags.append(f"日均涨星 {v:.0f}，增速偏高")

    # 老仓库（star 高但创建久）不是新需求信号
    if age and age > 1825 and window and window < 50:
        flags.append("老项目、窗口增量极低：非新增需求信号")

    # 协议：GPL 系强传染，直接封装商用有风险
    lic = (rec.get("license") or "").upper()
    if lic in ("GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0"):
        flags.append(f"协议 {lic} 强传染，禁止直接闭源封装商用")
    elif lic in ("", "NONE", "NOASSERTION", "NULL"):
        flags.append("无明确开源协议：默认保留全部权利，不得商用")

    # 渗透率：千星但零 issue → 没人真在用
    oi = rec.get("open_issues")
    if oi is not None and stars >= 1000 and oi == 0:
        flags.append("千星但零 issue：无真实使用反馈")

    level = "high" if len(flags) >= 2 else ("medium" if flags else "low")
    return level, flags


# 话题域门槛：只保留软件/产品类讨论。
# 为什么必须加：用通用付费短语（willing to pay 等）检索 HN，会命中任何话题的帖子——
# 实测捞到"出生率辩论""AirPods 5""LG 电视监控"，这些帖子里确实有人表达付费意愿，
# 但与"可被独立开发者解决的需求"毫无关系。这类噪音靠下游 LLM 逐个剔除太贵，
# 在采集入口按话题域砍掉最划算。
TECH_TOPIC = re.compile(
    r"(software|tool|app\b|apps\b|api\b|sdk|library|framework|code|coding|"
    r"develop|programming|engineer|saas|startup|founder|indie|product|"
    r"open[- ]?source|self[- ]?host|server|deploy|docker|kubernetes|database|"
    r"\bdata\b|pipeline|automation|workflow|integrat|dashboard|cli\b|terminal|"
    r"linux|macos|windows|browser|extension|plugin|cloud|hosting|devops|"
    r"\bai\b|\bllm|model|agent|prompt|inference|embedding|rag\b|"
    r"pricing|subscription|billing|invoice|payment|checkout|stripe|"
    r"customer|churn|onboarding|marketing|seo|analytics|landing page|"
    r"newsletter|email|crm|support ticket|helpdesk|docs|documentation|"
    r"bug|release|version|refactor|test|monitor|observab|log\b|"
    r"spreadsheet|excel|notion|slack|calendar|form\b|survey|scrap|parse|"
    r"translat|transcri|screenshot|pdf|export|backup|sync|migration|"
    # 开发工具类：不加这些会误杀"IDE/LSP/编辑器"这类真有付费意愿的讨论
    r"\bide\b|lsp\b|editor|vim|emacs|compiler|runtime|kernel|\bgit\b|"
    r"shell|bash|python|javascript|typescript|rust|golang|node|java\b|"
    r"sql|regex|stack overflow|github|npm|package manager|build system)", re.I)


def is_tech_topic(*texts):
    blob = " ".join(t or "" for t in texts)
    return bool(TECH_TOPIC.search(blob))


def _norm_title(t):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (t or "").lower())[:70]


# 信源可靠性权重：同样命中信号时，哪个来源更可能是"真需求"
# 依据是实测的可用率（人工抽查 top12）：
#   github_issue > reddit(垂直子版块) > browser(独立开发者社区) >> hn(泛话题评论)
SOURCE_WEIGHT = {
    "github_issue": 4.0,
    "upwork": 3.4,        # 有人正在付钱找人做事：付费意愿的最强证据
    "indeed": 3.2,        # 招聘 = 企业在出钱招人做的事（付费意愿证据）
    "stackoverflow": 2.8,  # 提问 = 未满足需求，密度高
    "twitter": 2.4,
    "xiaohongshu": 2.2,
    "zhihu": 2.0,
    "lobsters": 1.8,
    "devto": 1.8,
    "lesswrong": 1.6,
    "reddit": 2.6,
    "browser": 2.4,
    "producthunt": 2.2,
    "hn": 1.0,
    "github_trending": 2.0,
    "github_search": 2.0,
}


# ---------------------------------------------------------------- L1+L2 合并
def rule_filter(records, cfg):
    kept, dropped = [], []
    seen_titles = {}
    for r in records:
        if r.get("error"):
            dropped.append({**r, "drop_stage": "L1", "drop_reason": "采集失败"})
            continue

        # 跨子版块/跨信源的同一条内容：Reddit 交叉发帖会分到不同 t3 id，
        # 单靠 source_id 去重拦不住，必须再按标题归一化去重（实测踩过）。
        nt = _norm_title(r.get("title"))
        if len(nt) >= 20:
            if nt in seen_titles:
                dropped.append({**r, "drop_stage": "L1",
                                "drop_reason": f"与已有内容标题重复（{seen_titles[nt]}）"})
                continue
            seen_titles[nt] = r.get("source", "?")

        text = (r.get("text") or "")

        if r["source"] in REPO_SOURCES:
            if is_collection(text, r.get("repo", ""), r.get("topics")):
                dropped.append({**r, "drop_stage": "L1",
                                "drop_reason": "资源合集/教程仓库，无变现主体"})
                continue
            lvl, flags = supply_risk(r)
            r["supply_risk"] = lvl
            r["risk_flags"] = flags
            if lvl == "high":
                dropped.append({**r, "drop_stage": "L2",
                                "drop_reason": "供给侧高危：" + "；".join(flags)})
                continue
            if (r.get("stars_total") or 0) < cfg["min_stars"]:
                dropped.append({**r, "drop_stage": "L1",
                                "drop_reason": f"星标低于门槛 {cfg['min_stars']}"})
                continue
            # 仓库记录本身不构成"需求"，它只是一个待挖掘的供给对象
            r["record_type"] = "supply"

        elif r["source"] in TEXT_SOURCES:
            if NOISE_PAT.match(text.strip()[:60]) or len(text) < cfg["min_text_len"]:
                dropped.append({**r, "drop_stage": "L1", "drop_reason": "噪音/过短"})
                continue
            # 信源各自的"需求表达形式"不同，不能全用同一把尺子（实测第二批适配器
            # 接入后 0 条通过：SO 的提问、Indeed 的招聘帖都不含第一人称付费构式）：
            #   stackoverflow —— 问题式提问即需求代理（"how do I X" = X 难/没现成方案）
            #   indeed        —— 招聘帖 = 企业出钱让人做事，工资是最硬的付费证据
            if r["source"] == "stackoverflow":
                if QUESTION_PAT.search(f"{r.get('title', '')} {text[:120]}"):
                    r["pain_hits"] = ["question-form（提问即需求代理）"]
                    r["wtp_hits"] = r["strong_wtp_hits"] = []
                    r["record_type"] = "demand"
                    r["prefilter_score"] = _prefilter_score(r)
                    kept.append(r)
                    continue
                dropped.append({**r, "drop_stage": "L1", "drop_reason": "非问题式内容"})
                continue
            if r["source"] == "indeed":
                if HIRING_PAT.search(text):
                    r["pain_hits"] = ["hiring（企业出钱招人做 = 该任务值得花钱）"]
                    r["wtp_hits"] = r["strong_wtp_hits"] = []
                    r["record_type"] = "hiring"
                    r["prefilter_score"] = _prefilter_score(r)
                    kept.append(r)
                    continue
                dropped.append({**r, "drop_stage": "L1", "drop_reason": "非招聘正文"})
                continue
            r["pain_hits"] = pain_hits(text)
            r["wtp_hits"] = wtp_hits(text)
            r["strong_wtp_hits"] = strong_wtp_hits(text)
            # 门槛用"强付费构式"而不是裸词：这是零成本把需求侧精度从 ~0 拉起来的关键。
            if not r["pain_hits"] and not r["strong_wtp_hits"]:
                dropped.append({**r, "drop_stage": "L1",
                                "drop_reason": "未命中痛点/第一人称付费构式（词面碰撞噪音）"})
                continue
            # 话题域门槛：只在 HN 上启用，且**只看帖子标题**。
            # 教训：把评论正文也传进去等于没门槛——正文里几乎必然出现某个技术词，
            # 于是"出生率辩论"这类帖子照样放行（实测踩过）。
            # 判断"这条讨论属于什么话题"要靠帖子标题，不靠评论里零散的词。
            if r["source"] == "hn" and not is_tech_topic(r.get("title")):
                dropped.append({**r, "drop_stage": "L1",
                                "drop_reason": "帖子话题与软件/产品无关（空有付费措辞）"})
                continue
            r["record_type"] = "demand"
            r["prefilter_score"] = _prefilter_score(r)
            kept.append(r)
            continue

        r["prefilter_score"] = _prefilter_score(r)
        kept.append(r)

    kept.sort(key=lambda x: -x.get("prefilter_score", 0))
    return kept, dropped


def _prefilter_score(r):
    """便宜的排序分：决定谁优先进 LLM（LLM 有预算上限，必须让贵的算力花在刀刃上）"""
    s = SOURCE_WEIGHT.get(r["source"], 1.0)
    if r["source"] in REPO_SOURCES:
        if r.get("supply_risk") == "low":
            s += 1.5
        if r.get("license") in ("MIT", "Apache-2.0", "BSD-3-Clause", "ISC"):
            s += 2.5
        if (r.get("open_issues") or 0) >= 5:
            s += 1.5  # 有 issue 说明有真实用户在用
        age = _age_days(r.get("created_at"))
        if age and age < 1.1:
            s += 1.0  # 极新项目：趋势信号最强
    else:
        s += 2.5 * min(len(r.get("strong_wtp_hits", [])), 2)
        s += 0.8 * min(len(r.get("pain_hits", [])), 4)
        if r["source"] == "github_issue":
            s += 0.5 * min(r.get("comments", 0), 6)
            s += 0.6 * min(len(r.get("signal_hits", [])), 5)
        if r.get("points"):
            s += 0.4
    return round(s, 2)
