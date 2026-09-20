# -*- coding: utf-8 -*-
"""客户线索抽取：把「正在出钱找人做事」的公开线索抽成可执行的接活清单。

------------------------------------------------------------------ 为什么单独做这一层
run_windows.py 把线索**聚合成方向**，回答的是"什么值得做"。
但如果你缺的不是"做什么"而是"谁能付钱"，那聚合恰恰把最有用的信息压扁了：
报告里每个方向只展示 3 条证据，金额、原文、联系人全被丢掉。

本工具反过来做 —— **保留线索的个体身份**，回答"现在能接哪个活"：

    谁 / 要做什么 / 预算多少 / 原文 / 怎么联系 / 值不值得联系

两者互补，不替代：方向榜用于选赛道，线索表用于找第一个客户。

------------------------------------------------------------------ 三条判据（本工具的核心价值）
采集到处都有，值钱的是**筛选**。每条线索按三项打分：

  ① 钱    —— 文本里有没有明确的付费痕迹（有偿/预算/¥金额/时薪/bounty）
  ② 具体  —— 需求描述是否可评估（有动词+对象的"写个自动签到脚本"优于"求推荐工具"）
  ③ 新鲜  —— 多久之前发的（越新越可能还没被接走）

------------------------------------------------------------------ 必须内置供给方过滤（踩过的坑）
"有偿找人做脚本"这类查询会**同时**捞到两种方向相反的帖子：
    · 需求方：「有偿寻找一个代写游戏脚本的程序员」      ← 客户
    · 供给方：「个人纯手工接单，脚本定制，不成功不收费」 ← 竞争者，不是客户
实测知乎搜"有偿找人做脚本"，前 2 条里就有 1 条是供给方。
（这与 hunter/filter.py 里 r/forhire 的 [Hiring] vs [For Hire] 是同一类错误 ——
供给方广告被当成付费需求。那一处已修，这里必须一开始就做对。）

用法：
    python tools/leads.py                          # 全通道采集（需 Chrome + OpenCLI）
    python tools/leads.py --from-cache             # 只从已有 window_cache 抽（离线，秒出）
    python tools/leads.py --sources zhihu,forhire,bounty
    python tools/leads.py --min-score 3            # 只看值得联系的
"""
import argparse
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "out")

# ---------------------------------------------------------------- 判据词表
# ① 钱的痕迹：中文
MONEY_ZH = re.compile(
    r"(有偿|付费|预算|报酬|酬劳|酬金|报价|悬赏|赏金|茶水费|辛苦费|"
    r"价格可谈|价格好说|费用可谈|按次结算|日结|周结|"
    r"多少钱|愿意出|可以出|出资)", re.I)
# ① 钱的痕迹：英文
MONEY_EN = re.compile(
    r"(\bbudget\b|\bwilling to pay\b|\bpaid\b|\bbounty\b|\breward\b|\bprize\b|"
    r"\bpay(?:ing)?\s+for\b|\bhourly rate\b|\bper hour\b|\brate[: ]\s*\d)", re.I)

# ② 需求侧信号：有明确的"要做什么"
# 词表要覆盖真实表述 —— 实测漏了「寻找一个代写…的程序员」这种最常见的中文需求句式。
# 注意 "代做" 不放在这里：那是供给方动作（我代你做），放进来会污染需求判定。
DEMAND_ZH = re.compile(
    r"(求(?:一个|个|做|开发|定制|推荐|助|人)|"
    r"找人(?:做|开发|写)|寻找|招(?:人|募|聘)|聘请|"
    r"需要(?:一个|人|开发|做|能|找)|想(?:做|要|找)|"
    r"谁能(?:做|帮)|有没有(?:人|大神|大佬)(?:能|会|帮)|"
    r"外包|定制开发|帮(?:我|忙)?(?:写|做|开发)|"
    r"怎么(?:自动|批量)|如何(?:自动|批量)|"
    r"付费请|请人|有偿(?:求|找|请))", re.I)
DEMAND_EN = re.compile(
    r"(\[hiring\]|\bhiring\b|looking (?:for|to hire)|need (?:someone|a dev|help)|"
    r"\bbounty\b|\bwanted\b|who can (?:build|make)|can anyone (?:build|make))", re.I)

# ③ 供给方信号（**反方向**，必须过滤掉）
SUPPLY_ZH = re.compile(
    r"(本人|个人|专业|团队)?(?:接单|承接|代做|可做|可接|接活|包做|"
    r"不成功不收费|满意再付款|先做后付|"
    r"多年经验|十年经验|五年经验|技术过硬|"
    r"提供.{0,6}服务|长期接单|欢迎咨询|私信我|联系我详聊|"
    r"低价|价格优惠|物美价廉)", re.I)
SUPPLY_EN = re.compile(
    r"(\[for ?hire\]|\bfor hire\b|\bavailable for\b|hire me|"
    r"my (?:portfolio|services|rates)|i(?:'m| am) a freelancer|"
    r"years of experience|\bmy rate\b|open to (?:work|opportunities))", re.I)

# 时间：中文相对时间 / 英文相对时间
AGE_PATTERNS = [
    (re.compile(r"(\d+)\s*(?:分钟|minutes?)\s*前"), 1 / 1440),
    (re.compile(r"(\d+)\s*(?:小时|hours?)\s*前"), 1 / 24),
    (re.compile(r"(\d+)\s*(?:天|days?)\s*前"), 1),
    (re.compile(r"(\d+)\s*(?:周|weeks?)\s*前"), 7),
    (re.compile(r"(\d+)\s*(?:个?月|months?)\s*前"), 30),
]


def _age_days(rec):
    """从文本或时间戳推断"多久之前"。取不到返回 None（不当成新鲜）。"""
    txt = f"{rec.get('text') or ''} {rec.get('title') or ''}"
    for pat, mult in AGE_PATTERNS:
        m = pat.search(txt)
        if m:
            try:
                return int(m.group(1)) * mult
            except Exception:
                pass
    # ISO 日期 / 时间戳
    for key in ("created_at", "published_at", "issue_created", "updated_at"):
        v = rec.get(key)
        if not v:
            continue
        try:
            if isinstance(v, (int, float)) or str(v).isdigit():
                ts = float(v)
                if ts > 1e11:
                    ts /= 1000
                return max((time.time() - ts) / 86400, 0)
            s = str(v)[:19].replace("T", " ").replace("Z", "")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return max((time.time() - time.mktime(time.strptime(
                        s[:len(time.strftime(fmt))], fmt))) / 86400, 0)
                except Exception:
                    continue
        except Exception:
            continue
    return None


# ① 钱的痕迹：具体金额。**必须判合理性**，否则会被 ID 骗过去。
# 实测踩过：GitHub bounty 的 issue 里出现 `$239398281948585883`（18 位，是 id 不是钱），
# 原实现直接判 money=3，结果 26 条垃圾把 top30 挤满、国内通道一条都进不来。
_AMT_RE = re.compile(r"([¥￥$])?\s?(\d[\d,.]*)\s*(k|K|万|千|元|块|美元|usd|rmb|cny)?")
# 金额后面的计价方式 —— 决定它是"总额"还是"单价/周期价"，两者不能同一把尺子量
_PERIOD_RE = re.compile(
    r"(\s*/\s*(?:小时|时|天|次|单|篇|h|hr|hour|day|week|month)"
    r"|\s*(?:per|a)\s*(?:hour|day|week|month)"
    r"|\s*(?:hourly|weekly|monthly|daily)"
    r"|\s*(?:时薪|日薪|周薪|月薪))", re.I)
# 金额附近出现这些词，即使没写货币符/单位也认定是钱（"价格 500"、"预算 3000"）
_MONEY_WORD_NEAR = re.compile(
    r"(预算|价格|报价|报酬|酬劳|酬金|费用|薪酬|日结|周结|时薪|工资|"
    r"\bbudget\b|\brate\b|\bprice\b|\bpay\b|\bhourly\b|\bper hour\b|\bfee\b)", re.I)


def amount_info(text):
    """抽出金额，并判断它的**量级**与**计价方式**。

    为什么要看量级（踩过的坑）：原实现只看"有没有金额"，于是
    $50/week 的营销零工和 $3000 的悬赏拿同样的 money=3、并排在最前面 ——
    实测榜单前 12 条里有 4 条是 $18/h、$50/week 这类低价值零工，
    把真正值得看的挤了下去。

    返回 (归一化金额, 计价方式)，计价方式 ∈ {"total", "hour", "month"}；
    取不到返回 (None, "")。
    """
    best = None
    kind = ""
    for m in _AMT_RE.finditer(text or ""):
        cur, num, unit = m.group(1), m.group(2), (m.group(3) or "")
        digits = re.sub(r"[^\d]", "", num or "")
        if not digits or len(digits) > 7:      # 8 位以上基本是 id / 日期
            continue
        try:
            v = float(digits)
        except Exception:
            continue
        if unit in ("k", "K", "千"):
            v *= 1000
        elif unit == "万":
            v *= 10000
        if not (10 <= v <= 5_000_000):
            continue
        ctx = (text or "")[max(0, m.start() - 12): m.end() + 12]
        if not (cur or unit or _MONEY_WORD_NEAR.search(ctx)):
            continue
        # 计价方式：金额紧跟着 /小时 或 时薪 之类 → 单价；/周 /月 → 周期价
        tail = (text or "")[m.end(): m.end() + 14]
        p = _PERIOD_RE.match(tail)
        k = "total"
        if p:
            t = p.group(0).lower()
            if re.search(r"小时|时|h\b|hr|hour|时薪", t):
                k = "hour"
            elif re.search(r"week|月|month|周|weekly|monthly", t):
                k = "month"
        if best is None or v > best:
            best, kind = v, k
    return best, kind


def money_level(text):
    """0-3：金额的**量级**分级。三种计价方式用三把尺子（不能混着比）。

    阈值是按"这算不算一个正经的付费委托"定的，不是按绝对值：
      · 一次性 ≥500 → 3（$800 的自动化脚本 ≈ 5700 元，是真活）
      · 时薪   ≥50  → 3（$20/h 偏低但不至于当零工）
      · 月均   ≥1500 → 3（$50/week ≈ 200/月，明显是零工 → 1）
    这样 $50/week 和 $3000 不会再同分。

    已知局限：不区分币种，500 元与 $500 同等对待 —— 会低估人民币小额单、
    高估美元小额单。要精确得引入汇率，对"排序"这个用途不值当。
    """
    v, kind = amount_info(text)
    if v is None:
        return 0
    if kind == "hour":
        return 3 if v >= 50 else (2 if v >= 20 else 1)
    if kind == "month":
        monthly = v * 4 if re.search(r"week|周|weekly", text or "", re.I) else v
        return 3 if monthly >= 1500 else (2 if monthly >= 500 else 1)
    return 3 if v >= 500 else (2 if v >= 150 else 1)


def has_plausible_amount(text):
    """文本里有没有「像价格」的金额。

    保留这个薄封装是为了向后兼容（单测与调用方都在用）；
    真正的解析在 amount_info()，它还会给出量级与计价方式。
    """
    return amount_info(text)[0] is not None


