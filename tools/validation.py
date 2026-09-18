#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证台账 CLI —— 记录验证结果、查看北极星。

北极星指标：**近 7 天验证通过的方向数**（目标 ≥1）。
为什么用它当北极星：整条流水线的产出都不产生价值，只有"某个方向被真实验证过"
才产生价值——它同时度量了信号质量（推荐得对不对）和工作闭环（有没有真去做）。

用法：
  python tools/validation.py log "数据采集与解析" --window 今日 --result pass \\
      --intents 3 --note "问了 5 人，3 人已在为此付费"
  python tools/validation.py log "<方向>" --result reject --intents 0 --note "已有免费替代"
  python tools/validation.py log "<方向>" --result resurrect --note "此前否决，后被证明有价值（误杀）"
  python tools/validation.py stats
  python tools/validation.py queue        # 待验证队列（够格但没记录的）
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from hunter import validate as vd  # noqa: E402

OUT = os.path.join(ROOT, "out")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("log", help="记录一条验证结果")
    p.add_argument("direction")
    p.add_argument("--window", default="")
    p.add_argument("--result", required=True,
                   choices=["pass", "pending", "reject", "resurrect"])
    p.add_argument("--intents", type=int, default=0,
                   help="符合'已付费/明确预算'标准的受访者数")
    p.add_argument("--note", default="")
    p.add_argument("--url", action="append", default=[])

    sub.add_parser("stats", help="北极星与误杀率")
    sub.add_parser("queue", help="待验证队列")

    a = ap.parse_args()

    if a.cmd == "log":
        if a.result == "pass" and a.intents < 2:
            print("❌ 判定标准：通过必须有 ≥2 个受访者已在为此付费或给出明确预算"
                  f"（当前 --intents {a.intents}）。表达兴趣不算证据。")
            return 2
        rec = vd.add_record(a.direction, a.window, a.result, a.intents,
                            a.note, a.url)
        print("已记录：", json.dumps(rec, ensure_ascii=False))
        s = vd.stats()
        print(f"\n北极星（近 7 天验证通过方向数）：{s['north_star']} / 目标 {s['target']}")
        return 0

    if a.cmd == "stats":
        s = vd.stats()
        print(f"北极星（近 {s['window_days']} 天验证通过方向数）："
              f"**{s['north_star']}** / 目标 {s['target']} "
              f"{'✅ 达标' if s['north_star'] >= s['target'] else '❌ 未达标'}")
        print(f"  待续：{len(s['pending'])} 个 {s['pending']}")
        print(f"  否决：{len(s['rejected'])} 个 {s['rejected']}")
        print(f"  误杀复活：{len(s['resurrected'])} 个 {s['resurrected']}")
        mr = s["mistake_rate"]
        print(f"  误杀率（复活 / 否决+复活）：{'—' if mr is None else f'{mr:.0%}'}")
        print(f"  台账记录总数：{s['total_records']}")
        return 0

    if a.cmd == "queue":
        jp = sorted([f for f in os.listdir(OUT) if f.startswith("directions_")
                     and f.endswith(".json")])
        if not jp:
            print("找不到 directions_*.json")
            return 2
        with open(os.path.join(OUT, jp[-1]), encoding="utf-8") as f:
            d = json.load(f)
        rows_by_window = {v["label"]: v["directions"] for v in d["windows"].values()}
        q = vd.pending_queue(rows_by_window)
        if not q:
            print("待验证队列为空——够格的方向都已有记录。")
        for x in q:
            print(f"  [{x['window']}] {x['direction']}　{x['advice']}　趋势 {x['trend']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
