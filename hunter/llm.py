# -*- coding: utf-8 -*-
"""
L3 LLM 判断层。

关键设计（这层最容易做错）：
1. 每个维度打分必须附带 quote 原文片段，无 quote 的结论一律作废 —— 这是唯一能
   低成本约束模型幻觉的手段。宁可丢结果，不可要编造的结论。
2. 只让它做"读一段文本给出结构化判断"，不让它做"搜索/回忆/推理外部事实"。
   需要外部事实的部分（真实用户量、竞品是否已存在）必须由程序另外取证。
3. 输出严格 JSON schema，字段缺失即判无效并重试一次。
4. 未配置 API key 时自动降级为规则启发式，保证流水线永远能跑通。
"""
import json
import os
import re
import time
import urllib.request

API_KEY = (os.environ.get("DEEPSEEK_API_KEY")
           or os.environ.get("OPENAI_API_KEY") or "").strip()
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-flash")

SCHEMA = {
    "type": "object",
    "properties": {
        "is_real_pain": {"type": "boolean"},
        "pain_summary": {"type": "string"},
        "evidence_quotes": {"type": "array", "items": {"type": "string"}},
        "buyer_intent": {"type": "integer"},
        "wtp_signal": {"type": "integer"},
        "mvp_feasibility": {"type": "integer"},
        "competition": {"type": "integer"},
        "reusable_core": {"type": "boolean"},
        "target_user": {"type": "string"},
        "why_now": {"type": "string"},
        "kill_reason": {"type": "string"},
    },
    "required": ["is_real_pain", "pain_summary", "evidence_quotes", "buyer_intent",
                 "wtp_signal", "mvp_feasibility", "competition"],
}

SYSTEM = """你是独立开发者需求挖掘流水线里的"筛子"，不是创意机器。
你的唯一任务是：读一段来自社区或开源项目的原始文本，判断它是否构成一个
可被独立开发者用 2-4 周 MVP 解决、且有人愿意付钱的真实需求。

铁律：
1. evidence_quotes 必须是从原文中逐字截取的片段（英文原样，不得改写、不得翻译、
   不得拼接）。引用不出原文，就把 is_real_pain 判为 false。严禁凭常识补充内容。
2. 你不知道外部世界。不要假设某产品是否已存在、不要引用任何未在原文中出现的
   市场数据。不确定就降低 competition 的可信度，但不要编造。
3. 用户随口吐槽 ≠ 需求；只有表达了"想解决 / 想找工具 / 愿意付钱"才计分。

打分 0-5：
- buyer_intent：文本中是否有人明确在寻找解决方案（0=纯吐槽，5=正在找工具/招人做）
- wtp_signal：文本中的付费意愿强度（0=无，3=提到付费版/愿意买，5=已付费/明确报价）
- mvp_feasibility：反向量！5 = 独立开发者 2-4 周可做出 MVP；1 = 需要大团队
- competition：0=未见竞品迹象，5=已被成熟产品充分覆盖（注意：仅基于原文判断）

reusable_core：该开源项目能否作为内核复用、只在上层做封装（对应"不要从零重写底层"）。
kill_reason：若 is_real_pain=false 或明显不可做，用一句话说明理由；否则留空。"""


def _call(messages, retries=2):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {API_KEY}"})
    last = None
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode("utf-8"))
            return d["choices"][0]["message"]["content"]
        except Exception as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"LLM 调用失败: {last}")


def _validate(obj, raw_text):
    """反幻觉闸门：引用必须能在原文里找到，否则作废。"""
    qs = obj.get("evidence_quotes") or []
    norm = lambda s: re.sub(r"\s+", " ", (s or "")).lower()
    hay = norm(raw_text)
    good = [q for q in qs if len(q) >= 12 and norm(q)[:60] in hay]
    obj["evidence_quotes"] = good
    obj["_quotes_total"] = len(qs)
    obj["_quotes_verified"] = len(good)
    if not good:
        obj["is_real_pain"] = False
        obj["kill_reason"] = (obj.get("kill_reason") or "") + " [闸门] 无一条引用可在原文中定位，结论作废"
    return obj


def score(rec, dry_run=False):
    """对单条候选打分。返回 (score_obj, mode)"""
    text = (rec.get("text") or "")[:1800]
    ctx = (f"来源：{rec['source']}\n标题：{rec.get('title','')}\n"
           f"链接：{rec.get('url','')}\n"
           f"仓库指标：stars={rec.get('stars_total')} forks={rec.get('forks')} "
           f"license={rec.get('license')} 风险标记={rec.get('risk_flags')}\n"
           f"--- 原文 ---\n{text}")
    if dry_run or not API_KEY:
        return _heuristic(rec), "heuristic(未配置APIKey)"

    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": ctx}]
    try:
        out = _call(msgs)
        obj = json.loads(out)
    except Exception as e:
        return {"is_real_pain": False, "pain_summary": "", "evidence_quotes": [],
                "buyer_intent": 0, "wtp_signal": 0, "mvp_feasibility": 0,
                "competition": 0, "kill_reason": f"解析失败 {e}",
                "_mode": "llm-error"}, "llm-error"
    obj = _validate(obj, text)
    obj["_mode"] = "llm"
    obj["total"] = _total(obj, rec)
    return obj, "llm"


