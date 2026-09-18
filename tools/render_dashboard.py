#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 directions_*.json 渲染成可交互的可视化看板（单文件 HTML）。

为什么不用截图/静态图：看板要能悬停看数值、点图例过滤、切窗口对比，
ECharts 单文件 + 内联数据最合适；不用任何构建工具，Python 直接吐 HTML。

用法：
  python tools/render_dashboard.py                 # 取最新一份 directions_*.json
  python tools/render_dashboard.py --json <path>   # 指定报告

图表选择（对着"用户要回答的问题"设计，不为炫技）：
  1. 机会象限散点   —— "哪些方向热但拥挤、哪些稀疏但没人做"（x=热度 y=拥挤 log）
  2. 机会分条形     —— "综合排序到底谁先谁后"（含拥挤度着色，红海一眼可见）
  3. 平台支撑热力图 —— "这个方向是单平台噪音还是多平台共振"
  4. 平台占比环形   —— "本窗口的数据都是谁贡献的"（平台偏差提醒）
"""
import glob
import html
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

PLATFORM_SHORT = {
    "github_trending": "GT·Trending", "github_search": "GS·Search",
    "github_issue": "GI·Issues", "hn": "HN", "reddit": "Reddit",
    "producthunt": "ProductHunt", "upwork": "Upwork", "browser": "浏览器",
    "stackoverflow": "StackOverflow", "lobsters": "Lobsters", "devto": "DEV.to",
    "lesswrong": "LessWrong", "indeed": "Indeed", "twitter": "X/Twitter",
    "zhihu": "知乎", "xiaohongshu": "小红书",
    "juejin": "掘金", "bluesky": "Bluesky",
}
CROWD_COLOR = {"红海": "#d9534f", "拥挤": "#f0ad4e",
               "中等": "#4da3d9", "稀疏": "#5cb85c"}


def latest(pattern):
    c = sorted(glob.glob(os.path.join(OUT, pattern)))
    return c[-1] if c else None


def load_analysis():
    """热榜付费潜力分析（agent 判断层）。没有就返回 None。"""
    p = os.path.join(OUT, "platform_analysis_dashboard.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_resilience():
    """源健康与依赖对冲数据（P0-3）。没有就返回 None。"""
    p = os.path.join(OUT, "resilience.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_validation():
    """验证闭环数据（P0-2）：验证包 + 北极星 + 待验证队列。"""
    p = os.path.join(OUT, "validation_kits.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_platforms():
    """平台优先轨道的 JSON（run_platforms.py 产出）。没有就返回 None。"""
    p = latest("platforms_*.json")
    if not p:
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_annotations():
    p = os.path.join(OUT, "agent_annotations.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build(json_path, cache_path, ann):
    with open(json_path, encoding="utf-8") as f:
        rep = json.load(f)
    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)
    sys.path.insert(0, ROOT)
    from hunter import directions as dr
    from hunter import paths as ph

    data = {"generated_at": rep.get("generated_at", ""),
            "windows": [], "health": rep.get("health", [])}
    for key, win in rep["windows"].items():
        kept = cache.get("windows", {}).get(key, {}).get("kept", [])
        # 与报告一致：应用 agent 标注 → 逐方向统计各平台条数
        plat_matrix = {}
        plat_total = {}
        n_ann_hit = 0
        for r in kept:
            a = ann.get((r.get("source_id") or "")[:44])
            if a:
                n_ann_hit += 1
                name = a[0] if a[0] != "无" else None
            else:
                name = None
            name = name or dr.classify_best(r)[0]
            if not name:
                continue
            src = r.get("source", "?")
            plat_matrix.setdefault(name, {})
            plat_matrix[name][src] = plat_matrix[name].get(src, 0) + 1
            plat_total[src] = plat_total.get(src, 0) + 1
        dirs = []
        for s in win["directions"]:
            dirs.append({
                "name": s["name"], "evidence": s.get("evidence", 0),
                "score": s.get("score", 0), "opp_score": s.get("opp_score"),
                "market": s.get("market_repos"), "crowd": s.get("crowd", "—"),
                "opp_tag": s.get("opp_tag", "—"),
                "wtp": s.get("wtp_total", s.get("wtp", 0)),
                "heat": s.get("heat", 0),
                "mature_products": s.get("mature_products"),
                "pain": s.get("pain", 0),
                "sources": s.get("sources", []),
                "hot": s.get("hot", 0),
                "resonance": s.get("resonance", 0),
                "native_sources": s.get("native_sources", []),
                "keyword_sources": s.get("keyword_sources", []),
                "plat": plat_matrix.get(s["name"], {}),
                "mature": s.get("mature", []),
                "evidence_links": s.get("evidence_links", []),
                "advice": s.get("advice", ""),
                "advice_level": s.get("advice_level", 0),
                "advice_action": s.get("advice_action", ""),
                "advice_reasons": s.get("advice_reasons", []),
                "trend_level": s.get("trend_level", ""),
                "trend_score": s.get("trend_score", 0),
                "trend_reasons": s.get("trend_reasons", []),
            })
        # 贡献率直接从缓存算，不依赖上游 JSON 是否导出该字段
        n_nat, n_kw, rate = ph.counts(kept)
        data["windows"].append({"key": key, "label": win["label"],
                                "path_stats": [n_nat, n_kw, rate],
                                "raw": win.get("raw", 0), "kept": win.get("kept", 0),
                                "dirs": dirs, "plat_total": plat_total,
                                "ann_hits": n_ann_hit, "kept_n": len(kept)})
    return data


# 模板从独立文件读（不再内嵌进 Python 字符串），两个好处：
# ① JS 里的正则反斜杠不用再写两层转义——此前 `\*\*` 触发过 SyntaxWarning，
#    还把正则写坏过一次（改成 Python 字符串里的裸 replace，静默失效）；
# ② 模板可以直接被独立工具检查（node --check 抽出的脚本、HTML 校验）。
TPL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "dashboard_template.html")


def load_template():
    with open(TPL_PATH, encoding="utf-8") as f:
        return f.read()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    jp = a.json or latest("directions_*.json")
    cp = latest("window_cache_*.json")
    if not jp or not cp:
        print("找不到 directions/window_cache 文件");  return 2
    ann = load_annotations()
    # 判定方式与"是否应用标注"必须描述**同一次运行**，不能各自猜。
    # directions_*.json 的 classify 字段由 run_windows.py 写入（唯一事实来源）。
    # 老 JSON 没有该字段时才退回旧行为（有标注文件就当用了）—— 但那种情况下
    # 看板会与报告不一致，所以宁可把这段退路写窄、并优先信任落盘的记录。
    try:
        with open(jp, encoding="utf-8") as f:
            rep_meta = json.load(f).get("classify") or {}
    except Exception:
        rep_meta = {}
    if rep_meta.get("ann_used") is None:
        ann_used = bool(ann)
        ann_eff = ann
    else:
        ann_used = bool(rep_meta["ann_used"])
        ann_eff = ann if ann_used else {}      # 那次运行没用标注，看板也不该用
    data = build(jp, cp, ann_eff)
    from hunter import mode as md
    if rep_meta.get("mode"):
        # 直接复用报告记录的判定方式：看板是"渲染这次运行"，不是"重新决定"
        data["mode"] = rep_meta["mode"]
        hit, kept_n = rep_meta.get("ann_hit", 0), rep_meta.get("kept", 0)
    else:
        hit = sum(w.get("ann_hits", 0) for w in data["windows"])
        kept_n = sum(w.get("kept_n", 0) for w in data["windows"])
        data["mode"] = md.classify_mode(ann_used, hit, kept_n)
    data["mode_coverage"] = md.coverage_line(hit, kept_n, ann_used=ann_used)

    # ECharts 内嵌：看板必须离线可开。教训——之前走 CDN，预览环境加载不到就整页白屏
    # （页面 DOM 全由 JS 生成，echarts 未定义即抛异常，一行内容都出不来）。
    vendor = os.path.join(ROOT, "tools", "vendor", "echarts.min.js")
    ech = ""
    if os.path.isfile(vendor):
        with open(vendor, encoding="utf-8") as f:
            ech = f.read()
        if "</script>" in ech.lower()[:2000] or len(ech) < 100000:
            ech = ""  # 内容异常时不内嵌，退回 CDN + 占位提示
    echart_block = ech if ech else (
        "document.write('<scr'+'ipt src=\"https://cdn.jsdelivr.net/npm/echarts@5.5.0"
        "/dist/echarts.min.js\"><\\/scr'+'ipt>');")
    page = (load_template()
            .replace("__ECHARTS__", echart_block)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__CROWDCOLOR__", json.dumps(CROWD_COLOR, ensure_ascii=False))
            .replace("__PLATSHORT__", json.dumps(PLATFORM_SHORT, ensure_ascii=False))
            # 这里是**文本**注入，不能用 json.dumps —— 那样会在页面上渲染出
            # 一对多余的字面引号：方向判定："关键词签名（…）"（原实现如此）。
            .replace("__MODE__", html.escape(data["mode"]))
            .replace("__GENERATED__", data["generated_at"])
            .replace("__HEALTH_N__", str(len(data.get("health") or [])))
            .replace("__PLATFORMS_JSON__", json.dumps(load_platforms(), ensure_ascii=False))
            .replace("__ANALYSIS_JSON__", json.dumps(load_analysis(), ensure_ascii=False))
            .replace("__VALIDATION_JSON__", json.dumps(load_validation(), ensure_ascii=False))
            .replace("__RESILIENCE_JSON__", json.dumps(load_resilience(), ensure_ascii=False)))

    # 占位符残留自检：漏替换会让页面出现 __XXX__ 字面量，或直接造成 JS 语法错误整页空白
    left = [t for t in ("__ECHARTS__", "__DATA__", "__CROWDCOLOR__", "__PLATSHORT__",
                        "__MODE__", "__GENERATED__", "__HEALTH_N__",
                        "__PLATFORMS_JSON__", "__ANALYSIS_JSON__", "__VALIDATION_JSON__",
                        "__RESILIENCE_JSON__")
            if t in page]
    if left:
        print(f"  !! 占位符未替换：{left}")

    ts = time.strftime("%Y%m%d-%H%M")
    out = os.path.join(OUT, f"dashboard_{ts}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print("看板 ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
