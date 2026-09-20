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
# 金额附近出现这些词，即使没写货币符/单位也认定是钱（"价格 500"、"预算 3000"）
_MONEY_WORD_NEAR = re.compile(
    r"(预算|价格|报价|报酬|酬劳|酬金|费用|薪酬|日结|周结|时薪|工资|"
    r"\bbudget\b|\brate\b|\bprice\b|\bpay\b|\bhourly\b|\bper hour\b|\bfee\b)", re.I)


def has_plausible_amount(text):
    """文本里有没有「像价格」的金额。排除两类噪音：
    ① 超长数字串（issue id / 哈希 / 日期，如 $239398281948585883）
    ② 量级离谱的值。
    认定条件：有货币符、有单位、或附近有"预算/价格/rate"这类词三者之一。
    下界取 10 是为了放过 $20/h 这类时薪；上界 500 万覆盖真实外包预算。
    """
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
        if cur or unit:
            return True
        ctx = (text or "")[max(0, m.start() - 12): m.end() + 12]
        if _MONEY_WORD_NEAR.search(ctx):
            return True
    return False


def _money_score(text):
    """0-3：3=有合理量级的具体金额，2=多个付费词，1=单个付费词，0=没有"""
    if has_plausible_amount(text):
        return 3
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
        "supply_side": is_supply_side(txt, title),
        "junk_title": not title_quality(title),
    }
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


# ---------------------------------------------------------------- 离线模式
def from_cache(path=None):
    """从已有的 window_cache_*.json 抽线索 —— 不联网、秒出。

    这些记录已经被 rule_filter 过了一遍（含 forhire 供需过滤），
    所以是现成的高质量线索池。
    """
    if not path:
        c = sorted(glob.glob(os.path.join(OUT, "window_cache_*.json")))
        if not c:
            return [], []
        path = c[-1]
    with open(path, encoding="utf-8") as f:
        blob = json.load(f)
    out = []
    for k, w in (blob.get("windows") or {}).items():
        for r in w.get("kept", []):
            if r.get("record_type") in ("hiring", "bounty"):
                out.append(r)
    return out, [{"source": f"cache:{os.path.basename(path)}", "count": len(out),
                  "ok": len(out) > 0, "note": "离线：复用已采集并过滤过的记录"}]


# ---------------------------------------------------------------- 输出
def md_text(s):
    """把文本放进 Markdown 链接/表格前的转义。

    实测踩过：标题常以 `[Bounty]` / `[Hiring]` 开头，直接塞进 `[标题](url)` 会变成
    `[[Bounty] [Bounty $1,500] ...](url)` —— 嵌套方括号让 Markdown 解析失败，链接点不动。
    同时把 `|` 换成 `/`，避免撑破表格。
    """
    return (s or "").replace("[", "\\[").replace("]", "\\]").replace("|", "/")


def render(leads, health, kept_supply, src_desc, kept_junk=0, n_deep=0, n_skip=0):
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
        L += ["| # | 判断 | 分 | 来源 | 深读 | 标题 | 钱 | 具体 | 新鲜 | 多久前 |",
              "|---:|---|---:|---|---|---|---:|---:|---:|---|"]
        for i, x in enumerate(leads, 1):
            age = "—" if x["age_days"] is None else f"{x['age_days']:.1f} 天"
            t = md_text(x["title"])[:60]
            L.append(f"| {i} | {x['verdict']} | {x['score']} | {x['source']} | "
                     f"{'✅' if x.get('deep') else '—'} | [{t}]({x['url']}) | "
                     f"{x['money']} | {x['spec']} | {x['fresh']} | {age} |")
        L += ["", "---", "", "## 逐条原文（判断前请自己读一遍）", ""]
        for i, x in enumerate(leads[:30], 1):
            age = "—" if x["age_days"] is None else f"{x['age_days']:.1f} 天前"
            L += [f"**{i}. {x['verdict']}（{x['score']} 分）· {x['source']}**", "",
                  f"- 标题：{x['title']}",
                  f"- 链接：{x['url']}",
                  f"- 作者：{x['author'] or '—'}　发布：{age}",
                  f"- 原文：{x['text'][:400]}", ""]
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
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    raw, health, desc = [], [], ""

    if a.from_cache is not None:
        raw, health = from_cache(None if a.from_cache == "latest" else a.from_cache)
        desc = "已有 window_cache（离线复用，含项目已有的供需过滤）"
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

    leads = [x for x in leads if x["score"] >= a.min_score]
    leads.sort(key=lambda x: -x["score"])
    # 两道选样，缺一不可：
    #   cap_per_repo   —— 防同一个仓库连发刷量（实测 bounty-plaza 一个仓库 6+ 条）
    #   quota_select   —— 防条数多的信源霸榜（项目在 P0-3 学到的教训）
    leads = cap_per_repo(leads)
    leads = quota_select(leads, a.top)

    # 二段式：粗排定名单（便宜），深读定内容（贵）。
    # 顺序很重要 —— 配额先决定"谁有资格被看见"，深读再补上标题里没有的信息。
    # 国内线索尤其需要：搜索结果不含正文，不深读就永远是低分。
    n_deep = n_skip = 0
    if not a.no_deep and a.deep_n > 0:
        n_deep, n_skip = deep_read_top(leads, a.deep_n)
        leads.sort(key=lambda x: -x["score"])
        print(f"  深读 {n_deep} 条正文后重打分（另有 {n_skip} 条来源不支持深读）")

    ts = time.strftime("%Y%m%d-%H%M")
    mp = os.path.join(OUT, f"leads_{ts}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write(render(leads, health, n_supply, desc, kept_junk=n_junk,
                       n_deep=n_deep, n_skip=n_skip))
    jp = os.path.join(OUT, f"leads_{ts}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "sources": desc, "supply_filtered": n_supply,
                   "junk_filtered": n_junk,
                   "deep_read": n_deep, "deep_skipped": n_skip,
                   "leads": leads, "health": health},
                  f, ensure_ascii=False, indent=1, default=str)

    n_worth = sum(1 for x in leads if x["verdict"] == "值得联系")
    print(f"线索 {len(leads)} 条（值得联系 {n_worth}）｜过滤供给方 {n_supply} 条 / 无信息标题 {n_junk} 条")
    for h in health:
        print(f"  {'OK ' if h.get('ok') else '!! '}{h['source']:<28} {h.get('count', 0):>4} 条  "
              f"{h.get('note', '')}")
    print(f"\n清单 -> {mp}\nJSON -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