def _money_score(text):
    """0-3：有金额时按**量级**给分；没金额时才退回数付费词。

    量级比"有没有"重要得多 —— 原实现只看有没有，导致 $50/week 和 $3000
    同样拿 3 分、并排在最前面。
    """
    lvl = money_level(text)
    if lvl:
        return lvl
    n_zh = len(set(MONEY_ZH.findall(text)))
    n_en = len(set(m.group(0).lower() for m in MONEY_EN.finditer(text)))
    if n_zh + n_en >= 2:
        return 2
    if n_zh or n_en:
        return 1
    return 0


def _spec_score(text):
    """0-3：需求描述的具体程度。有动词+对象、篇幅够长 → 高。"""
    if not text or len(text) < 30:
        return 0
    s = 0
    if DEMAND_ZH.search(text) or DEMAND_EN.search(text):
        s += 1
    # 出现技术对象词 = 需求可评估
    if re.search(r"(脚本|爬虫|插件|工具|系统|网站|小程序|app|api|自动化|数据|"
                 r"script|scraper|plugin|tool|api|automation|bot|pipeline)", text, re.I):
        s += 1
    if len(text) >= 120:
        s += 1
    return min(s, 3)


def is_supply_side(text, title=""):
    """是不是"我在卖服务"（供给方）。供给方不是客户，必须过滤。

    判据优先级：标题里出现供给标记 → 直接判供给；
    否则看正文的供给信号是否**明显压过**需求信号。
    """
    head = title or ""
    if SUPPLY_ZH.search(head) or SUPPLY_EN.search(head):
        # 标题里同时有需求标记时不武断（如"求推荐接单平台"）
        if not (DEMAND_ZH.search(head) or DEMAND_EN.search(head)):
            return True
    n_sup = len(set(SUPPLY_ZH.findall(text))) + \
        len(set(m.group(0).lower() for m in SUPPLY_EN.finditer(text)))
    n_dem = len(set(DEMAND_ZH.findall(text))) + \
        len(set(m.group(0).lower() for m in DEMAND_EN.finditer(text)))
    return n_sup > 0 and n_sup >= n_dem


def title_quality(title):
    """标题是否承载了足够信息。

    为什么需要：GitHub bounty 里混着大量占位/刷量 issue —— 实测抓到
    「[Bounty] Bounty」「[Bounty] EKEODKDE9DKE9DO BOUNTY」这种，标题本身没有信息，
    但正文里凑得出一个金额，于是拿到满分。这类必须在标题层就挡住。
    """
    t = re.sub(r"\[[^\]]*\]", " ", title or "")      # 去掉 [Bounty] / [Hiring] 这类标记
    t = re.sub(r"[¥￥$]\s?[\d,.]*", " ", t)          # 去掉金额
    t = re.sub(r"[\d\W_]+", " ", t)                  # 去掉数字与符号
    # 乱码检测：长的大写连串（EKEODKDE9DKE9DO）会被当成"单词"骗过词数判断。
    # 真实标题不会整串大写 —— 用大写占比 + 最长 token 长度一起卡。
    letters = re.sub(r"[^A-Za-z]", "", t)
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        longest = max((len(w) for w in t.split()), default=0)
        if upper_ratio > 0.8 and longest >= 8:
            return False
    words = [w for w in t.split() if len(w) >= 3]
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
    return cjk >= 4 or len(words) >= 2


def repo_of(url):
    """从 URL 里取"同一个来源主体"的标识，用于限制单源刷量。

    GitHub 取 owner/repo（一个仓库连发 10 条 issue 属于刷量）；
    其他站点取域名+路径首段。
    """
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", url or "")
    if m:
        return f"gh:{m.group(1)}/{m.group(2)}".lower()
    m = re.match(r"https?://([^/]+)/([^/#?]*)", url or "")
    if m:
        return f"{m.group(1)}/{m.group(2)}".lower()
    return ""


def score_lead(lead):
    """综合分。钱权重最高 —— 因为它最接近"这单能成"。"""
    money = _money_score(lead["text"])
    # 询价帖**不是委托**：对方还在问"大概多少钱"，没有决定要做。
    # 实测踩过：一条「请人做小程序大概多少钱？」因为深读后的正文里有人报了价
    # （2 万到 20 万），money 拿到 3 分、排进前三 —— 但那条帖子里没有人要雇人。
    # 所以询价类的钱分**封顶 2**：它值得联系（进候选名单），但不该和真委托同权。
    if lead_kind(lead) == "inquiry":
        money = min(money, 2)
        lead["kind_note"] = "询价帖（非委托，钱分封顶 2）"
    spec = _spec_score(lead["text"])
    age = lead.get("age_days")
    fresh = 2 if age is not None and age <= 3 else (1 if age is not None and age <= 14 else 0)
    score = money * 1.5 + spec * 1.0 + fresh * 1.0
    lead.update({"money": money, "spec": spec, "fresh": fresh, "score": round(score, 1)})
    # 供给方直接判"跳过"：它可能同时命中金额词（"我的报价 $20/h"），
    # 打分高但方向是反的。在这里就压掉，避免调用方忘记过滤时把它当客户。
    if lead.get("supply_side"):
        lead["verdict"] = "跳过（供给方）"
        return lead
    if lead.get("junk_title"):
        # 标题没有信息（"[Bounty] Bounty"、"EKEODKDE9DKE9DO"）——正文凑得出金额也不行。
        lead["verdict"] = "跳过（标题无信息）"
        return lead
    # 阈值刻意收紧：实测原阈值下 30/30 全判"值得联系"，等于没有筛选。
    # 但新鲜度**不当门槛** —— 很多线索没写时间，不该因此判死；它只参与排序。
    if money >= 3 and spec >= 2:
        lead["verdict"] = "值得联系"
    elif (money >= 2 and spec >= 2) or (money >= 1 and spec >= 1):
        lead["verdict"] = "待看"
    else:
        lead["verdict"] = "跳过"
    return lead


def cap_per_repo(leads, max_per_repo=2):
    """同一个来源主体最多取 N 条 —— 防止单个刷量源把榜单占满。

    实测（2026-09-20）：github_bounty 里 `zhangjiayang6835-cyber/bounty-plaza`
    一个仓库就贡献了 6+ 条，标题还都是占位符。配额管的是"信源"，这一层管的是"信源内部的单个主体"。
    两道一起才够：信源配额防跨源霸榜，主体上限防同源内刷量。
    """
    cnt, out = {}, []
    for x in leads:
        k = x.get("group") or ""
        if k:
            if cnt.get(k, 0) >= max_per_repo:
                continue
            cnt[k] = cnt.get(k, 0) + 1
        out.append(x)
    return out


def quota_select(leads, top, per_source_min=3):
    """按信源配额选样：每个信源先保底 N 条，剩余名额按分数抢。

    为什么必须做 —— 这是项目自己在 P0-3 学到的教训，原文：
    「只要采集层允许噪音源海量进入，再好的下游过滤也救不回来。
      信源配额是防止『劣币驱逐良币』的必要机制。」
    实测（2026-09-20）：不加配额时，GitHub bounty 靠 40 条的量把 top30 全占了，
    知乎/小红书/V2EX 一条都进不来 —— 而国内线索恰恰是最需要的。
    配额放在**渲染前**，不是打分后：打分解决"哪条更好"，配额解决"谁有资格被看见"。
    """
    by = {}
    for x in leads:
        by.setdefault(x["source"], []).append(x)
    picked, used = [], set()
    for src in by:
        for x in by[src][:per_source_min]:
            if len(picked) >= top:
                break
            picked.append(x)
            used.add(id(x))
    for x in leads:
        if len(picked) >= top:
            break
        if id(x) not in used:
            picked.append(x)
            used.add(id(x))
    picked.sort(key=lambda x: -x["score"])
    return picked[:top]


# ---------------------------------------------------------------- 归一化
def _text_of(rec):
    parts = [rec.get("title") or "", rec.get("text") or "",
             rec.get("body") or "", rec.get("description") or ""]
    return " ".join(" ".join(p.split()) for p in parts if p).strip()


def to_lead(rec, source):
    txt = _text_of(rec)
    title = rec.get("title") or ""
    lead = {
        "source": source,
        "title": title[:120],
        "url": rec.get("url") or "",
        "text": txt[:1200],
        "author": rec.get("author") or "",
        "age_days": _age_days(rec),
        "group": repo_of(rec.get("url") or ""),
        # 带上 record_type：项目已有通道（bounty/forhire）在 hunter/filter.py
        # 已做过供需过滤，缓存复用时要能识别出来、不再二次判断。
        "record_type": rec.get("record_type") or "",
        "supply_side": is_supply_side(txt, title),
        "junk_title": not title_quality(title),
    }
    lead["tech"] = tech_tags(lead)          # 能力画像的词汇表，见 TECH_TAGS
    # 缓存复用时保留深读痕迹 —— 否则重跑会把"已深读"当成"没读到正文"，
    # 于是话术里误报一句"建议先点开链接看一眼"（实测踩过）。
    for k in ("deep", "deep_note"):
        if k in rec:
            lead[k] = rec[k]
    return score_lead(lead)


# ---------------------------------------------------------------- 各通道采集
ZH_QUERIES = ["有偿 找人做 脚本", "有偿 开发 小程序", "求开发 预算",
              "找人做 爬虫", "有偿 定制 工具"]
XHS_QUERIES = ["求推荐 自动化工具", "有偿 找人做", "求开发 小程序"]
V2EX_NODES = ["outsourcing", "jobs"]     # 外包 / 酷工作


def _oc():
    from hunter import opencli as oc
    return oc


def collect_zhihu(limit=20):
    oc = _oc()
    out, health = [], []
    for q in ZH_QUERIES:
        d, m = oc.run(["zhihu", "search", q, "--limit", str(limit)], timeout=120)
        rows = oc._rows(d) or []
        for r in rows:
            rec = oc._norm("zhihu", r, f"search:{q}")
            rec["source"] = "zhihu"
            rec["_query"] = q
            out.append(rec)
        health.append({"source": f"zhihu:search[{q[:14]}]", "count": len(rows),
                       "ok": m.get("ok", False), "note": (m.get("note") or "")[:70]})
    return out, health


def collect_xiaohongshu(limit=20):
    oc = _oc()
    out, health = [], []
    for q in XHS_QUERIES:
        d, m = oc.run(["xiaohongshu", "search", q, "--limit", str(limit)], timeout=120)
        rows = oc._rows(d) or []
        for r in rows:
            rec = oc._norm("xiaohongshu", r, f"search:{q}")
            rec["source"] = "xiaohongshu"
            rec["_query"] = q
            out.append(rec)
        health.append({"source": f"xhs:search[{q[:14]}]", "count": len(rows),
                       "ok": m.get("ok", False), "note": (m.get("note") or "")[:70]})
    return out, health


