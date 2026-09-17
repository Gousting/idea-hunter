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
