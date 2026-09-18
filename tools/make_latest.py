# -*- coding: utf-8 -*-
"""把最新一轮产出复制成稳定文件名（latest_*），并刷新 INDEX.md 的时间戳。

为什么需要：out/ 里累积了多轮次的带时间戳产物（dashboard_20260918-1543/1544/...），
人分不清哪份是当前该看的。**稳定命名**是最省事的解法——
读者只需要记 `latest_*`，而不是一串时间戳。

用法：
    python tools/make_latest.py
"""
import glob
import os
import re
import shutil
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

PAIRS = [
    ("dashboard_*.html", "latest_dashboard.html"),
    ("directions_*.md", "latest_directions.md"),
    ("directions_*.json", "latest_directions.json"),
    ("platforms_*.md", "latest_platforms.md"),
    ("analysis_*.md", "latest_analysis.md"),
]

# 固定名产出（本来就唯一，不需要时间戳）
FIXED = ["resilience.json", "validation_kits.json", "platform_analysis.json",
         "agent_annotations.json", "INDEX.md"]


def _latest(pat):
    f = sorted(glob.glob(os.path.join(OUT, pat)))
    return f[-1] if f else None


def main():
    rows = []
    for pat, dst in PAIRS:
        src = _latest(pat)
        if not src:
            print(f"  ! 未找到 {pat}（跳过）")
            continue
        shutil.copyfile(src, os.path.join(OUT, dst))
        rows.append((dst, os.path.basename(src), os.path.getsize(src)))

    for f in FIXED:
        p = os.path.join(OUT, f)
        if os.path.isfile(p):
            rows.append((f, f, os.path.getsize(p)))

    for d, s, n in rows:
        mark = "<-" if d != s else "  "
        print(f"  {d:<28} {mark} {s:<34} {n / 1024:>7.0f} KB")

    # 顺手把 INDEX.md 的生成时间刷新，避免读者以为索引是旧的
    ip = os.path.join(OUT, "INDEX.md")
    if os.path.isfile(ip):
        with open(ip, encoding="utf-8") as f:
            t = f.read()
        t2 = re.sub(r"生成时间：[0-9\-]+ [0-9:]+",
                    "生成时间：" + time.strftime("%Y-%m-%d %H:%M"), t, count=1)
        if t2 != t:
            with open(ip, "w", encoding="utf-8") as f:
                f.write(t2)
            print("  INDEX.md 时间戳已刷新")
    print(f"\n稳定名产出 {len(rows)} 份 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