def collect_v2ex(limit=20):
    """V2EX 外包/酷工作节点 —— 国内最接近 r/forhire 的入口。

    注：v2ex 节点列表是**原生榜**（平台排序），不需要关键词，所以这里只给节点名。
    """
    oc = _oc()
    out, health = [], []
    for node in V2EX_NODES:
        d, m = oc.run(["v2ex", "node", node, "--limit", str(limit)], timeout=120)
        rows = oc._rows(d) or []
        for r in rows:
            rec = oc._norm("v2ex", r, f"node:{node}")
            rec["source"] = "v2ex"
            rec["_query"] = node
            out.append(rec)
        health.append({"source": f"v2ex:node[{node}]", "count": len(rows),
                       "ok": m.get("ok", False), "note": (m.get("note") or "")[:70]})
    return out, health


def collect_project_channels():
    """复用项目已有的两条通道：GitHub 赏金 + r/forhire 的 [Hiring]。

    这两条**已经做过供需过滤**（hunter/filter.py 的 FORHIRE_DEMAND / github_bounty），
    所以这里直接拿原始记录，不必再过一遍 is_supply_side。
    """
    from hunter import sources as S
    out, health = [], []
    try:
        rs, h = S.github_bounties(per_page=40)
        out += rs
        health.append({**h, "source": "github_bounty"})
    except Exception as e:
        health.append({"source": "github_bounty", "count": 0, "ok": False,
                       "note": str(e)[:80]})
    try:
        rs, h = S.reddit_rss(["forhire"], spacing=0)
        out += rs
        health.append({**h, "source": "reddit:forhire"})
    except Exception as e:
        health.append({"source": "reddit:forhire", "count": 0, "ok": False,
                       "note": str(e)[:80]})
    return out, health


# ---------------------------------------------------------------- 深读正文
# 为什么需要（实测局限）：知乎/小红书的**搜索结果不含正文**，只有标题。
# 于是「钱」和「具体」两列对国内线索系统性偏低 —— 而国内线索恰恰是最需要的。
# 二段式解决：先用标题零成本粗排，再对头部 N 条深读正文后重打分。
#
# 各命令实测（2026-09-20）：
#   v2ex  /t/<id>                       → `v2ex topic <id>`             ✅
#                                          （沙箱里 502 是代理挡了 v2ex，本机应可用）
#   zhihu /question/<qid>/answer/<aid>  → `zhihu answer-detail <url>`   ✅ 附带 created_at
#   zhihu /question/<qid>               → `zhihu question <qid>`        ✅
#   zhihu /p/<id>（专栏文章）             → 无对应命令                     ❌
#   xiaohongshu search_result/explore   → Navigation rejected（需登录）  ❌
#
# 深读的额外收益：返回体里带 created_at，顺手补上原本缺失的新鲜度。
# 深读的真实价值（实测）：一条标题看着像需求的知乎回答，正文是「简单点，
# 淘宝直接搜脚本编辑」—— 不是需求，是建议。**只有读了正文才知道。**
DEEP_SUPPORTED = ("v2ex", "zhihu")


def _flatten_text(obj, limit=2500):
    """递归收集 JSON 里的字符串 —— 各适配器字段名不统一，硬编码字段会漏。"""
    out = []

    def walk(o):
        if sum(len(s) for s in out) > limit:
            return
        if isinstance(o, str):
            s = " ".join(o.split())
            if len(s) >= 8:
                out.append(s)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return " ".join(out)[:limit]


def _find_time(obj):
    """从深读返回体里找发布时间。返回原始字符串或 None。"""
    keys = ("created_at", "created", "published_at", "time", "timestamp")
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in keys and isinstance(v, (str, int, float)):
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return found[0] if found else None


def deep_read(lead, timeout=90):
    """按来源深读正文。返回 (补充正文, 发布时间或 None, 说明)。"""
    src, url = lead.get("source"), lead.get("url") or ""
    argv = None
    if src == "v2ex":
        m = re.search(r"/t/(\d+)", url)
        if m:
            argv = ["v2ex", "topic", m.group(1)]
    elif src == "zhihu":
        if re.search(r"/answer/(\d+)", url):
            argv = ["zhihu", "answer-detail", url]
        else:
            m = re.search(r"/question/(\d+)", url)
            if m:
                argv = ["zhihu", "question", m.group(1), "--limit", "3"]
    if not argv:
        return "", None, "该来源/URL 形式不支持深读"
    try:
        d, meta = _oc().run(argv, timeout=timeout)
    except Exception as e:
        return "", None, f"{type(e).__name__}: {str(e)[:50]}"
    if not meta.get("ok"):
        return "", None, (meta.get("note") or "深读失败")[:60]
    return _flatten_text(d), _find_time(d), ""


def deep_read_top(leads, n=8, timeout=90):
    """深读正文并重打分。返回 (成功条数, 不支持的条数)。

    **选谁读**（这里踩过一次坑）：第一版取 `leads[:n]`（按分数排的前 N 条），
    结果实测"深读 0 条" —— 因为头部全是分数高的 github_bounty（正文本来就有），
    而真正缺正文的国内线索分数低、排在后面，一条都没被读到。
    正确做法是**按"是否支持深读"筛，再按分数取前 N**：让贵的算力花在
    "读了才有信息"的条目上，而不是花在本来就完整的条目上。
    """
    cand = [x for x in leads if x.get("source") in DEEP_SUPPORTED][:n]
    n_unsupported = sum(1 for x in leads if x.get("source") not in DEEP_SUPPORTED)
    done = 0
    for x in cand:
        extra, ts, note = deep_read(x, timeout=timeout)
        x["deep"] = bool(extra)
        x["deep_note"] = note
        if not extra:
            continue
        done += 1
        # 正文并入 text 后重打分：预算和具体要求往往只在正文里
        x["text"] = (x["text"] + " " + extra)[:2400]
        if x.get("age_days") is None and ts is not None:
            x["age_days"] = _age_days({"created_at": ts})
        # 供给方可能只在正文里露出来（标题看不出来），重打分时一并复核
        x["supply_side"] = x.get("supply_side") or is_supply_side(x["text"], x["title"])
        score_lead(x)
    return done, n_unsupported


# ---------------------------------------------------------------- 应征话术
# 为什么单独做这一层：线索表解决"有没有活"，但真正让人卡住的是
# **打开对话框不知道写什么**。对不擅长主动推销的人，这个门槛比"找不到活"更高。
# 一段不用现想的话术，能把"要不要联系"从一次决策降成一次复制粘贴。
#
# 三条写法原则（都是从"对方会怎么读"倒推的）：
#   ① 先证明你读懂了他的需求 —— 引用他的原话，而不是群发的自我介绍
#   ② 问具体的技术问题，不问"请问需要吗" —— 问对问题本身就是能力证明
#   ③ 主动给"先出方案再决定"的台阶 —— 降低对方的决策成本，也降低你的承诺风险
#
# 反面清单（这些一写就减分）：群发式自我介绍、一上来问预算、保证"包您满意"、
# 长篇大论列技术栈、"我什么都能做"。

# 按技术对象定制那句"具体问题" —— 问对问题比问得多重要。
# **必须双语**：踩过的坑 —— 英文线索用了英文模板，但技术问题还是中文的，
# 发出去像机翻。语言要跟着线索走，不能只跟着来源走（V2EX 上也有英文帖）。
TECH_QUESTIONS = [
    (re.compile(r"(爬虫|scraper|scraping|数据采集|抓取)", re.I),
     "目标站点有没有反爬（验证码/频率限制/登录态）？大概的数据量级和更新频率是多少？",
     "Does the target site have anti-scraping measures (captcha / rate limits / login)? "
     "What's the data volume and refresh frequency?"),
    (re.compile(r"(小程序|mini ?program|微信开发)", re.I),
     "是从零开发还是在现有基础上改？主体资质（备案/认证）这块由哪边负责？",
     "Is this built from scratch or modifying something existing? "
     "Who handles the platform account and registration?"),
    (re.compile(r"(插件|extension|userscript)", re.I),
     "目标平台和版本是什么？需不需要上架商店（涉及审核周期）？",
     "Which platform and version? Does it need to be published to a store "
     "(that adds a review cycle)?"),
    (re.compile(r"(脚本|自动化|automat|script)", re.I),
     "需要跑在什么环境（Windows / Mac / 服务器）？触发方式是手动还是定时？",
     "What environment does it need to run in (Windows / Mac / server)? "
     "Is the trigger manual or scheduled?"),
    (re.compile(r"(接口|api|对接|集成|integrat)", re.I),
     "对方接口有文档吗，还是需要自己抓包？有没有测试环境？",
     "Is there API documentation, or does it need to be reverse-engineered? "
     "Is there a sandbox environment?"),
    (re.compile(r"(数据处理|清洗|excel|报表|数据分析)", re.I),
     "原始数据现在是什么形式（Excel / 数据库 / 接口）？输出要什么格式？",
     "What form is the source data in (Excel / database / API)? "
     "What output format do you need?"),
    (re.compile(r"(修复|bug|报错|error|fix|corrupt|regression)", re.I),
     "这个问题是稳定复现还是偶发？有没有能复现的最小用例或环境说明？",
     "Is this consistently reproducible or intermittent? "
     "Is there a minimal repro case or environment notes?"),
]
TECH_QUESTION_DEFAULT = "现在的做法是什么、卡在哪一步？"
TECH_QUESTION_DEFAULT_EN = "What's the current approach, and where exactly does it break?"


def _lang_of(lead):
    """按**内容**判断该用中文还是英文 —— 不能只看来源。

    踩过的坑：第一版用 `cjk == 0` 判断，只要正文里出现**一个**中文字就翻成中文，
    于是一条全英文的 GitHub 悬赏被套上了中文话术。
    改为看占比：拉丁字母数 > 中文数 × 3 才算英文。
    """
    t = f"{lead.get('title') or ''} {lead.get('text') or ''}"
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
    latin = len(re.findall(r"[A-Za-z]", t))
    return "en" if (latin > 20 and latin > cjk * 3) else "zh"


def _specific_question(text, lang="zh"):
    for pat, zh, en in TECH_QUESTIONS:
        if pat.search(text or ""):
            return en if lang == "en" else zh
    return TECH_QUESTION_DEFAULT_EN if lang == "en" else TECH_QUESTION_DEFAULT


def _clean_title(title):
    """去掉标题开头的标记（[Bounty] / [Hiring] / [苏州] …）。

    踩过的坑：直接嵌进话术会出现「[Bounty] [Bounty $1,500] …」这种重复，
    读起来像机器拼的。金额信息已由 tips 单独提示，标题里去掉更干净。
    """
    t = re.sub(r"^(\[[^\]]{0,24}\]\s*)+", "", (title or "").strip())
    return t.strip() or (title or "").strip()


def _norm_key(s):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (s or "").lower())


