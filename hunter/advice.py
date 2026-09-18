# -*- coding: utf-8 -*-
"""建议与趋势引擎：把方向统计翻译成"该不该看、会不会爆"。

为什么要单独一层：前面的输出只有热度/拥挤度/付费信号这些**指标**，
用户要的是**判断**。指标到判断之间的映射必须显式写下来，理由：

1. 判断必须可解释、可复核 —— 每条建议都带 reasons，用户能顺着理由回去看数据，
   而不是接受一句"值得做"。规则写死成常数，同一份数据永远给同一个结论。
2. 判断要区分"现在要不要动手"和"未来会不会变大"，这是两件事：
   - verdict（建议结论）看的是**当下值不值得投入**：热度 × 拥挤度 × 付费信号
   - trend（爆发趋势）看的是**变化速率**：涨星速度 × 平台共振 × 窗口加速 × 首次出现付费信号
   一个方向可能"当下不值得进但正在加速"（早期信号），也可能"很热但已经停滞"。
3. 宁可说"信号不足"也不硬编结论 —— 单条证据支撑不了判断，这一档必须存在。

趋势评分口径（可复算）：
  涨星速度  vmax≥200→+3 / ≥80→+2 / ≥30→+1
  平台共振  diversity≥3→+2 / ==2→+1
  窗口加速  今日/本周≥0.5→+2；本周/本月≥0.4→+1
  付费信号  wtp_total>0→+1
  新近出现  仅今日窗口有→+1
  ≥5 高 / 3-4 中 / ≤2 低
"""


def _vmax(row):
    """本方向相关仓库里的最高日均涨星（取不到就退回汇总 velocity 的日均近似）。"""
    vs = [r.get("star_velocity") or 0 for r in row.get("repos", [])]
    m = max(vs) if vs else 0
    if not m and row.get("velocity"):
        m = min(row["velocity"] / 30.0, 999)  # velocity 是窗口内合计，按 30 天粗除
    return m


def trend_of(name, rows_by_window):
    """爆发趋势评级 + 分数 + 理由。rows_by_window: {label: [rows]}"""
    ev = {}
    row_any = None
    for label, rows in rows_by_window.items():
        for r in rows:
            if r["name"] == name:
                ev[label] = r.get("evidence", 0)
                row_any = row_any or r
    if row_any is None:
        return None
    score, reasons = 0, []
    v = _vmax(row_any)
    if v >= 200:
        score += 3
        reasons.append(f"头部仓库日均涨星 {v:.0f}（极快）")
    elif v >= 80:
        score += 2
        reasons.append(f"头部仓库日均涨星 {v:.0f}（较快）")
    elif v >= 30:
        score += 1
        reasons.append(f"头部仓库日均涨星 {v:.0f}")

    div = len(row_any.get("sources", []))
    if div >= 3:
        score += 2
        reasons.append(f"{div} 个平台独立出现（共振）")
    elif div == 2:
        score += 1
        reasons.append("2 个平台出现")

    d, w, m = ev.get("今日", 0), ev.get("本周", 0), ev.get("本月", 0)
    # 注意：三个窗口是**独立采集**的（不是包含关系），所以 d 可能大于 w。
    # 表述必须区分"当下密集"和"正在加速"，写成"今日占本周 2/1"会误导。
    if d and w:
        if d >= w:
            score += 2
            reasons.append(f"今日 {d} 条 ≥ 本周 {w} 条（当下密集）")
        elif d / w >= 0.5:
            score += 2
            reasons.append(f"今日 {d} 条 / 本周 {w} 条（正在加速）")
    elif m and w and w / m >= 0.4:
        score += 1
        reasons.append(f"本周 {w} / 本月 {m}（升温）")

    if row_any.get("wtp_total", row_any.get("wtp", 0)) > 0:
        score += 1
        reasons.append("出现付费信号")
    # 招聘证据的 +1 保留在分数里，但理由不在这里重复写——建议侧已说明，
    # 两处都写会同一条理由出现两次（实测渲染出来很啰嗦）。
    if row_any.get("hiring"):
        score += 1

    if d and not m:
        score += 1
        reasons.append("仅近期窗口出现（新近冒头）")

    level = "高" if score >= 5 else ("中" if score >= 3 else "低")
    return {"level": level, "score": score, "reasons": reasons}


def verdict_of(row):
    """当下值不值得投入的建议结论。返回 (结论, 等级, 理由[], 建议动作)。"""
    ev = row.get("evidence", 0)
    market = row.get("market_repos")
    crowd = row.get("crowd", "—")
    wtp = row.get("wtp_total", row.get("wtp", 0))
    hiring = row.get("hiring", 0)
    div = len(row.get("sources", []))

    if ev >= 3 and market is not None and market >= 1000:
        return ("已拥挤，不建议正面进入", 1,
                [f"{ev} 条证据显示需求真实",
                 f"但 GitHub 存量 {market} 个（红海）"],
                "除非有明确差异化切口（细分人群 / 现有产品的具体差评），否则跳过")
    if ev >= 3 and market is not None and market >= 300:
        return ("需求真实但供给密集，需差异化", 2,
                [f"{ev} 条证据 · {div} 个平台",
                 f"存量 {market} 个，已有多家在解"],
                "先扒 3-5 个现有产品的差评与退款理由，找未被满足的细分场景")
    if ev >= 3 and market is not None and market < 300 and (wtp > 0 or hiring > 0):
        pay = "已出现付费信号" if wtp > 0 else f"{hiring} 条招聘证据（企业已在为这类活付钱）"
        return ("★ 建议优先验证", 4,
                [f"{ev} 条证据 · {div} 个平台",
                 f"存量仅 {market} 个（稀疏）",
                 pay],
                "本周人工核验 2-3 条原帖 + 抓 5 个同类招聘帖看具体要求，判断能否做成产品")
    if ev >= 3 and market is not None and market < 300:
        return ("★ 值得看，但需补付费证据", 3,
                [f"{ev} 条证据 · {div} 个平台",
                 f"存量仅 {market} 个，供给少"],
                "先验证有没有人愿意为此掏钱（找原帖作者 / 招聘帖 / 付费竞品）")
    if ev == 2:
        return ("待观察，证据偏弱", 2,
                [f"{div} 个平台各 1 条，尚未形成共振"],
                "记进观察名单，看下个窗口能否复现")
    return ("信号不足，暂不判断", 0,
            ["单条证据支撑不了结论"],
            "不下结论；若趋势评级高可提前留意")


def annotate(rows_by_window):
    """给每个窗口的 rows 挂上建议与趋势，返回 {方向名: advice}。"""
    out = {}
    labels = list(rows_by_window.keys())
    for label in labels:
        for row in rows_by_window[label]:
            name = row["name"]
            t = out.get(name, {}).get("trend") or trend_of(name, rows_by_window)
            v = out.get(name, {}).get("verdict") or verdict_of(row)
            out[name] = {"trend": t, "verdict": v}
        # 把建议挂到该窗口的 row 上，供渲染直接取用
        for row in rows_by_window[label]:
            a = out[row["name"]]
            row["advice"] = a["verdict"][0]
            row["advice_level"] = a["verdict"][1]
            row["advice_reasons"] = a["verdict"][2]
            row["advice_action"] = a["verdict"][3]
            row["trend_level"] = a["trend"]["level"]
            row["trend_score"] = a["trend"]["score"]
            row["trend_reasons"] = a["trend"]["reasons"]
    return out