def _total(obj, rec):
    """加权总分。权重是主观的，但必须写死成常量而不是让模型自由发挥，
    否则同一堆数据会随模型心情给出不同排序。"""
    if not obj.get("is_real_pain"):
        return 0.0
    s = (obj.get("buyer_intent", 0) * 0.30
         + obj.get("wtp_signal", 0) * 0.30
         + obj.get("mvp_feasibility", 0) * 0.25
         + (5 - min(obj.get("competition", 0), 5)) * 0.15)
    if obj.get("reusable_core"):
        s += 0.3
    s -= 0.5 * len(rec.get("risk_flags") or [])
    return round(max(s, 0.0), 2)


def _heuristic(rec):
    """无 key 降级：只用可复现的规则，绝不假装是 AI 判断。"""
    from .filter import pain_hits, wtp_hits, strong_wtp_hits
    t = rec.get("text") or ""
    pain = rec.get("pain_hits") if rec.get("pain_hits") is not None else pain_hits(t)
    wtp = rec.get("strong_wtp_hits") if rec.get("strong_wtp_hits") is not None else strong_wtp_hits(t)
    extra = rec.get("signal_hits") or []
    obj = {
        "is_real_pain": bool(pain or wtp),
        "pain_summary": " ".join(t.split())[:140],
        "evidence_quotes": [q for q in (wtp or pain or extra)[:3]],
        "buyer_intent": min(len(pain) + len(extra) // 2, 5),
        "wtp_signal": min(len(wtp) * 2, 5),
        "mvp_feasibility": 4 if rec["source"] == "github_issue" else 3,
        "competition": 0,
        "reusable_core": rec["source"] == "github_issue",
        "kill_reason": "" if (pain or wtp or extra) else "未命中需求信号",
    }
    obj["total"] = _total(obj, rec)
    return obj


# ---------------------------------------------------------------- 语义方向分类
# 为什么需要它：关键词签名有两个结构性偏差——
#   ① 28 个方向的签名宽度不等，「AI 代理」的签名最宽，导致它的证据数天然偏高，
#      用户正确地质疑了这一点（"AI 热度是真高还是你的搜索方式造成的"）；
#   ② 付费构式靠词面匹配，抓不住 "our team would pay for that ability" 之外的
#      大量口语化付费表达。
# LLM 分类一次解决两个问题：语义等距（不依赖签名宽度）+ 口语化付费信号。
# 设计要点：批量打包容（省 token）；方向名必须在给定列表内，否则判 None（防幻觉新方向）；
# 失败的批次回退到关键词签名，绝不因为 LLM 挂了让整条流水线死掉。

CLASSIFY_SYSTEM = """你是需求挖掘流水线里的分类器。给你若干条来自不同平台的原始记录
（GitHub 仓库简介 / HN 讨论 / Reddit 帖子 / Product Hunt 等），为每条判断：

1. direction：它最接近哪个「产品方向」。只能从给定列表里选，单选；
   如果都不沾边，填 "无"。
2. wtp：文本中是否存在付费意愿信号（有人愿意掏钱/正在掏钱/明确报价），0-5。
   注意口语化表达也算："would pay for that"、"shut up and take my money"、
   "我愿意为它付钱"、"有人靠这个赚钱吗" 等。
3. pain：文中是否表达了真实痛点（不是转述新闻），0-5。

铁律：只依据给出的文本判断，不要联想外部世界。返回严格 JSON。"""

_CLASSIFY_CACHE = None


def _direction_names():
    global _CLASSIFY_CACHE
    if _CLASSIFY_CACHE is None:
        from .directions import DIRECTIONS
        _CLASSIFY_CACHE = [d[0] for d in DIRECTIONS]
    return _CLASSIFY_CACHE


def classify_batch(records, batch_size=8, max_batches=None):
    """LLM 语义方向分类。返回 (处理条数, 模式说明)。

    成功时给每条记录写入：direction（方向名或 None）、llm_wtp、llm_pain。
    未配置 key 或全部失败时返回 (0, 原因)，调用方回退到关键词签名。
    """
    if not API_KEY:
        return 0, "未配置 APIKey，回退关键词签名"
    names = _direction_names()
    todo = [r for r in records if not r.get("direction")]
    done = 0
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    if max_batches:
        batches = batches[:max_batches]
    fails = 0
    for bi, batch in enumerate(batches):
        listing = "\n".join(
            f"[{i}] 来源:{r.get('source','')} 标题:{(r.get('title') or '')[:100]}\n"
            f"    正文:{((r.get('topic_text') or r.get('text') or ''))[:700]}"
            for i, r in enumerate(batch))
        user = (f"方向列表（只能选这些或'无'）：\n{json.dumps(names, ensure_ascii=False)}\n\n"
                f"记录：\n{listing}\n\n"
                f'返回 JSON：{{"items":[{{"i":0,"direction":"方向名","wtp":0,"pain":0}}]}}')
        try:
            out = _call([{"role": "system", "content": CLASSIFY_SYSTEM},
                         {"role": "user", "content": user}])
            obj = json.loads(out)
            items = obj.get("items") or []
        except Exception:
            fails += 1
            continue
        for it in items:
            try:
                i = int(it.get("i"))
                r = batch[i]
            except Exception:
                continue
            d = str(it.get("direction") or "").strip()
            r["direction"] = d if d in names else None
            clamp = lambda v: max(0, min(int(v or 0), 5))
            r["llm_wtp"] = clamp(it.get("wtp"))
            r["llm_pain"] = clamp(it.get("pain"))
            done += 1
    if fails and not done:
        return 0, f"LLM 分类全部失败（{fails} 批），回退关键词签名"
    mode = "llm-语义分类"
    if fails:
        mode += f"（{fails} 批失败已回退）"
    return done, mode