def _restate(lead, limit=100):
    """复述对方的需求 —— 用他自己的话，这是"我认真读了"的最强证明。

    踩过的坑：第一版直接取"含技术对象的第一句"，而 record.text 是 `标题 + 正文`，
    第一句往往就是标题 → 话术里出现「看到你发的「X」。你提到：X」的重复。
    所以这里**必须排除与标题几乎相同的那句**，取不到就返回空串让调用方省略。
    """
    title_key = _norm_key(lead.get("title"))
    text = " ".join((lead.get("text") or "").split())
    pat = re.compile(r"(脚本|爬虫|插件|小程序|工具|系统|网站|app|api|自动化|数据|"
                     r"script|scraper|plugin|tool|api|automation|bot)", re.I)
    for s in re.split(r"[。！？!?\n]+", text):
        s = s.strip()
        if not (12 <= len(s) <= 200) or not pat.search(s):
            continue
        k = _norm_key(s)
        # 与标题重复度太高就跳过（前 40 字相同，或标题被包含）
        if title_key and (k[:40] == title_key[:40] or title_key[:20] in k):
            continue
        return s[:limit]
    return ""


# 招聘帖问什么 —— 与项目类完全不同。
# 踩过的坑：第一版对所有类型都问"需要跑在什么环境"，对「量化策略研究员」这种
# 岗位帖完全是错位的，一眼就能看出是模板群发。
HIRING_QUESTIONS_ZH = [
    "这个岗位接受远程或兼职吗？",
    "团队现在多少人、主要技术栈是什么？",
    "面试流程大概几轮，有没有笔试或作业环节？",
]
HIRING_QUESTIONS_EN = [
    "Is this role open to remote or part-time?",
    "How big is the team, and what's the main tech stack?",
    "What does the interview process look like — how many rounds, any take-home?",
]
# 询价帖问什么 —— 目标是进入候选名单，不是拿下这一单
INQUIRY_DIMENSIONS_ZH = ("数据量/规模", "有没有现成的接口或方案", "要不要长期维护")
INQUIRY_DIMENSIONS_EN = ("data volume / scope", "whether an API or existing solution already exists",
                         "whether ongoing maintenance is expected")


def _kind_of_text(text, lead):
    """从一段文本判类型。返回类型名或 ""（判不出来）。"""
    if lead.get("source") == "github_bounty" or re.search(r"\bbounty\b|赏金", text, re.I):
        return "bounty"
    # 注意：**不要用单字「薪」** —— 它会被"薪资/薪酬/加薪"等各种语境命中，
    # 实测因此把一条询价帖误判成招聘帖。要用完整的词。
    if re.search(r"(招聘|诚聘|招人|热招|hiring|job|岗位|薪水|月薪|年薪|"
                 r"任职要求|岗位职责)", text, re.I):
        return "hiring"
    # 「价格」单用太宽（"价格可谈"会出现在任何外包帖里），要带上下文
    if re.search(r"(多少钱|大概多少|报价|预算多少|预算怎么|费用大概|收费|"
                 r"怎么算钱|how much|pricing)", text, re.I):
        return "inquiry"
    return ""


def lead_kind(lead):
    """线索类型 —— 决定话术的落点。四种类型的语气和问题完全不同。

    **优先只看标题**（与 tech_tags 同一个教训）：深读后的正文是一整段讨论，
    里面什么词都有。实测踩过 —— 一条「请人做小程序大概多少钱？」因为正文里
    有人提到「月薪」，被误判成招聘帖，于是询价的钱分封顶失效、又排回了前三。
    标题才说明这条线索「是什么」；标题判不出类型时才退回全文。
    """
    head = lead.get("title") or ""
    k = _kind_of_text(head, lead)
    if k:
        return k
    return _kind_of_text(f"{head} {lead.get('text') or ''}", lead) or "outsourcing"


def apply_script(lead):
    """给一条线索生成可直接复制的应征话术 + 针对性提醒。

    返回 {"kind", "kind_label", "message", "tips": [...]}。

    **四种类型用四套模板**（踩过的坑）：第一版只有"项目式"一套，结果对一条
    「量化策略研究员」招聘帖写"这个我可以做"、还问它"跑在什么环境" ——
    错位得非常明显，一眼能看出是模板群发。类型判断错了，话术还不如不写。
    """
    kind = lead_kind(lead)
    lang = _lang_of(lead)          # 按内容判语言，不按来源
    title = _clean_title(lead.get("title"))
    restate = _restate(lead)       # 可能与标题重复时返回空串
    q = _specific_question(lead.get("text"), lang)
    has_amount = lead.get("money", 0) >= 3
    en = (lang == "en")

    if kind == "bounty":
        body = (f'Hi — I saw your bounty "{title}".\n\n'
                "I can take this on. Two quick questions before I start:\n\n"
                f"1. {q}\n"
                "2. What counts as done here — a merged PR, or passing a specific test?\n\n"
                "I'll send a short plan and an estimate first, "
                "so you can decide before I write any code.") if en else (
                f"你好，看到你发的悬赏「{title}」。\n\n"
                "这个我可以做。动手前想先确认两点：\n\n"
                f"1. {q}\n"
                "2. 什么算完成 —— 合并 PR，还是通过某个具体测试？\n\n"
                "我可以先给一个实现思路和报价，你看合适再往下走；不合适也没关系。")

    elif kind == "hiring":
        qs = HIRING_QUESTIONS_EN if en else HIRING_QUESTIONS_ZH
        if en:
            body = (f"Hi — I saw your posting \"{title}\".\n\n"
                    "Three quick questions before I apply:\n\n"
                    + "".join(f"{i}. {x}\n" for i, x in enumerate(qs, 1))
                    + "\nHappy to send a CV and talk through what I've built "
                      "if the fit looks right.")
        else:
            body = (f"你好，看到你的招聘帖「{title}」。\n\n"
                    "投递前想先确认三点：\n\n"
                    + "".join(f"{i}. {x}\n" for i, x in enumerate(qs, 1))
                    + "\n合适的话我可以发一份简历，也想了解一下你们目前在做的方向。")

    elif kind == "inquiry":
        dims = INQUIRY_DIMENSIONS_EN if en else INQUIRY_DIMENSIONS_ZH
        dim_txt = " / ".join(dims)
        body = (f"Hi — saw you asking about \"{title}\".\n\n"
                f"Price for this kind of work mainly comes down to three things: {dim_txt}.\n\n"
                "If you can tell me roughly where you land on those, I can give you a "
                "concrete number — or a smaller fixed-scope version first, "
                "so you can check the direction before committing.") if en else (
                f"你好，看到你在问「{title}」。\n\n"
                f"这类需求的价格主要看三件事：{dim_txt}。\n\n"
                "如果你能说一下大致情况，我可以给一个具体报价；"
                "也可以先按最小可用的范围报一个小版本，你觉得方向对再往上加。")

    else:  # outsourcing
        if en:
            body = (f'Hi — I saw your post "{title}".\n\n'
                    + (f"You mentioned: {restate}\n\n" if restate else "")
                    + "I can take this on. Two quick questions before I start:\n\n"
                    + f"1. {q}\n"
                      "2. What's the deliverable and the acceptance criteria "
                      "(source / deployment / docs, and what counts as done)?\n\n"
                      "I'll send a short plan and an estimate first, "
                      "so you can decide before I start.")
        else:
            body = (f"你好，看到你发的需求「{title}」。\n\n"
                    + (f"你提到：{restate}\n\n" if restate else "")
                    + "这个我可以做。动手前想先确认两点：\n\n"
                    + f"1. {q}\n"
                      "2. 交付形式和验收标准（源码 / 部署 / 文档，以及怎么算做完）\n\n"
                      "我可以先给一个实现思路和报价，你看合适再往下走；不合适也没关系。")

    tips = []
    if has_amount:
        tips.append("对方已经写了金额 —— **不要主动压价**，先把范围与验收标准问清楚；"
                    "范围没谈拢时压价等于替自己挖坑。")
    else:
        tips.append("这条没有明确预算 —— 先问范围（要做什么、做到什么程度），"
                    "**别先报价**。范围不清楚时任何报价都会变成你的义务。")
    if kind == "hiring":
        tips.append("这是招聘帖：先确认是否接受**远程/兼职**（很多岗位默认坐班），"
                    "再谈薪 —— 顺序反了会浪费双方时间。")
    elif kind == "inquiry":
        tips.append("对方只是在问价、还没决定做 —— 目标不是拿下，"
                    "是**进入他的候选名单**。给判断框架比给数字更有用。")
    elif kind == "bounty":
        tips.append("开源悬赏通常要求提 PR 并被合并才结算 —— "
                    "先确认结算条件（合并即付 / 审核通过 / 有时间窗），别做完才发现拿不到。")
    if lead.get("age_days") is not None and lead["age_days"] > 7:
        tips.append(f"这条已经 {lead['age_days']:.0f} 天了，**可能已被接走** —— "
                    "第一句先问「这个还开放吗」，别直接报方案。")
    if not lead.get("deep") and lead.get("source") in DEEP_SUPPORTED:
        tips.append("这条**没读到正文**（只有标题）—— 发消息前先点开链接看一眼，"
                    "否则容易问出对方已经写明的问题。")
    tips.append("**问对问题本身就是能力证明**。这封信的目的不是成交，"
                "是让对方愿意回你第二句。")

    label = {"bounty": "悬赏/赏金", "hiring": "招聘", "inquiry": "询价",
             "outsourcing": "外包需求"}[kind]
    return {"kind": kind, "kind_label": label, "lang": lang,
            "message": body, "tips": tips}


# ---------------------------------------------------------------- 能力画像
# 为什么做这个：用户的核心困境是「我也不知道我能做什么」——
# 这是**自我认知**问题，工具无法替他回答。但工具能提供证据：
# 让他对线索做快速标注（能做 / 不能做 / 想做），累积起来就是一份
# **基于真实市场供给**的可服务范围画像，而不是自我感觉。
#
# 关键点：这不是心理测试，是市场快照 —— 标注的对象是"市场上真实存在的活"，
# 所以结论直接可用（"这类活我能接，而且每周有 N 条"）。
TECH_TAGS = [
    (re.compile(r"(爬虫|scraper|scraping|数据采集|抓取|采集)", re.I), "爬虫/数据采集"),
    (re.compile(r"(小程序|mini ?program|微信开发)", re.I), "小程序"),
    (re.compile(r"(插件|extension|userscript|油猴)", re.I), "浏览器插件"),
    (re.compile(r"(脚本|自动化|automat|script|定时|批量)", re.I), "脚本/自动化"),
    (re.compile(r"(接口|api|对接|集成|integrat|webhook)", re.I), "API 对接"),
    (re.compile(r"(数据处理|清洗|excel|报表|数据分析|可视化|dashboard)", re.I), "数据处理/报表"),
    (re.compile(r"(修复|bug|报错|error|fix|crash|corrupt|regression|调试)", re.I), "Bug 修复"),
    (re.compile(r"(训练|模型|推理|\bllm\b|agent|深度学习|分布式|\bgpu\b|"
                r"layernorm|rmsnorm|transformer)", re.I), "AI/模型工程"),
    (re.compile(r"(前端|react|vue|css|页面|ui ?kit|h5)", re.I), "前端"),
    (re.compile(r"(后端|服务端|数据库|架构|并发|性能|微服务)", re.I), "后端/架构"),
    (re.compile(r"(营销|运营|推广|marketing|\bseo\b|内容|文案|增长)", re.I), "营销/运营"),
    (re.compile(r"(设计|\bui\b|figma|视觉|海报|logo)", re.I), "设计"),
    (re.compile(r"(部署|运维|服务器|docker|k8s|kubernetes|nginx)", re.I), "部署/运维"),
    (re.compile(r"(客服|助理|assistant|排班|录入|整理|文员)", re.I), "非技术事务"),
]


def tech_tags(lead, limit=3):
    """给线索打技术类目标签 —— 这是能力画像的词汇表。

    **优先只看标题**（踩过的坑）：第一版对整个 text 匹配，而 text 是「标题 + 正文」，
    正文会东拉西扯 —— 实测一条「量化策略研究员」招聘同时命中 6 个标签
    （脚本/自动化、数据处理、Bug 修复、AI、后端、设计），画像统计因此完全没有区分度。
    标题才说明这份活「是什么」；标题给不出标签时才退回正文，并且限量。

    一条线索可以命中多个标签（「写个爬虫脚本」既是爬虫也是脚本），
    这样画像统计才有足够样本；但必须限量，否则每格都会被填满。
    """
    title = lead.get("title") or ""
    tags = [name for pat, name in TECH_TAGS if pat.search(title)]
    if not tags:
        body = lead.get("text") or ""
        tags = [name for pat, name in TECH_TAGS if pat.search(body)]
    return tags[:limit]


# 台账**故意不叫** leads_*.json（踩过的坑）：那个 glob 用来取"最新一轮产出"，
# 而 "leads_log.json" 在字符串排序里排在 "leads_20260920-1029.json" 之后，
# 于是"取最新产出"会读到台账本身，--mark 的序号全部错位（静默出错）。
LEDGER = os.path.join(OUT, "lead_marks.json")
MARKS = ("yes", "no", "maybe")          # 能做 / 不能做 / 想做
MARK_LABEL = {"yes": "能做", "no": "不能做", "maybe": "想做"}


def load_ledger():
    if not os.path.isfile(LEDGER):
        return {}
    try:
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ledger(d):
    os.makedirs(OUT, exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def mark_leads(leads, pairs):
    """按序号标注线索。pairs: [(1-based index, "yes"|"no"|"maybe")]。

    台账按 URL 存，所以跨轮次累积 —— 每次跑完标几条，几周后就有画像了。
    不要求一次标完：标得少也算数，画像里会如实写"样本 N 条"。
    """
    d = load_ledger()
    done, bad = 0, []
    for idx, mark in pairs:
        if mark not in MARKS:
            bad.append(f"{idx}:{mark}（标记只能是 {'/'.join(MARKS)}）")
            continue
        if not (1 <= idx <= len(leads)):
            bad.append(f"{idx}: 超出范围（本轮只有 {len(leads)} 条）")
            continue
        x = leads[idx - 1]
        d[x["url"]] = {"mark": mark, "title": x.get("title", ""),
                       "source": x.get("source", ""),
                       "tech": tech_tags(x),
                       "money": x.get("money", 0),
                       "ts": int(time.time())}
        done += 1
    save_ledger(d)
    return done, bad


def profile_md(leads=None, min_sample=5):
    """把标注累积成「可服务范围」画像。

    只报数据，不下结论 —— 结论由使用者自己下（这是他的自我认知，不是我的）。
    """
    d = load_ledger()
    if not d:
        return ["_台账是空的。先跑一次 `tools/leads.py`，再用 "
                "`--mark 3:yes --mark 7:no` 标注几条 —— 标得越多，画像越准。_"]
    by_mark = {m: [] for m in MARKS}
    for url, r in d.items():
        by_mark.setdefault(r.get("mark"), []).append(r)
    L = [f"# 可服务范围画像（基于 {len(d)} 条真实线索的标注）", "",
         "**这不是心理测试，是市场快照** —— 标注的对象是市场上真实存在的活，",
         "所以结论直接可用：哪类活你能接、而且市场上每周有多少条。", "",
         "> 标注是累积的（按 URL 存台账），跨轮次保留。样本少时结论会不稳，",
         "> 画像里会如实标出样本量，**别拿 5 条样本当结论**。", "", "---", ""]
    for m in MARKS:
        items = by_mark.get(m) or []
        if not items:
            continue
        cnt = {}
        for r in items:
            for t in (r.get("tech") or ["（未识别）"]):
                cnt[t] = cnt.get(t, 0) + 1
        top = sorted(cnt.items(), key=lambda kv: -kv[1])
        L += [f"## {MARK_LABEL[m]}　{len(items)} 条", "",
              "| 技术类目 | 条数 |", "|---|---:|"]
        for k, v in top:
            L.append(f"| {k} | {v} |")
        L.append("")
    yes = by_mark.get("yes") or []
    no = by_mark.get("no") or []
    maybe = by_mark.get("maybe") or []
    if yes or no:
        def counts(items):
            c = {}
            for r in items:
                for t in (r.get("tech") or ["（未识别）"]):
                    c[t] = c.get(t, 0) + 1
            return c

        cy, cn, cm = counts(yes), counts(no), counts(maybe)
        # 同一类目常在两边都出现（多标签），所以必须给**净差**，
        # 否则读者看到「能做里有脚本、不能做里也有脚本」只会觉得结论糊。
        cats = sorted(set(cy) | set(cn) | set(cm),
                      key=lambda k: -(cy.get(k, 0) - cn.get(k, 0)))
        L += ["---", "", "## 逐类目对比（同一类目两边都出现时，看净差）", "",
              "| 类目 | 能做 | 不能做 | 想做 | 净信号 |", "|---|---:|---:|---:|---|"]
        for k in cats:
            d = cy.get(k, 0) - cn.get(k, 0)
            sig = ("✅ 明显能做" if d >= 2 else
                   "↗ 偏能做" if d > 0 else
                   "❌ 明显不能做" if d <= -2 else
                   "↘ 偏不能做" if d < 0 else "— 打平")
            L.append(f"| {k} | {cy.get(k, 0)} | {cn.get(k, 0)} | {cm.get(k, 0)} | {sig} |")
        L += ["", "**净信号 = 能做 − 不能做**。净差为 0 的类目说明你自己也还没想清楚 ——"
                  "下次遇到这类线索多标几条，别急着下结论。", ""]
        if len(yes) < min_sample or len(no) < min_sample:
            L += [f"⚠ 样本量偏小（能做 {len(yes)} / 不能做 {len(no)}，建议各 ≥{min_sample} 条）。"
                  "**别拿现在的结论去改简历。**", ""]
        else:
            strong = [k for k in cats if cy.get(k, 0) - cn.get(k, 0) >= 2]
            weak = [k for k in cats if cy.get(k, 0) - cn.get(k, 0) <= -2]
            L += ["**可以据此做两件事**：", ""]
            if strong:
                L.append(f"1. 把「{'、'.join(strong)}」写进简历/自我介绍 —— "
                         "这是市场验证过的，不是自我感觉；")
            else:
                L.append("1. 还没有净差 ≥2 的类目 —— 再标几轮，别急着定位自己；")
            if weak:
                L.append(f"2. 「{'、'.join(weak)}」可以先用 `--use-profile` 降权，"
                         "省掉重复筛选（只是降权，不会让这类线索消失）；")
            else:
                L.append("2. 暂没有需要降权的类目。")
            L.append("")
    return L


def profile_weights():
    """从台账算出各类目的权重，供 --use-profile 调整排序。

    只做**加减分**，不做硬过滤 —— 硬过滤会形成信息茧房：
    你今天标"不能做"的类目，可能正是三个月后你该做的那一类。
    """
    d = load_ledger()
    w = {}
    for r in d.values():
        for t in (r.get("tech") or []):
            w.setdefault(t, {"yes": 0, "no": 0, "maybe": 0})
            m = r.get("mark")
            if m in w[t]:
                w[t][m] += 1
    out = {}
    for t, c in w.items():
        out[t] = c["yes"] * 0.6 + c["maybe"] * 0.3 - c["no"] * 0.6
    return out


# ---------------------------------------------------------------- HTML 交付
# 单文件、离线可开、零外部依赖 —— 与项目的看板同一定位。
# 为什么单独做：Markdown 适合归档与 diff，但这份东西的实际用法是
# **对着屏幕一条条读、点开链接、复制话术**。卡片式 + 筛选 + 复制按钮更顺手。
_HTML_CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f7f7f5;color:#2c2c2a;
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
 "Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;font-weight:500;margin:0 0 6px}
h2{font-size:17px;font-weight:500;margin:34px 0 12px;padding-bottom:8px;
 border-bottom:1px solid #e3e1da}
h3{font-size:15px;font-weight:500;margin:0 0 8px}
.sub{color:#5f5e5a;font-size:13px;margin-bottom:20px}
.hero{background:#eaf3de;border:1px solid #c0dd97;border-radius:12px;
 padding:16px 20px;margin:0 0 18px;display:flex;gap:26px;flex-wrap:wrap;align-items:baseline}
.hero .big{font-size:30px;font-weight:500;color:#27500a;line-height:1.1}
.hero .lbl{font-size:12px;color:#3b6d11}
.note{background:#fff;border:1px solid #e3e1da;border-radius:10px;
 padding:14px 18px;margin:0 0 16px;font-size:13.5px;color:#444441}
.note.warn{background:#faeeda;border-color:#fac775}
.note.gray{background:#f1efe8;border-color:#d3d1c7}
code{background:#f1efe8;padding:1px 5px;border-radius:4px;
 font:12.5px/1.5 ui-monospace,Menlo,Consolas,monospace}
pre{background:#2c2c2a;color:#f1efe8;padding:12px 14px;border-radius:8px;
 overflow-x:auto;font:12.5px/1.6 ui-monospace,Menlo,Consolas,monospace;
 white-space:pre-wrap;word-break:break-word;margin:0}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px;align-items:center}
.bar button{border:1px solid #d3d1c7;background:#fff;color:#444441;
 border-radius:20px;padding:5px 14px;font-size:13px;cursor:pointer}
.bar button.on{background:#2c2c2a;color:#fff;border-color:#2c2c2a}
.bar .sp{flex:1}
.card{background:#fff;border:1px solid #e3e1da;border-radius:12px;
 padding:16px 18px;margin:0 0 12px}
.card.worth{border-left:3px solid #639922}
.card.pend{border-left:3px solid #ef9f27}
.card.skip{border-left:3px solid #b4b2a9;opacity:.72}
.tag{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:20px;
 margin-right:6px;vertical-align:2px;white-space:nowrap}
.t-worth{background:#eaf3de;color:#27500a}
.t-pend{background:#faeeda;color:#633806}
.t-skip{background:#f1efe8;color:#5f5e5a}
.t-src{background:#e6f1fb;color:#0c447c}
.t-tech{background:#eeedfe;color:#3c3489}
.meta{color:#5f5e5a;font-size:12.5px;margin:8px 0 0}
.meta b{font-weight:500;color:#2c2c2a}
a{color:#185fa5;text-decoration:none;word-break:break-all}
a:hover{text-decoration:underline}
details{margin:10px 0 0}
summary{cursor:pointer;font-size:13px;color:#185fa5;user-select:none}
.cp{float:right;border:1px solid #d3d1c7;background:#fff;border-radius:6px;
 padding:3px 11px;font-size:12px;cursor:pointer;color:#444441}
.tips{margin:10px 0 0;padding-left:18px;font-size:13px;color:#444441}
.tips li{margin:4px 0}
table{width:100%;border-collapse:collapse;font-size:13px;background:#fff;
 border:1px solid #e3e1da;border-radius:10px;overflow:hidden}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #f1efe8}
th{background:#f7f7f5;font-weight:500;color:#5f5e5a;font-size:12.5px}
tr:last-child td{border-bottom:none}
td.n,th.n{text-align:right}
.net-pos{color:#3b6d11}.net-neg{color:#a32d2d}.net-flat{color:#888780}
.foot{color:#888780;font-size:12.5px;margin-top:34px;padding-top:16px;
 border-top:1px solid #e3e1da}
"""

_HTML_JS = """
function cp(id,btn){var t=document.getElementById(id).innerText;
 var done=function(){btn.textContent='已复制 ✓';setTimeout(function(){btn.textContent='复制话术';},1600);};
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(done,function(){fallback(t,done);});}
 else{fallback(t,done);}}
function fallback(t,cb){var a=document.createElement('textarea');a.value=t;
 a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();
 try{document.execCommand('copy');cb();}catch(e){alert('复制失败，请手动选择文本');}
 document.body.removeChild(a);}
function flt(v,btn){document.querySelectorAll('.bar button[data-v]').forEach(function(b){b.classList.remove('on');});
 btn.classList.add('on');
 document.querySelectorAll('.card').forEach(function(c){
   c.style.display=(v==='all'||c.dataset.v===v)?'':'none';});}
"""


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_html(leads, health, src_desc, kept_supply=0, kept_junk=0,
                n_deep=0, n_skip=0, n_scripts=3, n_prev=0, n_prev_pool=0,
                profile_lines=None):
    """产出单文件 HTML 交付（离线可开、零外部依赖）。"""
    import collections
    worth = [x for x in leads if x["verdict"] == "值得联系"]
    pend = [x for x in leads if x["verdict"] == "待看"]
    skip = [x for x in leads if x["verdict"] == "跳过"]
    dist = collections.Counter(x["source"] for x in leads)
    scripts = {x["url"]: apply_script(x) for x in worth[:n_scripts]}

    H = [_HTML_HEAD_TMPL.replace("__CSS__", _HTML_CSS).replace(
        "__TITLE__", "客户线索清单")]
    H.append('<div class="wrap">')
    H.append("<h1>客户线索清单</h1>")
    H.append(f'<div class="sub">生成于 {time.strftime("%Y-%m-%d %H:%M")}　·　'
             f'来源：{_esc(src_desc)}　·　'
             f'共 {len(leads)} 条线索</div>')

    H.append('<div class="hero">'
             f'<div><div class="big">{len(worth)}</div>'
             '<div class="lbl">值得联系</div></div>'
             f'<div><div class="big">{len(pend)}</div>'
             '<div class="lbl">待看</div></div>'
             f'<div><div class="big">{len(skip)}</div>'
             '<div class="lbl">跳过</div></div>'
             f'<div><div class="big">{len(dist)}</div>'
             '<div class="lbl">来源通道</div></div>'
             "</div>")

    H.append('<div class="note"><b>这是什么</b>：不是「值得做的方向」，'
             "是<b>现在能去联系的活</b>。每条线索保留个体身份"
             "（谁 / 要做什么 / 预算 / 原文 / 怎么联系），不做方向聚合。<br>"
             "判据：<b>钱</b>（按量级，不是看有没有）× 1.5 ＋ "
             "<b>需求具体度</b> × 1.0 ＋ <b>新鲜度</b> × 1.0。</div>")

    H.append('<div class="note gray"><b>怎么用起来</b>（这一步不做，它只是个清单）：'
             "读一遍下面的卡片 → 对每条标一个「能做 / 不能做 / 想做」→ 标够 5 条看画像。<br>"
             "<code>python tools/leads.py --mark 3:yes --mark 7:no</code>　"
             "<code>python tools/leads.py --profile</code>　"
             "<code>python tools/leads.py --use-profile</code><br>"
             "标注台账按 URL 累积、跨轮次保留 —— "
             "标的是市场上真实存在的活，所以结论直接可用，而不是自我感觉。</div>")

    if n_prev:
        H.append(f'<div class="note warn">其中 <b>{n_prev}</b> 条你已标注过，'
                 "已沉到榜尾。</div>")
    elif n_prev_pool:
        H.append(f'<div class="note warn">候选池里有 <b>{n_prev_pool}</b> 条你已标注过，'
                 f"但都没进前 {len(leads)} 名 —— 说明这轮新线索够多。</div>")

    # ---- 筛选栏 ----
    H.append('<div class="bar">'
             '<button data-v="all" class="on" onclick="flt(\'all\',this)">'
             f'全部 {len(leads)}</button>'
             f'<button data-v="值得联系" onclick="flt(\'值得联系\',this)">'
             f'值得联系 {len(worth)}</button>'
             f'<button data-v="待看" onclick="flt(\'待看\',this)">待看 {len(pend)}</button>'
             f'<button data-v="跳过" onclick="flt(\'跳过\',this)">跳过 {len(skip)}</button>'
             '<span class="sp"></span>'
             f'<span class="sub" style="margin:0">来源：'
             + "、".join(f"{_esc(k)} {v}" for k, v in dist.most_common())
             + "</span></div>")

    # ---- 线索卡片 ----
    H.append("<h2>线索</h2>")
    if not leads:
        H.append('<div class="note warn">本轮没有抽到线索。可能原因：'
                 "通道需要登录、查询词太窄、或该窗口没人在找人做事。</div>")
    for i, x in enumerate(leads, 1):
        v = x["verdict"]
        cls = "worth" if v == "值得联系" else ("pend" if v == "待看" else "skip")
        tcls = "t-worth" if v == "值得联系" else ("t-pend" if v == "待看" else "t-skip")
        H.append(f'<div class="card {cls}" data-v="{_esc(v)}">')
        H.append(f'<span class="tag {tcls}">{_esc(v)}</span>'
                 f'<span class="tag t-src">{_esc(x["source"])}</span>')
        for t in (x.get("tech") or []):
            H.append(f'<span class="tag t-tech">{_esc(t)}</span>')
        H.append(f'<h3 style="margin-top:10px">{i}. '
                 f'<a href="{_esc(x["url"])}" target="_blank" rel="noopener">'
                 f'{_esc(x["title"])}</a></h3>')
        age = "未知" if x["age_days"] is None else f"{x['age_days']:.1f} 天前"
        bits = [f"分 <b>{x['score']}</b>",
                f"钱 <b>{x['money']}</b>", f"具体 <b>{x['spec']}</b>",
                f"新鲜 <b>{x['fresh']}</b>", _esc(age)]
        if x.get("deep"):
            bits.append("✅ 已深读正文")
        if x.get("prev_mark"):
            bits.append("上次标注：<b>"
                        + {"yes": "能做", "no": "不能做",
                           "maybe": "想做"}.get(x["prev_mark"], "—") + "</b>")
        if x.get("profile_bonus"):
            bits.append(f"画像加成 {x['profile_bonus']:+.1f}")
        H.append('<div class="meta">' + "　·　".join(bits) + "</div>")
        if x.get("kind_note"):
            H.append(f'<div class="meta">{_esc(x["kind_note"])}</div>')
        s = scripts.get(x["url"])
        if s:
            sid = f"sc{i}"
            H.append('<details><summary>应征话术（'
                     + _esc(s["kind_label"]) + "）—— 点开复制</summary>")
            H.append(f'<button class="cp" onclick="cp(\'{sid}\',this)">复制话术</button>')
            H.append(f'<pre id="{sid}" style="margin-top:8px">{_esc(s["message"])}</pre>')
            H.append('<ul class="tips">')
            for t in s["tips"]:
                H.append("<li>" + _esc(t).replace("**", "") + "</li>")
            H.append("</ul></details>")
        H.append("</div>")

    # ---- 能力画像 ----
    if profile_lines:
        H.append("<h2>能力画像</h2>")
        H.append('<div class="note">这不是心理测试，是<b>市场快照</b> —— '
                 "标注的对象是市场上真实存在的活，所以结论直接可用。</div>")
        for ln in profile_lines:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if ln.startswith("|"):
                H.append(f'<div style="font-size:13px">{_esc(ln)}</div>')
            elif ln.startswith(">"):
                H.append(f'<div class="note gray">{_esc(ln.lstrip("> "))}</div>')
            else:
                H.append(f'<div style="font-size:13.5px;margin:6px 0">'
                         f'{_esc(ln.replace("**", ""))}</div>')

    # ---- 局限 ----
    H.append("<h2>已知局限（读榜单前必看）</h2>")
    lim = [f"<b>深读覆盖 {n_deep} 条</b>，另有 {n_skip} 条来源不支持深读。"
           "未深读的条目只有标题，建议点开链接自己看一眼 —— "
           "打分偏低不等于线索差。",
           "深读只支持 <b>V2EX</b>（/t/id）与 <b>知乎</b>（问题/回答）。"
           "知乎专栏文章（/p/id）没有对应命令，小红书笔记需登录，这两类只能靠标题判断。",
           "<b>金额不区分币种</b>，500 元与 $500 同等对待 —— 会低估人民币小额单。",
           "金额识别只看文本，写在图片里的预算抓不到。",
           f"本轮过滤：供给方 {kept_supply} 条（「我在接单」≠ 客户）、"
           f"无信息标题 {kept_junk} 条（如「[Bounty] Bounty」这类占位 issue）。",
           "供给方过滤是启发式的，中文表述千变万化，会有漏网。"]
    H.append('<ul class="tips">')
    for t in lim:
        H.append(f"<li>{t}</li>")
    H.append("</ul>")

    # ---- 通道健康 ----
    H.append("<h2>通道健康</h2>")
    H.append("<table><tr><th>通道</th><th class='n'>条数</th><th>状态</th>"
             "<th>备注</th></tr>")
    for h in health:
        st = "✅" if h.get("ok") else "❌"
        H.append(f'<tr><td>{_esc(h.get("source"))}</td>'
                 f'<td class="n">{h.get("count", 0)}</td><td>{st}</td>'
                 f'<td>{_esc(h.get("note", ""))}</td></tr>')
    H.append("</table>")

    H.append('<div class="foot">'
             "合规：抓的是公开页面，用途限定为<b>个人找活</b>；"
             "不要批量转发或做成对外产品。登录态类通道（小红书 / Upwork）"
             "可能违反站点自动化条款，有账号风险。<br>"
             "由 <code>tools/leads.py</code> 生成 · 单文件离线可开 · 零外部依赖"
             "</div>")
    H.append("</div>")
    H.append(f"<script>{_HTML_JS}</script>")
    H.append("</body></html>")
    return "\n".join(H)


_HTML_HEAD_TMPL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style></head><body>
"""


# ---------------------------------------------------------------- 离线模式
def from_cache(path=None):
    """从已有的采集缓存抽线索 —— 不联网、秒出。

    两级缓存（踩过的坑）：第一版只读 `window_cache_*.json`，那是
    **run_windows.py 的产出**，leads.py 自己从不保存 —— 于是全新用户照 README
    敲 `--from-cache` 会拿到 0 条，而且**退出码是 0**，分不清是工具坏了还是没数据。
    现在优先读 leads.py 自己存的 `leads_cache_*.json`，再退回 window_cache。
    """
    if not path:
        for pat in ("leads_cache_[0-9]*.json", "window_cache_[0-9]*.json"):
            c = sorted(glob.glob(os.path.join(OUT, pat)))
            if c:
                path = c[-1]
                break
        if not path:
            return [], [{"source": "cache", "count": 0, "ok": False,
                         "note": "找不到任何缓存 —— 先跑一次不带 --from-cache 的采集"}]
    with open(path, encoding="utf-8") as f:
        blob = json.load(f)
    # leads_cache：leads.py 自己存的**过滤后 leads**（首选）
    # —— 存 leads 而不是 raw，因为 raw 里没有 record_type，
    #    回读时会按 record_type 过滤成空（这是我第一版写错的地方）。
    if "leads" in blob:
        return list(blob["leads"]), [
            {"source": f"cache:{os.path.basename(path)}",
             "count": len(blob["leads"]), "ok": bool(blob["leads"]),
             "note": "离线：复用上一轮的过滤结果"}]
    # window_cache：run_windows.py 的产出，已经过 rule_filter
    out = []
    for k, w in (blob.get("windows") or {}).items():
        for r in w.get("kept", []):
            if r.get("record_type") in ("hiring", "bounty"):
                out.append(r)
    return out, [{"source": f"cache:{os.path.basename(path)}", "count": len(out),
                  "ok": len(out) > 0,
                  "note": "离线：复用已采集并过滤过的记录"}]


# ---------------------------------------------------------------- 输出
def md_text(s):
    """把文本放进 Markdown 链接/表格前的转义。

    实测踩过：标题常以 `[Bounty]` / `[Hiring]` 开头，直接塞进 `[标题](url)` 会变成
    `[[Bounty] [Bounty $1,500] ...](url)` —— 嵌套方括号让 Markdown 解析失败，链接点不动。
    同时把 `|` 换成 `/`，避免撑破表格。
    """
    return (s or "").replace("[", "\\[").replace("]", "\\]").replace("|", "/")


def render(leads, health, kept_supply, src_desc, kept_junk=0, n_deep=0, n_skip=0,
           n_scripts=3, n_prev=0, n_prev_pool=0):
    L = ["# 客户线索清单（正在出钱找人做事的人）", "",
         f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}　·　来源：{src_desc}", "",
         "**这是什么**：不是「值得做的方向」，是**现在能去联系的活**。",
         "每条线索保留个体身份（谁/要做什么/预算/原文/怎么联系），不做方向聚合。", "",
         "**三项判据**：① 钱（有具体金额 > 只有付费词）② 需求具体度（有动词+对象 > 泛泛求推荐）"
         "③ 新鲜度（≤3 天满分）。综合分 = 钱×1.5 + 具体×1.0 + 新鲜×1.0。", "",
         f"**供给方已过滤 {kept_supply} 条**（「我在接单」≠ 客户，方向相反）—— "
         "这条与 r/forhire 的 [Hiring] vs [For Hire] 是同一类错误，见 hunter/filter.py。", "",
         f"**无信息标题已过滤 {kept_junk} 条**（如「[Bounty] Bounty」这类占位/刷量 issue —— "
         "正文凑得出金额但标题没有信息）。", "",
         "**两道选样**：同源主体上限 2 条（防单仓库刷量）＋ 信源配额每源保底 3 条"
         "（防条数多的信源霸榜）。", "",
         f"**深读正文 {n_deep} 条**（标题粗排后对头部深读，正文里往往才写着预算与具体要求；"
         f"另有 {n_skip} 条来源不支持深读 —— 见文末局限）。", "",
         "**怎么用起来**（这一步不做，工具就只是个清单）：读一遍下表，"
         "对每条标一个「能做 / 不能做 / 想做」——", "",
         "```bash",
         "python tools/leads.py --mark 3:yes --mark 7:no --mark 11:maybe",
         "python tools/leads.py --profile          # 标够 5 条后看「可服务范围画像」",
         "python tools/leads.py --use-profile      # 让后续榜单按画像把你能接的排前面",
         "```", "",
         "> 标注台账按 URL 累积、跨轮次保留。**这是「我也不知道我能做什么」的解法** ——"
         "标的是市场上真实存在的活，所以结论直接可用，而不是自我感觉。", "",
         "---", ""]
    if not leads:
        L += ["_本轮没有抽到线索。可能原因：通道需要登录、查询词太窄、或该窗口没人在找人做事。_", ""]
    else:
        worth = [x for x in leads if x["verdict"] == "值得联系"]
        pend = [x for x in leads if x["verdict"] == "待看"]
        # 来源分布必须露出来：配额有没有生效，看这一行就知道。
        # （实测不加配额时，条数多的信源会把榜单占满，其他通道一条都进不来。）
        import collections
        dist = collections.Counter(x["source"] for x in leads)
        L += [f"**值得联系 {len(worth)} 条　待看 {len(pend)} 条　共 {len(leads)} 条**", "",
              "来源分布（已按信源配额选样，每源保底 3 条）："
              + "、".join(f"{k} {v}" for k, v in dist.most_common()), ""]
        # 已标计数要分清口径：「候选池里 9 条已标」≠「榜上 9 条已标」。
        # 实测踩过：我写成"其中 9 条你已标注过，已沉到榜尾"，但那些条目
        # 被挤出前 20、一条都没显示 —— 报数时没想清楚这个数的口径。
        if n_prev:
            L += [f"**其中 {n_prev} 条你已标注过，已沉到榜尾**（「上次」列是上次的标记）。", ""]
        elif n_prev_pool:
            L += [f"**候选池里有 {n_prev_pool} 条你已标注过，但都没进前 {len(leads)} 名**"
                  "—— 说明这轮新线索够多，标过的自然被挤出去了。", ""]
        L += ["> 用 `--new-only` 只看没标过的；已标的默认沉底但仍保留，"
              "方便你以后回看时找得到。", ""]
        L += ["| # | 判断 | 上次 | 分 | 来源 | 类目 | 深读 | 标题 | 钱 | 具体 | 新鲜 | 多久前 |",
              "|---:|---|---|---:|---|---|---|---|---:|---:|---:|---|"]
        for i, x in enumerate(leads, 1):
            age = "—" if x["age_days"] is None else f"{x['age_days']:.1f} 天"
            t = md_text(x["title"])[:56]
            tech = "、".join(x.get("tech") or []) or "—"
            bonus = x.get("profile_bonus")
            bs = f"（画像 {bonus:+.1f}）" if bonus else ""
            pm = x.get("prev_mark")
            pms = {"yes": "能", "no": "不能", "maybe": "想"}.get(pm, "—") if pm else "—"
            L.append(f"| {i} | {x['verdict']} | {pms} | {x['score']}{bs} | {x['source']} | "
                     f"{tech} | {'✅' if x.get('deep') else '—'} | [{t}]({x['url']}) | "
                     f"{x['money']} | {x['spec']} | {x['fresh']} | {age} |")
        L += ["", "---", "", "## 逐条原文（判断前请自己读一遍）", ""]
        for i, x in enumerate(leads[:30], 1):
            age = "—" if x["age_days"] is None else f"{x['age_days']:.1f} 天前"
            L += [f"**{i}. {x['verdict']}（{x['score']} 分）· {x['source']}**", "",
                  f"- 标题：{x['title']}",
                  f"- 链接：{x['url']}",
                  f"- 作者：{x['author'] or '—'}　发布：{age}",
                  f"- 原文：{x['text'][:400]}", ""]
    # 应征话术：线索表解决"有没有活"，但真正让人卡住的是"打开对话框不知道写什么"。
    # 对不擅长主动推销的人，这个门槛比找不到活更高。
    scripts = [x for x in leads if x["verdict"] == "值得联系"][:n_scripts]
    if scripts:
        L += ["", "---", "", "## 应征话术（可直接复制）", "",
              f"针对「值得联系」的前 {len(scripts)} 条生成，按线索类型分四套模板"
              "（悬赏 / 招聘 / 询价 / 外包）—— 语气和问题都不一样，用错类型一眼能看出是群发。", "",
              "> ⚠ **发之前请自己读一遍，改掉不符合实际的地方。** "
              "模板能省掉「不知道写什么」的门槛，但不能替你知道自己会什么。", ""]
        for i, x in enumerate(scripts, 1):
            s = apply_script(x)
            # 标题在这里是**纯文本标题**，不需要 md_text 的方括号转义
            # （转义只在链接文本里有必要，否则源文件里会多出一堆 \ 看着像出错）
            L += [f"### {i}. {(x['title'] or '')[:70]}　<span>{s['kind_label']}</span>", "",
                  f"线索链接：{x['url']}", "",
                  "```text", s["message"], "```", "",
                  "**发之前注意**：", ""]
            for t in s["tips"]:
                L.append(f"- {t}")
            L.append("")

    L += ["## 通道健康", "", "| 通道 | 条数 | 状态 | 备注 |", "|---|---:|---|---|"]
    for h in health:
        L.append(f"| {h['source']} | {h.get('count', 0)} | "
                 f"{'✅' if h.get('ok') else '❌'} | {h.get('note', '')} |")
    L += ["", "> **合规提醒**：这些通道抓的是公开页面，用途限定为**个人找活**；"
              "不要批量转发或做成对外产品。登录态类通道（小红书/Upwork）"
              "可能违反站点自动化条款，有账号风险 —— 见 out/resilience.json 的合规登记。", ""]
    # 局限必须写在产出里，不能只留在文档 —— 否则读者会把"打分低"读成"线索差"。
    L += ["## 已知局限（读榜单前必看）", "",
          "1. **国内通道的搜索结果只有标题，没有正文**。已用「深读」部分缓解："
          "**先按来源是否支持深读筛选，再取分数最高的若干条深读正文重打分**"
          "（表格「深读」列为 ✅ 的就是读过的）。"
          "**深读列是 — 的条目，建议点开链接自己看一眼。**", "",
          "2. **深读只支持两种来源**：V2EX（`/t/<id>`）与知乎（问题/回答）。"
          "**知乎专栏文章（`/p/<id>`）没有对应命令，小红书笔记需登录（实测 Navigation rejected）** ——"
          "这两类只能靠标题判断。", "",
          "3. **时间信息不一定拿得到**。「多久前」为空表示该通道没给发布时间，"
          "不是「很久以前」。深读返回体里带 `created_at` 时会自动补上。", "",
          "4. **金额识别只看文本**。写在图片里、或需要点进详情页才看到的预算抓不到。", "",
          "5. **供给方过滤是启发式的**。中文表述千变万化（「承接」「可接」「长期合作」…），"
          "会有漏网。看到明显是「我在接单」的条目，说明词表该补了。", "",
          "> **深读的真实价值**（实测）：一条标题看着像需求的知乎回答，正文是"
          "「简单点，淘宝直接搜脚本编辑」—— 不是需求，是建议。**只有读了正文才知道。**", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-cache", nargs="?", const="latest", default=None,
                    help="只从已有 window_cache 抽（离线、秒出）")
    ap.add_argument("--sources", default="zhihu,xhs,v2ex,project",
                    help="逗号分隔：zhihu,xhs,v2ex,project")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--deep-n", type=int, default=8,
                    help="对头部 N 条深读正文后重打分（每次一次浏览器调用，默认 8；"
                         "国内通道的搜索结果不含正文，只有深读才看得到预算与具体要求）")
    ap.add_argument("--no-deep", action="store_true", help="跳过深读")
    ap.add_argument("--scripts", type=int, default=3,
                    help="为前 N 条「值得联系」生成应征话术（默认 3，0 关闭）")
    ap.add_argument("--mark", action="append", default=[],
                    metavar="序号:yes|no|maybe",
                    help="标注线索（可重复）：--mark 3:yes --mark 7:no。"
                         "序号是上一次产出的行号；台账按 URL 累积，跨轮次保留")
    ap.add_argument("--profile", action="store_true",
                    help="只看能力画像（读台账，不采集）")
    ap.add_argument("--use-profile", action="store_true",
                    help="按台账里的标注调整排序（只加减分，不硬过滤）")
    ap.add_argument("--new-only", action="store_true",
                    help="只显示没标注过的线索（已标的沉底但仍保留，除非加这个开关）")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)

    # ---- 只读台账的两种模式：不采集、秒回 ----
    if a.profile:
        md = "\n".join(profile_md())
        p = os.path.join(OUT, "leads_profile.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(md)
        print(md)
        print(f"\n画像 -> {p}")
        return 0

    if a.mark:
        c = sorted(glob.glob(os.path.join(OUT, "leads_[0-9]*.json")))
        if not c:
            print("找不到 leads_*.json —— 先跑一次采集，再按产出行号标注")
            return 2
        with open(c[-1], encoding="utf-8") as f:
            blob = json.load(f)
        ls = blob.get("leads") or []
        pairs = []
        for spec in a.mark:
            k, _, v = str(spec).partition(":")
            try:
                pairs.append((int(k), v.strip().lower()))
            except ValueError:
                print(f"  ⚠ 无法解析 --mark {spec}（格式应为 序号:yes|no|maybe）")
        done, bad = mark_leads(ls, pairs)
        for b in bad:
            print(f"  ⚠ {b}")
        total = len(load_ledger())
        print(f"已标注 {done} 条　台账累计 {total} 条")
        if total < 5:
            print("  提示：标够 5 条以上再看画像更有意义 —— python tools/leads.py --profile")
        else:
            print("  看画像：python tools/leads.py --profile")
        return 0
    raw, health, desc = [], [], ""

    if a.from_cache is not None:
        raw, health = from_cache(None if a.from_cache == "latest" else a.from_cache)
        # 没有缓存时**必须报错退出**，不能返回空列表还假装成功。
        # 踩过的坑：全新用户照 README 敲 --from-cache 会拿到 0 条、退出码 0，
        # 分不清是工具坏了还是本来就没数据 —— 这种"静默空结果"最难排查。
        if not raw and any("找不到任何缓存" in (h.get("note") or "") for h in health):
            print("❌ 找不到任何采集缓存，--from-cache 无法工作。")
            print("   它复用上一轮的采集结果，所以需要先跑一次真实采集：")
            print("     python tools/leads.py --top 24        # 生成缓存")
            print("     python tools/leads.py --from-cache    # 之后就能秒出")
            return 2
        desc = "已有采集缓存（离线复用，含项目已有的供需过滤）"
    else:
        want = [s.strip() for s in a.sources.split(",") if s.strip()]
        for s in want:
            try:
                if s == "zhihu":
                    rs, h = collect_zhihu(a.limit)
                elif s in ("xhs", "xiaohongshu"):
                    rs, h = collect_xiaohongshu(a.limit)
                elif s == "v2ex":
                    rs, h = collect_v2ex(a.limit)
                elif s == "project":
                    rs, h = collect_project_channels()
                else:
                    continue
                raw += rs
                health += h
            except Exception as e:
                health.append({"source": s, "count": 0, "ok": False,
                               "note": f"{type(e).__name__}: {str(e)[:70]}"})
        desc = "＋".join(want)

    # 归一化 + 过滤
    leads, n_supply, n_junk, seen = [], 0, 0, set()
    for r in raw:
        key = (r.get("url") or "") or (r.get("title") or "")[:60]
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        src = r.get("source", "?")
        lead = to_lead(r, src)
        if lead["junk_title"]:
            n_junk += 1
            continue
        # 项目已有通道（bounty/forhire）在 hunter/filter.py 已做过供需过滤，不再二次判断
        pre_filtered = r.get("record_type") in ("hiring", "bounty")
        if lead["supply_side"] and not pre_filtered:
            n_supply += 1
            continue
        leads.append(lead)

    # 已标注过的线索：默认**仍然保留但排到最后**，并标出上次的标记；--new-only 则完全隐藏。
    # 为什么需要（这是我推荐的"每周跑一次、标 20 条"工作流的前提）：
    # 如果每次重跑都把标过的重新摆在最前面，就得反复重读同样的东西 ——
    # 那不是"省时间的工具"，是"每周浪费半小时的仪式"。
    ledger = load_ledger()
    for x in leads:
        prev = ledger.get(x["url"])
        if prev:
            x["prev_mark"] = prev.get("mark")
            x["already_marked"] = True
    n_prev_pool = sum(1 for x in leads if x.get("already_marked"))
    if a.new_only:
        leads = [x for x in leads if not x.get("already_marked")]

    # 能力画像调整：**只加减分，不做硬过滤**。
    # 硬过滤会形成信息茧房 —— 你今天标"不能做"的类目，可能正是三个月后该做的那一类。
    # 而且标错一条的代价只是排序偏一点，不会让整类线索消失。
    if a.use_profile:
        w = profile_weights()
        if w:
            for x in leads:
                bonus = sum(w.get(t, 0) for t in (x.get("tech") or []))
                x["profile_bonus"] = round(bonus, 1)
                x["score"] = round(x["score"] + bonus, 1)
            print(f"  已按能力画像调整排序（台账 {len(load_ledger())} 条标注）")
        else:
            print("  台账为空，--use-profile 无效果（先用 --mark 标几条）")

    leads = [x for x in leads if x["score"] >= a.min_score]
    # 未标过的排前面（同一批里先看新的），已标过的沉底但仍在榜上
    leads.sort(key=lambda x: (bool(x.get("already_marked")), -x["score"]))
    # 两道选样，缺一不可：
    #   cap_per_repo   —— 防同一个仓库连发刷量（实测 bounty-plaza 一个仓库 6+ 条）
    #   quota_select   —— 防条数多的信源霸榜（项目在 P0-3 学到的教训）
    leads = cap_per_repo(leads)
    leads = quota_select(leads, a.top)

    # 二段式：粗排定名单（便宜），深读定内容（贵）。
    # 顺序很重要 —— 配额先决定"谁有资格被看见"，深读再补上标题里没有的信息。
    # 国内线索尤其需要：搜索结果不含正文，不深读就永远是低分。
    # 最终榜单里的已标条数（与候选池里的分开统计：池里有 9 条不等于榜上有 9 条）
    n_prev = sum(1 for x in leads if x.get("already_marked"))
    n_deep = n_skip = 0
    if not a.no_deep and a.deep_n > 0:
        n_deep, n_skip = deep_read_top(leads, a.deep_n)
        # 重排时必须保留"已标沉底"这一层，否则前面的排序被覆盖
        leads.sort(key=lambda x: (bool(x.get("already_marked")), -x["score"]))
        print(f"  深读 {n_deep} 条正文后重打分（另有 {n_skip} 条来源不支持深读）")

    ts = time.strftime("%Y%m%d-%H%M%S")
    # 存一份"过滤后的 leads"作为**自己的**缓存 —— 这样 --from-cache 才自洽，
    # 不必依赖 run_windows.py 先跑过（那是个没写进文档的隐式依赖，实测让新用户困惑）。
    # 只存 leads 不存 raw：raw 里没有 record_type，回读时会过滤成空。
    # 从缓存跑出来的结果不再存（避免"缓存套缓存"）。
    if a.from_cache is None:
        cp = os.path.join(OUT, f"leads_cache_{ts}.json")
        with open(cp, "w", encoding="utf-8") as f:
            json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "leads": leads}, f, ensure_ascii=False, indent=1, default=str)
        print(f"缓存 -> {cp}")
    # HTML 是主交付：这份东西的实际用法是对着屏幕一条条读、点开链接、复制话术。
    # Markdown/JSON 保留作归档与机器消费。
    hp = os.path.join(OUT, f"leads_{ts}.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(render_html(leads, health, desc, kept_supply=n_supply, kept_junk=n_junk,
                            n_deep=n_deep, n_skip=n_skip, n_scripts=a.scripts,
                            n_prev=n_prev, n_prev_pool=n_prev_pool,
                            profile_lines=profile_md() if load_ledger() else None))
    mp = os.path.join(OUT, f"leads_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write(render(leads, health, n_supply, desc, kept_junk=n_junk,
                       n_deep=n_deep, n_skip=n_skip,
                       n_scripts=a.scripts, n_prev=n_prev,
                       n_prev_pool=n_prev_pool))
    jp = os.path.join(OUT, f"leads_{ts}.json")
    # 话术也落盘：方便被别的脚本消费（如批量导入到某个外联工具）
    worth = [y for y in leads if y["verdict"] == "值得联系"][:max(a.scripts, 0)]
    scripts = {x["url"]: apply_script(x) for x in worth}
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "sources": desc, "supply_filtered": n_supply,
                   "junk_filtered": n_junk,
                   "deep_read": n_deep, "deep_skipped": n_skip,
                   "already_marked": n_prev, "already_marked_pool": n_prev_pool,
                   "scripts": scripts,
                   "leads": leads, "health": health},
                  f, ensure_ascii=False, indent=1, default=str)

    n_worth = sum(1 for x in leads if x["verdict"] == "值得联系")
    print(f"线索 {len(leads)} 条（值得联系 {n_worth}）｜过滤供给方 {n_supply} 条 / 无信息标题 {n_junk} 条")
    for h in health:
        print(f"  {'OK ' if h.get('ok') else '!! '}{h['source']:<28} {h.get('count', 0):>4} 条  "
              f"{h.get('note', '')}")
    print(f"\nHTML -> {hp}\n清单 -> {mp}\nJSON -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
